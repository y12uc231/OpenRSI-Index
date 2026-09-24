"""Published immutable central reservation engine; called on source only."""
import json


def fingerprint(lines):
    return json.dumps(lines, sort_keys=True, separators=(",", ":"))


def reserve(conn, reservation_id, lines):
    encoded = fingerprint(lines)
    old = conn.execute("SELECT * FROM legacy_requests WHERE reservation_id=?", (reservation_id,)).fetchone()
    if old:
        return {"status": old["status"] if old["fingerprint"] == encoded else "idempotency_conflict", "lines": lines}
    for sku, qty in lines.items():
        stock = conn.execute("SELECT * FROM legacy_stock WHERE sku=?", (sku,)).fetchone()
        if not stock["active"]:
            raise ValueError("legacy caller failed to fence routing")
        if conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (sku,)).fetchone():
            raise ValueError("legacy caller must defer behind tentative holds")
    status = "committed" if all(conn.execute("SELECT available FROM legacy_stock WHERE sku=?", (sku,)).fetchone()[0] >= qty for sku, qty in lines.items()) else "out_of_stock"
    if status == "committed":
        for sku, qty in lines.items():
            conn.execute("UPDATE legacy_stock SET available=available-? WHERE sku=?", (qty, sku))
            conn.execute("INSERT INTO legacy_holds VALUES(?,?,?,'committed')", (reservation_id, sku, qty))
    conn.execute("INSERT INTO legacy_requests VALUES(?,?,?,?)", (reservation_id, encoded, status, encoded))
    return {"status": status, "lines": lines}
