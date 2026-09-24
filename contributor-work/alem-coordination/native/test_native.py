"""Offline deployment invariants; actual kernel enforcement uses probe.py."""
import ast
from pathlib import Path
import unittest
import tempfile
import sys
import importlib.util
import os
import py_compile
import shutil
import subprocess
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import source_inventory, native_worker_error, engine_command, _support

ROOT = Path(__file__).resolve().parent

class NativeTests(unittest.TestCase):
    def test_source_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'directory').mkdir()
            (root/'alias').symlink_to(root/'directory', target_is_directory=True)
            with self.assertRaises(ValueError):
                source_inventory(root)

    def test_source_inventory_omits_only_git_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'module.py').write_text('x=1')
            (root/'.git').mkdir()
            (root/'.git/HEAD').write_text('metadata')
            self.assertEqual(source_inventory(root), {'module.py'})

    def test_engine_is_exact_scientific_copy(self):
        original = (ROOT.parent/'controller/engine.py').read_text()
        port = (ROOT/'engine.py').read_text()
        port = port.replace(";parser.add_argument('--proof-first-world',action='store_true')", "")
        port = port.replace("        if args.proof_first_world: worlds=worlds[:1]\n", "")
        port = port.replace("        # engine_entry stages verified source in a fresh private import root.\n",
                            "        shutil.copytree('/app/alem','/tmp/alem')\n        sys.path[:0]=['/tmp','/app/baselines']\n")
        self.assertEqual(port, original)

    def test_task_loader_ignores_extra_shadow_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            native, controller = task/'native', task/'controller'
            native.mkdir(); controller.mkdir()
            for name in ('wire', 'feedback', 'launcher'):
                (controller/(name+'.py')).write_text('origin="verified"\n')
            (controller/'sandbox.py').write_text('raise AssertionError("unchecked shadow executed")\n')
            (native/'sandbox.py').write_text('origin="native"\n')
            previous = {n:sys.modules.get(n) for n in ('wire','feedback','launcher','alem_native_sandbox')}
            try:
                modules = _support.task_modules(native)
                self.assertEqual([m.origin for m in modules], ['verified','verified','verified','native'])
            finally:
                for name, module in previous.items():
                    if module is None: sys.modules.pop(name, None)
                    else: sys.modules[name] = module

    def test_task_loader_compiles_source_not_timestamp_valid_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'checked.py'
            # Same byte length and timestamp: normal SourceFileLoader accepts
            # the stale cache, whereas our exact-source loader must not.
            path.write_text('origin="injected"\n')
            timestamp = path.stat().st_mtime
            py_compile.compile(str(path), doraise=True)
            path.write_text('origin="verified"\n')
            os.utime(path, (timestamp,timestamp))
            ordinary = importlib.util.spec_from_file_location('ordinary_cache_probe',path)
            ordinary_module = importlib.util.module_from_spec(ordinary)
            ordinary.loader.exec_module(ordinary_module)
            self.assertEqual(ordinary_module.origin,'injected')
            try:
                self.assertEqual(_support.load_file('exact_cache_probe',path).origin,'verified')
            finally:
                sys.modules.pop('exact_cache_probe',None)

    def test_private_source_staging_ignores_shared_tmp_and_cleans_repeat_runs(self):
        from importlib.machinery import PathFinder
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, shared = base/'source', base/'scratch'
            (source/'alem').mkdir(parents=True); (source/'baselines').mkdir()
            (source/'alem/__init__.py').write_text('origin="verified"\n')
            (source/'baselines/utils.py').write_text('origin="verified"\n')
            shared.mkdir()
            (shared/'utils.py').write_text('raise AssertionError("shared scratch imported")\n')
            (shared/'alem').mkdir()  # Pre-existing fixed destination is harmless.
            saved = list(sys.path)
            roots = []
            try:
                sys.path.insert(0,str(shared))
                for _ in range(2):
                    before = list(sys.path)
                    with _support.engine_source(source, parent=shared) as staged:
                        roots.append(staged)
                        self.assertEqual(PathFinder.find_spec('utils',sys.path).origin,str(staged/'baselines/utils.py'))
                        self.assertEqual(PathFinder.find_spec('alem',sys.path).origin,str(staged/'alem/__init__.py'))
                        self.assertEqual(staged.stat().st_mode & 0o777,0o700)
                    self.assertFalse(staged.exists())
                    self.assertEqual(sys.path,before)
                self.assertNotEqual(roots[0],roots[1])
                self.assertTrue((shared/'alem').is_dir())
            finally:
                sys.path[:] = saved

    def test_observed_post_ready_exit_is_candidate_invalid(self):
        worker = SimpleNamespace(candidate_ready=True,proc=SimpleNamespace(poll=lambda:17))
        for exc in (EOFError(), BrokenPipeError()):
            self.assertEqual(native_worker_error(exc,worker),
                             {'status':'candidate_invalid','code':'candidate_act','error_type':'CandidateError'})

    def test_startup_unknown_exit_and_timeout_stay_infrastructure(self):
        for ready, code, exc in ((False,17,EOFError()),(True,None,EOFError()),(True,17,TimeoutError()),(True,17,OSError())):
            worker = SimpleNamespace(candidate_ready=ready,proc=SimpleNamespace(poll=lambda:code))
            self.assertEqual(native_worker_error(exc,worker)['status'],'infrastructure_or_incomplete')

    def test_isolated_supervisor_ignores_unlisted_stdlib_shadow_and_requires_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            native, controller = task/'native',task/'controller'
            native.mkdir();controller.mkdir()
            for name in ('run.py','runtime_support.py','sandbox.py'):
                shutil.copyfile(ROOT/name,native/name)
            for name in ('wire.py','feedback.py','launcher.py'):
                shutil.copyfile(ROOT.parent/'controller'/name,controller/name)
            (native/'json.py').write_text('raise AssertionError("unchecked native json shadow executed")\n')
            command = [str(native/'run.py'),'--help']
            good = subprocess.run([sys.executable,'-I','-B']+command,capture_output=True,text=True,timeout=10)
            self.assertEqual(good.returncode,0,good.stderr)
            bad = subprocess.run([sys.executable,'-B']+command,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('requires python -I -B',bad.stderr)
            self.assertNotIn('shadow executed',bad.stderr)

    @unittest.skipIf(sys.version_info < (3,11), 'safe-path child startup requires Python3.11+')
    def test_engine_startup_has_fixed_hashseed_and_ignores_pythonpath(self):
        command = engine_command('dev')
        entry = command.index(str(ROOT/'engine_entry.py'))
        code = ('import json,sys; print(json.dumps([sys.flags.safe_path,sys.flags.no_user_site,'
                'sys.flags.hash_randomization,hash("alem-native-fixed-text"),sys.path]))')
        command = command[:entry]+['-c',code]
        inherited = dict(os.environ,PYTHONPATH='/unchecked-work-shadow',PYTHONHASHSEED='123')
        import json
        first = json.loads(subprocess.check_output(command,env=inherited,text=True,timeout=10))
        second = json.loads(subprocess.check_output(command,env=inherited,text=True,timeout=10))
        self.assertEqual(first,second)
        self.assertEqual(first[:3],[True,1,0])
        self.assertNotIn('/unchecked-work-shadow',first[4])
        expected = int(subprocess.check_output(
            ['/usr/bin/env','-i','PYTHONHASHSEED=0',sys.executable,'-c',
             'print(hash("alem-native-fixed-text"))'],text=True,timeout=10))
        self.assertEqual(first[3],expected)

    def test_both_architectures_deny_required_channels(self):
        tree = ast.parse((ROOT/'actor_bootstrap.py').read_text())
        assignment = next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='numbers' for t in n.targets))
        values = ast.literal_eval(assignment.value)
        for arch, required in {'x86_64':{41,53,56,57,58,59,203,*range(240,246),29,30,31,310,311}, 'aarch64':{198,199,220,221,122,*range(180,198),270,271}}.items():
            self.assertTrue(required <= set(values[arch]))

    def test_actor_paths_do_not_encode_world_identifier(self):
        text = (ROOT/'run.py').read_text()
        self.assertIn('world_root = temporary_root / "actors"', text)
        self.assertNotIn('world_root = temporary_root / ("world-"', text)

    def test_native_entrypoints_have_no_docker_execution(self):
        for name in ('run.py','sandbox.py','actor_bootstrap.py','engine_entry.py'):
            tree = ast.parse((ROOT/name).read_text())
            strings = [n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
            self.assertNotIn('docker',strings)
            self.assertNotIn('/var/run/docker.sock',strings)

if __name__=='__main__': unittest.main()
