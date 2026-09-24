def expand(conn):
    raise NotImplementedError("implement compatible ledger expansion and audit view")


def backfill(conn, cursor, limit):
    raise NotImplementedError("implement incremental identity-preserving import")


def contract(conn):
    raise NotImplementedError("retire global-key table without rebinding operations")
