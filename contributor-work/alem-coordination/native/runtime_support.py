"""Exact task imports and fresh private engine source staging.

The supervisor starts with -I; its engine starts with an empty explicit
environment, -P -s and hashseed0. This guards task-owned import paths;
inherited Python/system libraries remain the documented platform boundary.
"""
import contextlib
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile


def load_file(name, path):
    """Load exactly one regular task file, ignoring search paths and caches."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("task module must be a regular file")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # -B prevents writes, not reads of .pyc files. Work may leave an unchecked
    # timestamp-valid cache beside a task file, so compile the exact source.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def task_modules(native):
    """Only these known modules satisfy the frozen helpers' relative imports."""
    native = Path(native)
    controller = native.parent / "controller"
    wire = load_file("wire", controller / "wire.py")
    feedback = load_file("feedback", controller / "feedback.py")
    launcher = load_file("launcher", controller / "launcher.py")
    sandbox = load_file("alem_native_sandbox", native / "sandbox.py")
    return wire, feedback, launcher, sandbox


@contextlib.contextmanager
def engine_source(source, parent=None):
    """Stage previously hash-verified code; never add shared /tmp to sys.path."""
    source = Path(source)
    previous = list(sys.path)
    with tempfile.TemporaryDirectory(prefix="alem-engine-", dir=parent) as name:
        root = Path(name)
        # TemporaryDirectory is newly created, mode0700, owned by the verifier.
        # Both import roots contain only copies of the verified source tree.
        shutil.copytree(source / "alem", root / "alem")
        shutil.copytree(source / "baselines", root / "baselines")
        sys.path[:0] = [str(root), str(root / "baselines")]
        try:
            yield root
        finally:
            sys.path[:] = previous
