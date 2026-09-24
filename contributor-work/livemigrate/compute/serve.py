"""Launch the pinned text-only inference profile on an operator-supplied GPU.

This script does not download weights or provision hardware. The weights path
must be a materialized copy of the complete Hugging Face snapshot at the
profile's exact revision. Cache symlinks cannot resolve outside its Docker mount.
"""
import argparse
import json
from pathlib import Path
import subprocess


def materialized_weights(weights, profile):
    """Check mount completeness, not provenance: content hashes remain external."""
    supplied = Path(weights)
    if supplied.is_symlink():
        raise ValueError('weights directory must be materialized, not a symlink')
    weights = supplied.resolve()
    if weights.name != profile['model_revision'] or not weights.is_dir():
        raise ValueError('pass a materialized snapshot directory named for the exact model revision')
    for path in weights.rglob('*'):
        if path.is_symlink():
            raise ValueError('materialize snapshot symlinks before launch: ' + str(path.relative_to(weights)))
        if not path.is_dir() and not path.is_file():
            raise ValueError('snapshot contains a non-regular entry: ' + str(path.relative_to(weights)))
    for name in ('config.json', 'tokenizer_config.json', 'tokenizer.json', 'model.safetensors.index.json'):
        path = weights / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('materialized snapshot requires nonempty ' + name)
    index = json.loads((weights / 'model.safetensors.index.json').read_text())
    weight_map = index.get('weight_map')
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError('weight index requires a nonempty weight_map')
    for name in weight_map.values():
        if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('weight index contains an invalid shard path')
        path = weights / name
        if path.suffix != '.safetensors' or not path.is_file() or path.stat().st_size == 0:
            raise ValueError('missing or empty materialized weight shard: ' + name)
    return weights


def command(weights, profile):
    weights = materialized_weights(weights, profile)
    return ['docker', 'run', '--rm', '--pull=never', '--gpus', 'device=0',
            '--shm-size', '8g', '--publish', '127.0.0.1:8000:8000',
            '--mount', 'type=bind,src=' + str(weights) + ',dst=/model,readonly',
            '--env', 'HF_HUB_OFFLINE=1', '--env', 'TRANSFORMERS_OFFLINE=1',
            profile['vllm_image'], '--model', '/model',
            '--served-model-name', profile['served_model_name'],
            '--dtype', profile['dtype'], '--tensor-parallel-size', '1',
            '--max-model-len', str(profile['max_model_len']),
            '--max-num-seqs', '3', '--gpu-memory-utilization', '0.90',
            '--language-model-only', '--reasoning-parser', 'qwen3',
            '--host', '0.0.0.0', '--port', '8000']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('weights', type=Path)
    parser.add_argument('--print-only', action='store_true')
    args = parser.parse_args()
    profile = json.loads(Path(__file__).with_name('qwen38.json').read_text())
    argv = command(args.weights, profile)
    if args.print_only:
        print(json.dumps(argv, indent=2))
    else:
        from verify_assets import verify
        manifest = json.loads(Path(__file__).with_name('qwen38-assets.json').read_text())
        if manifest['revision'] != profile['model_revision'] or manifest['model_id'] != profile['model_id']:
            raise ValueError('asset manifest and model profile disagree')
        print(json.dumps(verify(args.weights, manifest)), flush=True)
        raise SystemExit(subprocess.call(argv))
