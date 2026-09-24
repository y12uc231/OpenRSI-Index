import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verify_model_assets_test', ROOT / 'compute/verify_assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class AssetTests(unittest.TestCase):
    def test_exact_blob_and_lfs_hashes_fail_on_same_size_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'revision'
            root.mkdir()
            (root / 'config.json').write_bytes(b'{}')
            (root / 'weight').write_bytes(b'tensor')
            manifest = {'revision': 'revision', 'files': [
                {'path': 'config.json', 'bytes': 2, 'algorithm': 'git-blob-sha1',
                 'digest': hashlib.sha1(b'blob 2\0{}').hexdigest()},
                {'path': 'weight', 'bytes': 6, 'algorithm': 'sha256',
                 'digest': hashlib.sha256(b'tensor').hexdigest()}]}
            self.assertEqual(assets.verify(root, manifest)['verified_files'], 2)
            (root / 'weight').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                assets.verify(root, manifest)
            (root / 'weight').unlink()
            (root / 'weight').symlink_to(root / 'config.json')
            with self.assertRaisesRegex(ValueError, 'regular files'):
                assets.verify(root, manifest)

    def test_manifest_paths_cannot_escape_materialized_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'revision'
            root.mkdir()
            for name in ('../outside', '/absolute', 'folder\\outside'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'manifest path'):
                    assets.verify(root, {'revision': 'revision', 'files': [{'path': name}]})


if __name__ == '__main__':
    unittest.main()
