"""Trusted synthetic controls; no model outputs or API calls."""
import copy
import pathlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import runtime
import scenarios

ROOT = pathlib.Path(runtime.__file__).parent


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.candidate = pathlib.Path(self.temp.name)
        for role in ("db", "api", "consumer"):
            shutil.copyfile(ROOT / "reference" / (role + ".py"), self.candidate / (role + ".py"))

    def append(self, role, text):
        path = self.candidate / (role + ".py")
        path.write_text(path.read_text() + "\n" + text)

    def replace(self, role, old, new):
        path = self.candidate / (role + ".py")
        source = path.read_text()
        self.assertIn(old, source)
        path.write_text(source.replace(old, new))

    def public(self):
        return runtime.execute(self.candidate, scenarios.PUBLIC[0])

    def assert_final_pass_trace_fail(self, result, code):
        self.assertEqual(result["status"], "scored", result)
        self.assertTrue(result["static"]["passed"], result)
        self.assertTrue(result["completion"]["passed"], result)
        self.assertFalse(result["passed"], result)
        self.assertIn(code, {e["code"] for e in result["trace"]["violations"]}, result)

    def test_reference_all_faults_are_exercised(self):
        result = runtime.run_suite(self.candidate, "all")
        self.assertEqual(result["passed"], 4, result)
        self.assertGreater(result["cases"][1]["faults"]["replayed_packets"], 0)
        self.assertTrue(result["cases"][2]["faults"]["lost_effect_ack"])
        self.assertEqual(result["cases"][3]["faults"]["lost_output_trigger"]["input_kind"], "move")

    def test_consistent_alternative_wire_and_target_schema(self):
        for role in ("db", "api", "consumer"):
            self.append(role, '''
_base = on_message
def on_message(conn, message):
    import copy
    message = copy.deepcopy(message)
    if 'verb' in message['body']:
        message['body']['kind'] = message['body'].pop('verb')[len('alternate:'):]
    result = _base(conn, message)
    for packet in result['messages']:
        packet['body']['verb'] = 'alternate:' + packet['body'].pop('kind')
    return result
''')
        for old, new in (("EXISTS stock(", "EXISTS target_inventory("), ("FROM stock", "FROM target_inventory"), ("INTO stock", "INTO target_inventory"), ("UPDATE stock", "UPDATE target_inventory")):
            self.replace("consumer", old, new)
        result = runtime.run_suite(self.candidate, "all")
        self.assertEqual(result["passed"], 4, result)

    def test_per_sku_drain_before_handoff_is_valid(self):
        self.append("db", '''
_base = on_message
def on_message(conn, message):
    import json
    conn.execute('CREATE TABLE IF NOT EXISTS deferred_moves(sku TEXT PRIMARY KEY,payload TEXT)')
    body = message['body']
    if body['kind'] == 'move' and conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (body['sku'],)).fetchone():
        conn.execute('INSERT OR REPLACE INTO deferred_moves VALUES(?,?)', (body['sku'], json.dumps(message)))
        result = _base(conn, {'src':'driver','body':{'kind':'tick'}})
    else:
        result = _base(conn, message)
    for row in conn.execute('SELECT * FROM deferred_moves').fetchall():
        if not conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (row['sku'],)).fetchone():
            conn.execute('DELETE FROM deferred_moves WHERE sku=?', (row['sku'],))
            extra = _base(conn, json.loads(row['payload']))
            result['messages'] += extra['messages']
            result['replies'] += extra['replies']
    return result
''')
        self.assertEqual(runtime.run_suite(self.candidate, "all")["passed"], 4)

    def test_deferred_move_still_exercises_post_fence_output_loss(self):
        self.append("db", '''
_base = on_message
def on_message(conn, message):
    import json
    conn.execute('CREATE TABLE IF NOT EXISTS next_tick_moves(sku TEXT PRIMARY KEY,payload TEXT)')
    if message['body']['kind'] == 'move':
        conn.execute('INSERT OR REPLACE INTO next_tick_moves VALUES(?,?)', (message['body']['sku'],json.dumps(message)))
        return _base(conn, {'src':'driver','body':{'kind':'tick'}})
    result = _base(conn, message)
    if message['body']['kind'] == 'tick':
        for row in conn.execute('SELECT * FROM next_tick_moves').fetchall():
            conn.execute('DELETE FROM next_tick_moves WHERE sku=?', (row['sku'],))
            extra = _base(conn, json.loads(row['payload']))
            result['messages'] += extra['messages']
            result['replies'] += extra['replies']
    return result
''')
        result = runtime.run_suite(self.candidate, "all")
        self.assertEqual(result["passed"], 4, result)
        self.assertTrue(result["cases"][3]["faults"]["lost_output"])
        self.assertEqual(result["cases"][3]["faults"]["lost_output_trigger"]["input_kind"], "tick")

    def test_durable_global_commit_allows_early_ack(self):
        self.replace("api", 'call["state"] in ("committed", "rejected")', 'call["state"] in ("committing", "committed", "rejected")')
        self.replace("api", 'call["state"] == "committed" else call["reason"]', 'call["state"] in ("committing", "committed") else call["reason"]')
        self.assertEqual(runtime.run_suite(self.candidate, "all")["passed"], 4)

    def test_premature_fulfillment_cannot_be_repaired_away(self):
        self.append("api", '''
_base = on_message
def on_message(conn, message):
    import json
    result = _base(conn, message)
    for row in conn.execute("SELECT calls.* FROM calls JOIN transactions USING(reservation_id) WHERE transactions.state='preparing' AND reservation_id='bundle'"):
        result['replies'].append({'call_id':row['call_id'],'reservation_id':row['reservation_id'],'lines':json.loads(row['lines_json']),'status':'committed'})
    return result
''')
        self.assert_final_pass_trace_fail(self.public(), "fulfillment_without_commit_certificate")

    def test_global_head_of_line_blocking_violates_independent_window(self):
        self.replace("api", "if not busy.intersection(lines):", "if not busy:")
        self.assert_final_pass_trace_fail(self.public(), "stable_window_progress_failure")

    def test_temporary_authority_overlap_survives_final_repair(self):
        self.append("db", '''
_base = on_message
def on_message(conn, message):
    result = _base(conn, message)
    for move in conn.execute('SELECT * FROM moves'):
        conn.execute('UPDATE legacy_stock SET active=? WHERE sku=?', (0 if move['state']=='done' else 1,move['sku']))
    return result
''')
        self.assert_final_pass_trace_fail(self.public(), "multiple_active_owners")

    def test_release_after_global_commit_is_permanent_violation(self):
        self.append("api", '''
_base = on_message
def on_message(conn, message):
    result = _base(conn, message)
    conn.execute('CREATE TABLE IF NOT EXISTS injected_once(id INTEGER PRIMARY KEY)')
    if not conn.execute('SELECT 1 FROM injected_once').fetchone():
        row = conn.execute("SELECT * FROM transactions WHERE state='committing' AND reservation_id='bundle'").fetchone()
        if row:
            conn.execute('INSERT INTO injected_once VALUES(1)')
            for packet in result['messages']:
                if packet['body'].get('reservation_id') == 'bundle':
                    packet['body']['kind'] = 'abort'
    return result
''')
        result = self.public()
        self.assertFalse(result["passed"])
        self.assertIn("global_commit_without_reserved_lines", {e["code"] for e in result["trace"]["violations"]})

    def test_aborted_partial_bundle_must_release_its_other_line(self):
        self.append("consumer", '''
_base = on_message
def on_message(conn, message):
    body = message['body']
    if body.get('kind') == 'abort':
        holder = conn.execute("SELECT * FROM holds WHERE reservation_id=? AND sku=? AND state='prepared'", (body['reservation_id'],body['sku'])).fetchone()
        if holder:
            result = _base(conn, {'src':'driver','body':{'kind':'tick'}})
            result['messages'].append({'to':'gateway','body':{'kind':'aborted','reservation_id':body['reservation_id'],'sku':body['sku']}})
            return result
    return _base(conn, message)
''')
        result = self.public()
        self.assertEqual(result["status"], "scored", result)
        self.assertFalse(result["passed"])
        self.assertFalse(result["history"]["passed"], result)
        self.assertFalse(result["static"]["passed"], result)

    def test_global_identity_across_legacy_and_new_entrypoints(self):
        scenario = copy.deepcopy(scenarios.PUBLIC[0])
        scenario["steps"] = [
            scenarios.client("one", "shared", {"Z": 1}), scenarios.rounds(10),
            scenarios.client("retry", "shared", {"Z": 1}, "source"), scenarios.rounds(8),
            {"kind":"move", "sku":"X", "destination":"A"}, scenarios.rounds(10),
            scenarios.client("two", "after", {"Z": 1}, "source"), scenarios.rounds(10),
            scenarios.client("conflict", "after", {"X": 1}), scenarios.rounds(10),
            {"kind":"move", "sku":"Y", "destination":"B"}, scenarios.rounds(15),
        ]
        result = runtime.execute(self.candidate, scenario)
        self.assertTrue(result["passed"], result)

    def test_invalid_candidate_is_unscored(self):
        (self.candidate / "consumer.py").write_text("invalid syntax !")
        result = self.public()
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertIsNone(result["score"])

    def test_infrastructure_error_propagates(self):
        class InfraError(RuntimeError):
            infrastructure_error = True
        def broken(*args):
            raise InfraError()
        with self.assertRaises(InfraError):
            runtime.execute(self.candidate, scenarios.PUBLIC[0], invoke=broken)

    def test_history_bound_exhaustion_is_unscored(self):
        with mock.patch.object(runtime, "check_history", return_value={"passed":False, "reason":"bound_exhausted", "exhaustive":False, "explored":1}):
            result = self.public()
        self.assertEqual(result["status"], "unscored_checker_bound")
        self.assertIsNone(result["score"])

    def test_callback_work_bound_is_structured_and_stops_dispatch(self):
        with mock.patch.object(runtime, "MAX_CALLBACKS", 5):
            result = self.public()
        self.assertEqual(result["status"], "candidate_invalid", result)
        self.assertIsNone(result["score"])
        self.assertEqual(result["completion"]["candidate_callbacks"], 5)
        errors = [item for item in result["trace"]["violations"] if item.get("error_type") == "CallbackWorkBound"]
        self.assertEqual(len(errors), 1)

    def test_recursive_audit_view_is_bounded_and_unscored(self):
        self.append("consumer", '''
_base = on_message
def on_message(conn, message):
    result = _base(conn, message)
    conn.execute('DROP VIEW IF EXISTS audit_inventory')
    conn.execute("CREATE VIEW audit_inventory AS WITH RECURSIVE infinite(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM infinite) SELECT sum(n) AS sku,0 AS total,0 AS available,0 AS epoch,'active' AS authority FROM infinite")
    return result
''')
        result = self.public()
        self.assertEqual(result["status"], "unscored_audit_bound", result)
        self.assertIsNone(result["score"])

    def test_finite_audit_row_excess_is_unscored(self):
        self.append("consumer", '''
_base = on_message
def on_message(conn, message):
    result = _base(conn, message)
    conn.execute('DROP VIEW IF EXISTS audit_inventory')
    conn.execute("CREATE VIEW audit_inventory AS WITH RECURSIVE rows(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM rows WHERE n<101) SELECT 'X' AS sku,3 AS total,3 AS available,1 AS epoch,'staged' AS authority FROM rows")
    return result
''')
        result = self.public()
        self.assertEqual(result["status"], "unscored_audit_bound", result)
        self.assertIsNone(result["score"])

    def test_missing_gateway_audit_view_returns_invalid_without_final_crash(self):
        self.append("api", '''
_base = on_message
def on_message(conn, message):
    result = _base(conn, message)
    conn.execute('DROP VIEW audit_decisions')
    return result
''')
        result = self.public()
        self.assertEqual(result["status"], "candidate_invalid", result)
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
