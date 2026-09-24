"""Summarize saved native results without loading a model or generating data."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def summarize(result, wall_seconds=None):
    if result['status'] != 'completed' or len(result['evaluation_batches']) != 1:
        raise ValueError('only a completed single native20 batch can be summarized')
    config = result['config']
    if (config['TEST_NUM_EPISODES'], config['TEST_MAX_STEPS'], config['EVAL_SEED'],
        config['SCALE_BASE_DIFFICULTY'], config['EVAL_DIFFICULTIES']) != (20, 10000, 9999, False, ['hard']):
        raise ValueError('configuration differs from declared native20 baseline')
    batch = result['evaluation_batches'][0]
    rows = batch['native_per_episode']
    if len(rows) != 20 or [r['seed'] for r in rows] != list(range(20)):
        raise ValueError('native20 must retain every ordered episode')
    metrics = {'coordination': 'Team/coord_reward_pct_of_max', 'base': 'Team/normal_reward_pct_of_max',
               'total': 'Team/reward_pct_of_max'}
    summary = {
        'scope': 'Fresh v0.2.1 Hard20 baseline; one training seed; base scaling false; no historical replication.',
        'world_seeds': list(range(9999, 10019)), 'episode_count': len(rows),
        'natural_terminations': sum(bool(r['done']) for r in rows),
        'all_agents_dead_episodes': sum(r['Deaths/total_deaths'] == 3 for r in rows),
        'environment_transitions': batch['environment_transitions'],
        'evaluation_seconds_including_jit': batch['seconds_including_jit'],
        'evaluation_transitions_per_second_including_jit': batch['transitions_per_second_including_jit'],
        'total_python_seconds': result['total_seconds_including_import_restore_and_jit'],
        'docker_wall_seconds': wall_seconds,
        'peak_process_rss_kib_linux': result['peak_process_rss_kib_linux'],
        'effective_config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'reward_normalized_percent': {}, 'per_world': [],
    }
    for label, metric in metrics.items():
        values = [r[metric] * 100 for r in rows]
        summary['reward_normalized_percent'][label] = {
            'mean': statistics.mean(values), 'sample_sd': statistics.stdev(values),
            'sample_se': statistics.stdev(values) / len(values)**0.5,
            'min': min(values), 'max': max(values),
        }
    for row in rows:
        summary['per_world'].append({'world_seed': 9999 + row['seed'],
                                    'transitions': int(row['mean_episode_length']) + 1,
                                    'naturally_terminated': bool(row['done']),
                                    'total_deaths': row['Deaths/total_deaths'],
                                    **{label + '_reward_percent': row[key] * 100 for label, key in metrics.items()}})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--launch', type=Path)
    args = parser.parse_args()
    launch = json.loads(args.launch.read_text()) if args.launch else {}
    print(json.dumps(summarize(json.loads(args.result.read_text()), launch.get('wall_seconds')), indent=2))
