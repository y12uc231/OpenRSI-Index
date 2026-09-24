"""Offline deployment invariants; actual kernel enforcement uses probe.py."""
import ast
from pathlib import Path
import unittest
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import source_inventory

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
        self.assertEqual(port, original)

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
