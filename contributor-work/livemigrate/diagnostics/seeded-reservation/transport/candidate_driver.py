"""One callback RPC. This file runs only in the candidate container."""
import contextlib
import importlib.util
import json
import os
import resource
import sqlite3
import sys

CALLS = {"db": {"expand", "backfill", "contract", "on_message"},
         "api": {"handle", "on_message"}, "consumer": {"consume", "on_message"}}


def main():
    connection = None
    try:
        # Non-root driver cannot raise this hard limit. Unlike a container-wide
        # cap equal to its exact process count, this leaves runc/tini headroom
        # while denying candidate forks and threads after a successful return.
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        raw = sys.stdin.buffer.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("RPC input limit exceeded")
        request = json.loads(raw)
        if set(request) != {"role", "function", "database", "args"}:
            raise ValueError("invalid RPC fields")
        role, function = request["role"], request["function"]
        if role not in CALLS or function not in CALLS[role]:
            raise ValueError("invalid callback")
        database = request["database"]
        if not isinstance(database, str) or not database.startswith("/db/") or "/" in database[4:]:
            raise ValueError("invalid database path")
        if not isinstance(request["args"], list):
            raise ValueError("args must be an array")
        # The consumer also has a read-only filesystem mount. query_only alone
        # would not stop candidate code from opening a second connection.
        readonly = role == "consumer" and function == "consume"
        if readonly:
            connection = sqlite3.connect("file:" + database + "?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
        else:
            connection = sqlite3.connect(database, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN" if readonly else "BEGIN IMMEDIATE")
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            # Optional helper path is fixed by the trusted CLI, never by RPC.
            # Only its published source file is copied; no oracle is imported.
            if os.path.isfile("/candidate/legacy.py"):
                legacy_spec = importlib.util.spec_from_file_location("legacy", "/candidate/legacy.py")
                legacy = importlib.util.module_from_spec(legacy_spec)
                sys.modules["legacy"] = legacy
                legacy_spec.loader.exec_module(legacy)
            spec = importlib.util.spec_from_file_location("candidate_" + role, "/candidate/" + role + ".py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = getattr(module, function)(connection, *request["args"])
            # Check JSON before committing so an invalid result cannot silently
            # commit through this driver. Deliberate candidate commits remain
            # contract violations for the host's independent trace checks.
            encoded = json.dumps({"rpc_version": 1, "ok": True, "result": result}, allow_nan=False, separators=(",", ":"))
            connection.commit()
        sys.stdout.write(encoded + "\n")
    except BaseException as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        error = {"rpc_version": 1, "ok": False, "error": type(exc).__name__ + ": " + str(exc)[:1000]}
        sys.stdout.write(json.dumps(error, allow_nan=False) + "\n")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
