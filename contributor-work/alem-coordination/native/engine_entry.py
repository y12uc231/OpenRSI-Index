"""Trusted native engine entry: same scientific code and normal image CPU affinity."""
import sys
if __name__ == "__main__" and (not getattr(sys.flags, "safe_path", False)
        or not sys.flags.no_user_site or sys.flags.hash_randomization):
    raise SystemExit("native engine requires sanitized python -P -s -B with hashseed0")
import importlib.util
import os
from pathlib import Path
import runpy
ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("alem_native_support", ROOT / "runtime_support.py")
support = importlib.util.module_from_spec(spec)
exec(compile((ROOT / "runtime_support.py").read_bytes(), str(ROOT / "runtime_support.py"), "exec"), support.__dict__)
support.load_file("wire", ROOT.parent / "controller/wire.py")
with support.engine_source(Path("/app"), parent="/var/lib"):
    runpy.run_path(str(ROOT / "engine.py"), run_name="__main__")
