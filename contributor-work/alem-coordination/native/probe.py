"""Trusted native sandbox probes only; no model execution or downloads."""
import base64
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "controller"))
from launcher import FrameProcess
from sandbox import actor_root, copy_runtime

PROBE = '''import os, socket, random, subprocess, ctypes, errno, platform, sys
counter = 0
def initialize(agent_id, schema):
    assert os.geteuid() == 10001 + agent_id
    assert len(os.sched_getaffinity(0)) == 1
    try: os.sched_setaffinity(0, os.sched_getaffinity(0))
    except PermissionError: pass
    else: raise AssertionError('affinity mutable')
    frame = sys._getframe().f_back
    while frame:
        for key, value in list(frame.f_locals.items()):
            if key in ('world_id','current_world'): raise AssertionError('world identifier in frame')
            if key == 'jail': assert 'world-' not in str(value)
        frame = frame.f_back
    assert not any(os.path.exists(p) for p in ['/proc','/app','/assets','/results','/task'])
    assert os.path.getsize('/tmp/scratch') == 0
    try: open('/tmp/new-file','w')
    except PermissionError: pass
    else: raise AssertionError('scratch directory writable')
    with open('/tmp/scratch','r+b') as h:
        try: h.truncate(16*1024*1024+1)
        except OSError as error: assert error.errno == errno.EFBIG
        else: raise AssertionError('scratch exceeds16MiB')
    assert random.random() == 0.8444218515250481
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try: socket.socket(family)
        except PermissionError: pass
        else: raise AssertionError('socket allowed')
    libc = ctypes.CDLL(None, use_errno=True)
    for number in ((240,29) if platform.machine() == 'x86_64' else (180,194)):
        assert libc.syscall(number, b'alem_probe', 0, 0, 0) == -1
        assert ctypes.get_errno() == errno.EPERM
    try: os.fork()
    except PermissionError: pass
    except BlockingIOError: pass
    else: raise AssertionError('fork allowed')
    try: os.execve('/missing-executable', ['/missing-executable'], {})
    except PermissionError: pass
    else: raise AssertionError('exec not blocked by seccomp')
    try: open('/candidate/controller.py','a')
    except PermissionError: pass
    else: raise AssertionError('candidate writable')
    with open('/tmp/scratch','w') as h: h.write(str(agent_id))
    return {'n':0,'id':agent_id}
def act(local, memory):
    global counter
    assert memory['n'] == counter
    assert int(open('/tmp/scratch').read()) == memory['id']
    counter += 1
    return {'action': 0, 'memory': {'n':counter,'id':memory['id']}}
'''


def main():
    os.environ["PYTHONHASHSEED"] = "0"
    with tempfile.TemporaryDirectory(prefix="alem-native-probe-", dir="/var/lib") as temporary:
        root = Path(temporary)
        source = root / "candidate"
        source.mkdir()
        (source / "controller.py").write_text(PROBE)
        template = root / "template"
        copy_runtime(template)
        workers = []
        try:
            for index, actor in enumerate((0, 1, 2, 0)):
                command = actor_root(template, root / ("actor-" + str(index)), source, actor)
                worker = FrameProcess(command, root / ("stderr-" + str(index)))
                workers.append(worker)
                worker.send({"kind": "initialize", "agent_id": actor, "schema": {}})
                try:
                    response = worker.recv()
                except Exception:
                    print((root / ("stderr-" + str(index))).read_text()[:8192], file=sys.stderr)
                    raise
                if response != {"ready": True}:
                    raise AssertionError((response, (root / ("stderr-" + str(index))).read_text()))
                packet = {"observation": {"dtype":"f4","size":1,"data":base64.b64encode(struct.pack('<f',0)).decode()},
                          "frozen_logits": {"dtype":"f4","size":1,"data":base64.b64encode(struct.pack('<f',0)).decode()},
                          "legal_mask":{"dtype":"u1","size":1,"data":"AQ=="},"proposal":0,"previous_reward":0,"step":0}
                for step in range(2):
                    worker.send({"kind": "act", "local": packet | {"step": step}})
                    assert worker.recv() == {"action": 0}
        finally:
            for worker in workers:
                worker.close()
        print(json.dumps({"status":"passed","fresh_actor_processes":4,"callbacks":8,"network_families_denied":["INET","INET6","UNIX"],"fork_exec_denied":True,"posix_sysv_ipc_denied":True,"affinity_change_denied":True,"no_world_id_in_frames":True,"private_chroot_and_tmp":True,"single_scratch_file_limit_bytes":16777216,"llm_calls":0,"policy_forward_calls":0,"python":sys.version.split()[0]}))


if __name__ == "__main__":
    main()
