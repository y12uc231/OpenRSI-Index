import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common
import replay
import summarize


class PackageTests(unittest.TestCase):
    def test_native_evidence_is_byte_exact(self):
        provenance = common.read_json(ROOT / 'evidence/provenance.json')
        self.assertEqual(common.sha256(ROOT / 'evidence/native20.json'), provenance['original_result_sha256'])
        self.assertEqual(common.sha256(ROOT / 'evidence/summary.json'), provenance['original_summary_sha256'])
        self.assertEqual(common.sha256(ROOT / 'native20.py'), provenance['harness_sha256'])

    def test_summary_preserves_all_worlds_and_scores(self):
        result = common.read_json(ROOT / 'evidence/native20.json')
        observed = summarize.summarize(result)
        original = common.read_json(ROOT / 'evidence/summary.json')
        self.assertEqual(observed['reward_normalized_percent'], original['reward_normalized_percent'])
        self.assertEqual(observed['world_seeds'], list(range(9999, 10019)))
        self.assertEqual(observed['environment_transitions'], 9428)
        self.assertEqual(observed['natural_terminations'], 20)
        self.assertEqual(observed['all_agents_dead_episodes'], 20)
        self.assertEqual(observed['effective_config_sha256'], original['effective_config_sha256'])
        result['evaluation_batches'][0]['native_per_episode'].pop()
        with self.assertRaises(ValueError):
            summarize.summarize(result)

    def test_manifest_checks_multiplicity_sizes_and_digests(self):
        assets = common.read_json(ROOT / 'asset-manifest.json')
        self.assertEqual(len(assets['files']), 20)
        self.assertEqual(len({x['path'] for x in assets['files']}), 20)
        self.assertEqual(sum(x['bytes'] for x in assets['files']), 224560898)
        for row in assets['files']:
            self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$')
            if row['hub_lfs_sha256']:
                self.assertEqual(row['sha256'], row['hub_lfs_sha256'])

    def test_paths_cannot_escape_via_parent_or_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'link').symlink_to(root.parent, target_is_directory=True)
            for bad in ('../secret', '/absolute', 'link/secret'):
                with self.assertRaises(ValueError):
                    common.checked_path(root, bad)
            self.assertEqual(common.checked_path(root, 'assets/example'), root.resolve() / 'assets/example')

    def test_no_network_fixed_limits_and_readonly_inputs(self):
        args = replay.command(Path('/work'), Path('/output'), 'sha256:example', 'test')
        for option, value in [('--network', 'none'), ('--cpus', '4'), ('--memory', '6g'),
                              ('--pids-limit', '256'), ('--cap-drop', 'ALL')]:
            self.assertEqual(args[args.index(option) + 1], value)
        mounts = [args[i + 1] for i, arg in enumerate(args) if arg == '--mount']
        self.assertEqual(len(mounts), 4)
        self.assertEqual(sum(x.endswith(',readonly') for x in mounts), 3)
        self.assertEqual(args[-4:], ['--episodes', '20', '--steps', '10000'])

    def test_public_artifacts_have_no_local_paths_or_raw_logs(self):
        for path in ROOT.rglob('*'):
            if not path.is_file() or '.work' in path.parts or '__pycache__' in path.parts:
                continue
            self.assertLess(path.stat().st_size, 2 * 1024 * 1024)
            if path.suffix in ('.json', '.md', '.lock'):
                text = path.read_text()
                self.assertNotIn('/Users/', text)
                self.assertNotIn('/home/', text)
                self.assertNotIn('sk-proj-', text)
            self.assertNotIn(path.name, ('stdout.txt', 'stderr.txt', 'events.jsonl'))


if __name__ == '__main__':
    unittest.main()
