"""Linux actor bootstrap: chroot + distinct UID + no-new-privileges + seccomp."""
import ctypes
import errno
import os
from pathlib import Path
import platform
import resource
import runpy
import sys


def restrict_syscalls():
    # Reject forbidden syscall creation paths before any candidate import.
    numbers = {
        "x86_64": [203, 240, 241, 242, 243, 244, 245, 29, 30, 31, 64, 65, 66, 67, 68, 69, 70, 71, 220, 41, 42, 43, 44, 45, 46, 47, 49, 50, 53, 56, 57, 58, 59, 101,
                   165, 166, 272, 288, 298, 304, 308, 310, 311, 321, 322, 323, 425, 426, 427, 435],
        "aarch64": [122, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 39, 40, 97, 117, 198, 199, 200, 201, 202, 203, 206, 207, 211,
                    212, 220, 221, 241, 242, 265, 268, 270, 271, 280, 281, 282, 425, 426, 427, 435],
    }
    arches = {"x86_64": 0xC000003E, "aarch64": 0xC00000B7}
    machine = platform.machine()
    if machine not in numbers:
        raise RuntimeError("unsupported seccomp architecture")
    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]
    # seccomp_data.arch at offset4; nr at offset0. Kill wrong ABI, including x32.
    rules = [(0x20, 0, 0, 4), (0x15, 1, 0, arches[machine]), (0x06, 0, 0, 0x80000000),
             (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x80000000)]
    for number in numbers[machine]:
        rules += [(0x15, 0, 1, number), (0x06, 0, 0, 0x00050000 | errno.EPERM)]
    rules += [(0x06, 0, 0, 0x7FFF0000)]
    array = (Filter * len(rules))(*(Filter(*rule) for rule in rules))
    program = Program(len(rules), array)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "no-new-privileges/seccomp unavailable")


def main():
    if len(sys.argv) != 4 or os.geteuid() != 0:
        raise RuntimeError("root bootstrap and exact jail/UID/CPU arguments required")
    jail, uid, cpu = Path(sys.argv[1]).resolve(), int(sys.argv[2]), int(sys.argv[3])
    if uid not in (10001, 10002, 10003):
        raise ValueError("actor UID")
    os.chdir(jail)
    os.chroot(jail)
    os.chdir("/tmp")
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    os.sched_setaffinity(0, {cpu})
    os.umask(0o077)
    os.environ.clear()
    os.environ.update(PATH="/usr/local/bin", HOME="/tmp", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    sys.argv = ["/driver/controller_driver.py"]
    sys.orig_argv = list(sys.argv)
    del jail, cpu
    sys.path[:] = ["/driver", "/usr/local/lib/python3.12", "/usr/local/lib/python3.12/lib-dynload"]
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    restrict_syscalls()
    runpy.run_path("/driver/controller_driver.py", run_name="__main__")


if __name__ == "__main__":
    main()
