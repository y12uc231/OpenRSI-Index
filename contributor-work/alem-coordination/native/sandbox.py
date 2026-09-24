"""Construct actor roots using existing local Python. No daemon or downloads."""
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CONTROLLER = ROOT.parent / "controller"


def copy_runtime(target):
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        raise RuntimeError("validated native route requires Linux Python3.12")
    stdlib = Path("/usr/local/lib/python3.12")
    if not stdlib.is_dir():
        raise RuntimeError("expected image Python layout unavailable")
    shutil.copytree(stdlib, target / "usr/local/lib/python3.12", ignore=shutil.ignore_patterns("site-packages", "__pycache__"))
    # Dynamic stdlib extensions need system libraries. ldd inspects only the
    # image's trusted binary/modules, never candidate bytes.
    binaries = [Path(sys.executable).resolve()] + list((stdlib / "lib-dynload").glob("*.so"))
    libraries = set()
    for binary in binaries:
        result = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, check=True, timeout=10)
        libraries.update(re.findall(r"(?<!\S)(/[^\s()]+)", result.stdout))
    for name in libraries:
        source = Path(name)
        destination = target / source.relative_to("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (target / "driver").mkdir()
    for name in ("controller_driver.py", "wire.py"):
        shutil.copyfile(CONTROLLER / name, target / "driver" / name)
    for path in target.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)


def actor_root(template, destination, candidate, actor):
    uid = 10001 + actor
    # Copies, not shared writable files or hardlinks to the Work tree.
    shutil.copytree(template, destination)
    destination.chmod(0o755)
    (destination / "candidate").mkdir(mode=0o755)
    shutil.copyfile(candidate / "controller.py", destination / "candidate/controller.py")
    (destination / "candidate/controller.py").chmod(0o444)
    (destination / "tmp").mkdir(mode=0o555)
    (destination / "tmp/scratch").touch(mode=0o666)
    (destination / "tmp/scratch").chmod(0o666)
    (destination / "dev").mkdir(mode=0o755)
    os.mknod(destination / "dev/null", stat.S_IFCHR | 0o666, os.makedev(1, 3))
    (destination / "dev/null").chmod(0o666)
    cpus = sorted(os.sched_getaffinity(0))
    cpu = cpus[-3:][actor % len(cpus[-3:])]
    # -I would ignore PYTHONHASHSEED and change arbitrary controller semantics.
    # Start with an empty environment, fixed seed, no site, and safe import path.
    return ["/usr/bin/env", "-i", "PYTHONHASHSEED=0", "PYTHONDONTWRITEBYTECODE=1",
            sys.executable, "-P", "-B", "-S", str(ROOT / "actor_bootstrap.py"),
            str(destination), str(uid), str(cpu)]
