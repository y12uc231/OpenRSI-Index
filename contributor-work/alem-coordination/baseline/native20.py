"""Trusted instrumentation around the unchanged official eval-only entry point.

Run only in the no-network container. No training, action edits, or env edits.
"""
import argparse
import importlib.metadata
import json
import pathlib
import resource
import shutil
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=int, default=20)
    parser.add_argument('--steps', type=int, default=10000)
    parser.add_argument('--output', default='/results/result.json')
    args = parser.parse_args()
    if args.episodes != 20 or args.steps != 10000:
        raise ValueError('Frozen baseline requires20 worlds and native10000step ceiling')
    started = time.monotonic()
    # Alem creates a texture cache next to its assets on import, even for the
    # symbolic environment. Copy the unchanged package into container-only tmp.
    shutil.copytree('/app/alem', '/tmp/alem')
    sys.path.insert(0, '/tmp')
    sys.path.insert(0, '/app/baselines')
    import jax
    import yaml
    import utils
    import ippo_hypermarl_rnn as trainer

    checkpoint = '/assets/1B/hypermarl-rnn/hard/seed0/checkpoint'
    with open('/app/baselines/config/hypermarl_rnn.yaml') as handle:
        config = yaml.safe_load(handle)
    with open('/assets/1B/hypermarl-rnn/hard/seed0/config.json') as handle:
        release = json.load(handle)
    config.update(release['reload_overrides'])
    config.update({
        'LOAD_CHECKPOINT': checkpoint,
        'TRAINING_COORDINATION_DIFFICULTY': 'hard',
        'SCALE_BASE_DIFFICULTY': False,
        'EVAL_DIFFICULTIES': ['hard'],
        'TEST_NUM_EPISODES': args.episodes,
        'TEST_MAX_STEPS': args.steps,
        'EVAL_SEED': 9999,
        'VISUALIZE': False,
        'WANDB_MODE': 'disabled',
        'RUN_TAGS': [],
        'SEED': 0,
    })
    # Fail before any entry point if fixed network-shape config differs.
    shape_keys = ['APPEND_AGENT_ID', 'GRU_HIDDEN_DIM', 'FC_DIM_SIZE',
                  'ACTIVATION', 'HYPERNET_EMBEDDING_DIM', 'HYPERNET_HIDDEN_DIMS',
                  'HYPERNET_INIT_SCALE', 'USE_AGENT_ID_EMBEDDINGS',
                  'USE_BIAS_IN_HYPERNET', 'ACTION_MASKING', 'NUM_COMM_CHANNELS']
    for key in shape_keys:
        if config[key] != release['training_config'][key]:
            raise ValueError('Released shape/config mismatch: ' + key)
    results = {'status': 'running', 'scope': 'fresh20world Hard baseline, currentv0.2.1 config, one training seed, not historical replication',
               'source_sha': '14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e',
               'asset_revision': '9493179ea5e86cd625add66c0f88e23f04f928b5',
               'checkpoint': '1B/hypermarl-rnn/hard/seed0',
               'config': config, 'devices': [str(x) for x in jax.devices()],
               'versions': {p: importlib.metadata.version(p) for p in
                            ['alem-env', 'jax', 'jaxlib', 'flax', 'orbax-checkpoint', 'jaxmarl', 'numpy']},
               'evaluation_batches': []}
    original_sequential = utils._run_eval_sequential

    def observed_sequential(*pos, **kw):
        begin = time.monotonic()
        value = original_sequential(*pos, **kw)
        elapsed = time.monotonic() - begin
        aggregate, per_episode, _ = value
        # Official code logs zero-based last step as mean_episode_length.
        transitions = sum(int(row['mean_episode_length']) + 1 for row in per_episode)
        results['evaluation_batches'].append({
            'seconds_including_jit': elapsed, 'environment_transitions': transitions,
            'transitions_per_second_including_jit': transitions / elapsed,
            'native_aggregate': aggregate, 'native_per_episode': per_episode,
        })
        return value

    utils._run_eval_sequential = observed_sequential
    output = pathlib.Path(args.output)
    try:
        trainer.single_run(config)
        results['status'] = 'completed'
    except Exception as error:
        results['status'] = 'error'
        results['error_type'] = type(error).__name__
        results['error_message'] = str(error)
        raise
    finally:
        results['total_seconds_including_import_restore_and_jit'] = time.monotonic() - started
        results['peak_process_rss_kib_linux'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        output.write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
