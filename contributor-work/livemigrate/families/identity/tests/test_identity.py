import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import runtime
import scenarios


class IdentityTests(unittest.TestCase):
    def candidate(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name)
        for role in ("db", "api", "consumer"):
            shutil.copyfile(HERE / "reference" / (role + ".py"), path / (role + ".py"))
        return path

    def append(self, path, role, source):
        with (path / (role + ".py")).open("a") as stream:
            stream.write(source)

    def assert_static_false_positive(self, result):
        self.assertTrue(result["static"]["passed"], result)
        self.assertFalse(result["trace"]["passed"], result)
        self.assertEqual(result["status"], "scored", result)
        self.assertEqual(result["score"], 0.0, result)

    def test_reference_all_declared_traces(self):
        result = runtime.run_suite(HERE / "reference", "all")
        self.assertEqual(result["passed"], 4, result)
        self.assertEqual(result["score"], 1.0)

    def test_regenerated_legacy_id_passes_final_database_but_duplicates_effect(self):
        path = self.candidate()
        self.append(path, "consumer", '''
_base_consume = consume
def consume(conn, event):
    import json
    result = _base_consume(conn, event)
    if result["operation_id"].startswith('["legacy",'):
        result["operation_id"] = json.dumps(["tenant", result["tenant_id"], result["request_id"]], ensure_ascii=False, separators=(",", ":"))
        result["idempotency_key"] = result["operation_id"]
    return result
''')
        result = runtime.execute(path, scenarios.PUBLIC[0])
        self.assert_static_false_positive(result)
        self.assertGreater(result["trace"]["physical_effects"], result["trace"]["accepted_operations"])

    def test_ambiguous_global_lookup_after_collision_corrupts_old_delivery(self):
        path = self.candidate()
        self.append(path, "consumer", '''
_base_consume = consume
def consume(conn, event):
    result = _base_consume(conn, event)
    row = conn.execute("SELECT * FROM accepted_requests WHERE request_id=? ORDER BY tenant_id DESC LIMIT 1", (result["request_id"],)).fetchone()
    result = dict(row)
    result["idempotency_key"] = result["operation_id"]
    return result
''')
        result = runtime.execute(path, scenarios.PUBLIC[0])
        self.assert_static_false_positive(result)
        self.assertIn("incorrect_settlement_attempt", {item["code"] for item in result["trace"]["violations"]})

    def test_latest_balance_is_not_immutable_delta(self):
        path = self.candidate()
        self.append(path, "consumer", '''
_base_consume = consume
def consume(conn, event):
    result = _base_consume(conn, event)
    result["delta"] = conn.execute("SELECT balance FROM accounts WHERE tenant_id=? AND account_id=?", (result["tenant_id"], result["account_id"])).fetchone()[0]
    return result
''')
        result = runtime.execute(path, scenarios.PUBLIC[0])
        self.assert_static_false_positive(result)
        self.assertIn("incorrect_physical_effects", {item["code"] for item in result["trace"]["violations"]})

    def test_naive_consumer_scope_encoding_collides_for_distinct_pairs(self):
        path = self.candidate()
        self.append(path, "consumer", '''
_base_consume = consume
def consume(conn, event):
    result = _base_consume(conn, event)
    if event["version"] == 3:
        result["operation_id"] = result["tenant_id"] + ":" + result["request_id"]
        result["idempotency_key"] = result["operation_id"]
    return result
''')
        result = runtime.execute(path, scenarios.HELDOUT[1])
        self.assert_static_false_positive(result)
        self.assertIn("sink_key_conflict", {item["code"] for item in result["trace"]["violations"]})

    def test_alternate_ids_and_immutable_record_lookup_are_valid(self):
        path = self.candidate()
        api = (path / "api.py").read_text().replace('["tenant", tenant, key]', '["implementation-owned", key, tenant]')
        (path / "api.py").write_text(api)
        self.append(path, "api", '''
_base_handle = handle
def handle(conn, request, phase):
    result = _base_handle(conn, request, phase)
    if result.get("ok") and "operation_id" in result and phase != "overlap":
        operation = result["operation_id"]
        conn.execute("UPDATE outbox SET version=77,payload=? WHERE operation_id=? AND version=3", (json.dumps({"accepted": operation}), operation))
    return result
''')
        self.append(path, "consumer", '''
_base_consume = consume
def consume(conn, event):
    if event["version"] != 77:
        return _base_consume(conn, event)
    row = conn.execute("SELECT * FROM accepted_requests WHERE operation_id=?", (event["payload"]["accepted"],)).fetchone()
    result = dict(row)
    result["idempotency_key"] = result["operation_id"]
    return result
''')
        result = runtime.run_suite(path, "all")
        self.assertEqual(result["passed"], 4, result)

    def test_transient_conflict_balance_change_not_erased_by_repair(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        dirty = [False]
        def invoke(role, function, conn, *args):
            result = trusted(role, function, conn, *args)
            if role == "api" and args[0].get("op") == "credit" and args[0].get("request_id") == "shared":
                request = args[0]
                with conn:
                    if request["delta"] == 99:
                        conn.execute("UPDATE accounts SET balance=balance+41 WHERE tenant_id='beta' AND account_id='wallet'")
                        dirty[0] = True
                    elif dirty[0] and request["account_id"] == "reserve":
                        conn.execute("UPDATE accounts SET balance=balance-41 WHERE tenant_id='beta' AND account_id='wallet'")
                        dirty[0] = False
            return result
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assert_static_false_positive(result)
        self.assertIn("incorrect_balances", {item["code"] for item in result["trace"]["violations"]})

    def test_global_deduplication_forever_fails_required_scoped_progress(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        def invoke(role, function, conn, *args):
            if role == "api" and args[0].get("op") == "credit" and args[1] != "overlap":
                request = args[0]
                other = conn.execute("SELECT 1 FROM accepted_requests WHERE request_id=? AND tenant_id!=?", (request["request_id"], request["tenant_id"])).fetchone()
                if other is not None:
                    return {"ok": False, "error": "idempotency_conflict"}
            return trusted(role, function, conn, *args)
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "scored", result)
        self.assertEqual(result["score"], 0.0)

    def test_duplicate_audit_rows_are_not_hidden_by_dict_conversion(self):
        trusted = runtime.trusted_invoker(HERE / "reference")
        def invoke(role, function, conn, *args):
            result = trusted(role, function, conn, *args)
            if role == "db" and function == "expand":
                with conn:
                    definition = conn.execute("SELECT sql FROM sqlite_master WHERE name='accepted_requests'").fetchone()[0]
                    conn.execute("DROP VIEW accepted_requests")
                    conn.execute(definition.replace("accepted_requests", "underlying_requests", 1))
                    conn.execute("CREATE VIEW accepted_requests AS SELECT * FROM underlying_requests UNION ALL SELECT * FROM underlying_requests")
            return result
        result = runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)
        self.assertFalse(result["passed"])
        self.assertIn("duplicate_ledger_rows", {item["code"] for item in result["trace"]["violations"]})

    def test_invalid_candidates_and_infrastructure_are_not_scored_as_zero(self):
        result = runtime.run_suite(HERE / "starter", "public")
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertIsNone(result["score"])
        class InfrastructureError(RuntimeError):
            infrastructure_error = True
        def invoke(*args):
            raise InfrastructureError("synthetic failure")
        with self.assertRaises(InfrastructureError):
            runtime.execute(HERE / "reference", scenarios.PUBLIC[0], invoke=invoke)


if __name__ == "__main__":
    unittest.main()
