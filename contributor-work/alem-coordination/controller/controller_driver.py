"""Container-only candidate driver. The evaluator never imports candidate code."""
import base64
import contextlib
import importlib.util
import json
import math
import os
import random
import resource
import struct
import sys

from wire import read, write

MAX_MEMORY = 65536


def vector(value, kind):
    if not isinstance(value, dict) or set(value) != {"dtype", "data", "size"} or value["dtype"] != kind:
        raise ValueError("array schema")
    size = value["size"]
    if type(size) is not int or not 0 <= size <= 100000:
        raise ValueError("array size")
    raw = base64.b64decode(value["data"], validate=True)
    width = 4 if kind == "f4" else 1
    if len(raw) != size * width:
        raise ValueError("array length")
    if kind == "f4":
        values = list(struct.unpack("<" + "f" * size, raw))
        if not all(math.isfinite(x) for x in values):
            raise ValueError("nonfinite array")
        return values
    if any(x not in (0, 1) for x in raw):
        raise ValueError("nonboolean mask")
    return [bool(x) for x in raw]


def bounded_memory(memory):
    raw = json.dumps(memory, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_MEMORY:
        raise ValueError("declared memory exceeds 64KiB")
    return json.loads(raw)


def candidate_response(response, legal_mask):
    if not isinstance(response, dict) or set(response) != {"action", "memory"}:
        raise ValueError("result schema")
    action = response["action"]
    if type(action) is not int or not 0 <= action < len(legal_mask) or not legal_mask[action]:
        raise ValueError("invalid action")
    return action, bounded_memory(response["memory"])


def main():
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    # Save protocol separately and silence candidate stdout, including os.write(1).
    channel = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    with open(os.devnull, "w") as silent:
        os.dup2(silent.fileno(), sys.stdout.fileno())
        with contextlib.redirect_stdout(silent):
            try:
                init = read(sys.stdin.buffer)
                if not isinstance(init, dict) or set(init) != {"kind", "agent_id", "schema"} or init["kind"] != "initialize" or type(init["agent_id"]) is not int or init["agent_id"] not in range(3):
                    raise ValueError("invalid trusted initialization")
            except Exception as exc:
                write(channel, {"error": {"status": "infrastructure_or_incomplete", "code": "worker_input", "error_type": type(exc).__name__}})
                return
            # Same fixed seed in every actor and world. Using clocks/OS entropy
            # is prohibited scientifically; this is not claimed to block it.
            random.seed(0)
            phase = "candidate_import"
            try:
                spec = importlib.util.spec_from_file_location("controller", "/candidate/controller.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules["controller"] = module
                spec.loader.exec_module(module)
                phase = "candidate_initialize"
                memory = bounded_memory(module.initialize(init["agent_id"], init["schema"]))
                write(channel, {"ready": True})
                while True:
                    phase = "worker_input"
                    request = read(sys.stdin.buffer)
                    if request is None:
                        return
                    if not isinstance(request, dict) or set(request) != {"kind", "local"} or request["kind"] != "act":
                        raise ValueError("invalid trusted request")
                    local = request["local"]
                    if not isinstance(local, dict) or set(local) != {"observation", "legal_mask", "frozen_logits", "proposal", "previous_reward", "step"}:
                        raise ValueError("local schema")
                    local = dict(local, observation=vector(local["observation"], "f4"), legal_mask=vector(local["legal_mask"], "u1"), frozen_logits=vector(local["frozen_logits"], "f4"))
                    phase = "candidate_act"
                    response = module.act(local, memory)
                    phase = "candidate_output"
                    action, memory = candidate_response(response, local["legal_mask"])
                    write(channel, {"action": action})
            except BaseException as exc:
                status = "infrastructure_or_incomplete" if phase == "worker_input" else "candidate_invalid"
                # Exception text is private operator diagnostics, bounded here
                # and again in the host stderr drain. Never public feedback.
                print((phase + ": " + type(exc).__name__ + ": " + str(exc))[:8192], file=sys.stderr)
                write(channel, {"error": {"status": status, "code": phase, "error_type": type(exc).__name__[:80]}})


if __name__ == "__main__":
    main()
