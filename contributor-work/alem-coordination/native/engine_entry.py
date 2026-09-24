"""Trusted native engine entry: same scientific code and normal image CPU affinity."""
import os
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "controller"))
runpy.run_path(str(Path(__file__).with_name("engine.py")), run_name="__main__")
