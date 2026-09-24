import copy
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import runtime
import scenarios


class RuntimeTests(unittest.TestCase):
    def candidate(self, consumer=None, db_suffix=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = pathlib.Path(temp.name)
        for role in ("db", "api", "consumer"):
            shutil.copyfile(HERE / "reference" / (role + ".py"), path / (role + ".py"))
        if consumer is not None:
            (path / "consumer.py").write_text(consumer)
        if db_suffix is not None:
            with (path / "db.py").open("a") as stream:
                stream.write(db_suffix)
        return path

    def assert_static_only_false_positive(self, result):
        self.assertTrue(result["static"]["passed"], result)
        self.assertFalse(result["trace"]["passed"], result)
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["status"], "scored", result)
        self.assertEqual(result["score"], 0.0)

    def test_reference_passes_public_and_all_temporal_variants(self):
        result = runtime.run_suite(HERE / "reference", "all")
        self.assertEqual(result["passed"], result["total"], result)
        self.assertEqual(result["score"], 1.0)

    def test_cents_authoritative_overlap_can_keep_unused_stale_shadow(self):
        path = self.candidate(db_suffix='''
_original_expand = expand
def expand(conn):
    _original_expand(conn)
    conn.execute("DROP TRIGGER orders_update_bridge")
''')
        source = (path / "api.py").read_text()
        source = source.replace('amount = order["amount_micros"]', 'amount = order["amount_cents"] * 10000 if phase == "overlap" else order["amount_micros"]')
        (path / "api.py").write_text(source)
        result = runtime.run_suite(path, "all")
        self.assertEqual(result["passed"], result["total"], result)
        self.assertEqual(result["score"], 1.0)

    def test_current_order_read_corrupts_delayed_payment_despite_clean_final_db(self):
        path = self.candidate(consumer='''
def consume(conn, event):
    p = event["payload"]
    row = conn.execute("SELECT * FROM orders WHERE order_id=?", (p["order_id"],)).fetchone()
    amount = row["amount_micros"]
    if amount is None:
        amount = row["amount_cents"] * 10000
    return {"payment_id": p["payment_id"], "idempotency_key": p["payment_id"], "amount_micros": amount}
''')
        result = runtime.execute(path, scenarios.PUBLIC[0])
        self.assert_static_only_false_positive(result)
        self.assertIn("incorrect_physical_effects", {item["code"] for item in result["trace"]["violations"]})

    def test_legacy_unit_error_passes_final_db_but_fails_receipts(self):
        path = self.candidate(consumer='''
def consume(conn, event):
    p = event["payload"]
    amount = p["amount_micros"] if "amount_micros" in p else p["amount_cents"]
    return {"payment_id": p["payment_id"], "idempotency_key": p["payment_id"], "amount_micros": amount}
''')
        self.assert_static_only_false_positive(runtime.execute(path, scenarios.PUBLIC[0]))

    def test_changed_idempotency_namespace_duplicates_cross_version_effect(self):
        path = self.candidate(consumer='''
def consume(conn, event):
    p = event["payload"]
    amount = p["amount_micros"] if event["version"] == 2 else p["amount_cents"] * 10000
    return {"payment_id": p["payment_id"], "idempotency_key": "v2:" + p["payment_id"], "amount_micros": amount}
''')
        result = runtime.execute(path, scenarios.PUBLIC[0])
        self.assert_static_only_false_positive(result)
        self.assertGreater(result["trace"]["physical_effects"], result["trace"]["accepted_payments"])

    def test_final_reconciliation_cannot_erase_stale_backfill_read(self):
        path = self.candidate(db_suffix='''
_original_expand = expand
def expand(conn):
    _original_expand(conn)
    conn.execute("DROP TRIGGER orders_update_bridge")
''')
        scenario = {"name": "final_repair_counterexample", "initial_orders": [{"order_id": "A", "revision": 1, "amount_cents": 1000}], "steps": [
            {"kind": "expand"}, {"kind": "backfill", "limit": 1},
            {"kind": "request", "actor": 1, "phase": "overlap", "request": {"op": "put", "order_id": "A", "expected_revision": 1, "amount_cents": 1500}},
            {"kind": "request", "actor": 2, "phase": "overlap", "request": {"op": "get", "order_id": "A"}},
            {"kind": "backfill_all", "limit": 1}, {"kind": "contract"},
        ]}
        result = runtime.execute(path, scenario)
        self.assert_static_only_false_positive(result)
        failures = result["trace"]["violations"]
        read = next(item for item in failures if item["code"] == "incorrect_request_result")
        self.assertEqual(read["expected"]["amount_micros"], 15000000)
        self.assertEqual(read["observed"]["amount_micros"], 10000000)

    def test_transient_conflict_mutation_is_retained_after_later_valid_repair(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        def invoke(role, function, conn, *args):
            result = trusted(role, function, conn, *args)
            if role == "api" and args[0].get("payment_id") == "p_conflict":
                with conn:
                    conn.execute("UPDATE orders SET amount_cents=42,amount_micros=420000 WHERE order_id='A'")
            return result
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assert_static_only_false_positive(result)
        self.assertIn("incorrect_live_row", {item["code"] for item in result["trace"]["violations"]})

    def test_api_conflict_and_preexisting_payment_replay_are_covered(self):
        scenario = copy.deepcopy(scenarios.PUBLIC[0])
        self.assertEqual(scenario["steps"][0]["request"]["payment_id"], "p_preexisting")
        result = runtime.execute(HERE / "reference", scenario)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["trace"]["accepted_payments"], 5)

    def test_external_infrastructure_failure_propagates_unscored(self):
        class InfrastructureFailure(RuntimeError):
            infrastructure_error = True
        def invoke(*args):
            raise InfrastructureFailure("synthetic transport error")
        with self.assertRaises(InfrastructureFailure):
            runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)

    def test_missing_or_unimplemented_candidate_is_unscored(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = runtime.execute(temp, scenarios.PUBLIC[0])
        self.assertEqual(missing["status"], "candidate_invalid")
        self.assertIsNone(missing["score"])
        result = runtime.run_suite(HERE / "starter", "public")
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertIsNone(result["score"])

    def test_hook_receives_only_closed_transaction_and_disk_database(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        def invoke(role, function, conn, *args):
            self.assertFalse(conn.in_transaction)
            self.assertTrue(pathlib.Path(conn.execute("PRAGMA database_list").fetchone()[2]).is_file())
            return trusted(role, function, conn, *args)
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assertTrue(result["passed"], result)

    def test_integer_ok_does_not_satisfy_boolean_response_contract(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        def invoke(role, function, conn, *args):
            result = trusted(role, function, conn, *args)
            if role == "api" and isinstance(result, dict) and result.get("ok") is True:
                result["ok"] = 1
            return result
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assert_static_only_false_positive(result)


if __name__ == "__main__":
    unittest.main()
