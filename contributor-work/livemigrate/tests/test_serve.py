"""Launcher validation uses tiny local fixtures; no Docker or model downloads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('livemigrate_serve_test', CORE / 'compute' / 'serve.py')
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)
PROFILE = json.loads((CORE / 'compute' / 'qwen38.json').read_text())


class SnapshotTests(unittest.TestCase):
    def snapshot(self, parent):
        root = parent / PROFILE['model_revision']
        root.mkdir()
        for name in ('config.json', 'tokenizer_config.json', 'tokenizer.json'):
            (root / name).write_text('{}')
        (root / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'a': 'part-1.safetensors', 'b': 'part-2.safetensors'}}))
        for name in ('part-1.safetensors', 'part-2.safetensors'):
            (root / name).write_bytes(b'fixture bytes; not model weights')
        return root

    def test_materialized_snapshot_mounts_readonly_without_implicit_pull(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.snapshot(Path(directory))
            command = serve.command(root, PROFILE)
            self.assertIn('--pull=never', command)
            self.assertEqual(command[command.index('--mount') + 1], 'type=bind,src=' + str(root.resolve()) + ',dst=/model,readonly')
            self.assertEqual(command.count('--mount'), 1)
            self.assertIn('HF_HUB_OFFLINE=1', command)
            self.assertIn('TRANSFORMERS_OFFLINE=1', command)

    def test_cache_blob_symlink_is_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.snapshot(parent)
            blobs = parent / 'blobs'
            blobs.mkdir()
            (blobs / 'hash').write_bytes(b'cached model shard')
            (root / 'part-1.safetensors').unlink()
            (root / 'part-1.safetensors').symlink_to('../blobs/hash')
            self.assertTrue((root / 'part-1.safetensors').is_file())
            with self.assertRaisesRegex(ValueError, 'materialize snapshot symlinks'):
                serve.command(root, PROFILE)

    def test_missing_shard_and_index_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.snapshot(Path(directory))
            (root / 'part-2.safetensors').unlink()
            with self.assertRaisesRegex(ValueError, 'missing or empty'):
                serve.command(root, PROFILE)
            (root / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'a': '../outside.safetensors'}}))
            with self.assertRaisesRegex(ValueError, 'invalid shard path'):
                serve.command(root, PROFILE)

    def test_broken_symlink_and_symlink_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.snapshot(Path(directory))
            link = root / 'unused-config'
            link.symlink_to('../missing')
            with self.assertRaisesRegex(ValueError, 'materialize snapshot symlinks'):
                serve.command(root, PROFILE)
            link.unlink()
            (root / 'linked-assets').symlink_to(root.parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'materialize snapshot symlinks'):
                serve.command(root, PROFILE)


if __name__ == '__main__':
    unittest.main()
