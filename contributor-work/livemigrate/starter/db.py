"""Implement the DB role described in API_CONTRACT.md."""


def expand(conn):
    raise NotImplementedError("implement compatible expansion")


def backfill(conn, cursor, limit):
    raise NotImplementedError("implement incremental backfill")


def contract(conn):
    raise NotImplementedError("implement safe contraction")
