"""Plot all frozen-workload outcomes; never treat an unscored run as zero.

Usage: python plot_alem_pilot.py --baseline evaluation-baseline.json
  --results RESULTS_DIRECTORY --output OUTPUT_PREFIX
Requires matplotlib==3.10.3. Model output is read only as JSON data.
"""
import argparse
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

PRIMARY = 'Team/coord_reward_pct_of_max'


def read(path):
    return json.loads(path.read_text())


def scores(record):
    if record.get('status') != 'scored' or record.get('provenance_verified') is not True:
        return None
    rows = record['worlds']
    assert len(rows) == 20 and all(r['status'] == 'scored' for r in rows)
    assert [r['world_id'] for r in rows] == list(range(9999, 10019))
    values = [100 * r['reward_fraction'][PRIMARY] for r in rows]
    assert all(0 <= x <= 100 for x in values)
    assert abs(statistics.mean(values) - 100 * record['primary_score_fraction']) < 1e-8
    return values


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    ref = scores(read(args.baseline))
    assert ref is not None
    specs = [('Pass-through', None, '#62666c'),
             ('Scripted sync', 'visible-sync-001', '#d98913'),
             ('GPT-6 Astra', 'astra-001', '#0072b2'),
             ('GPT-6 Sol', 'sol-001', '#009e73')]
    series = []
    for name, folder, color in specs:
        if folder is None:
            value = ref
        else:
            assert (args.results / folder / 'summary.json').is_file(), 'Wait for the completed export'
            evaluation = args.results / folder / 'final-evaluation.json'
            value = scores(read(evaluation)) if evaluation.is_file() else None
        series.append((name, value, color))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#272b31', 'text.color': '#272b31',
                         'xtick.color': '#424750', 'ytick.color': '#424750',
                         'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.9), gridspec_kw={'width_ratios': [1.15, 1]})
    fig.subplots_adjust(left=.075, right=.98, top=.76, bottom=.26, wspace=.29)
    fig.text(.075, .935, 'Alem coordination research pilot', size=19, weight='bold')
    fig.text(.075, .88, 'Final artifacts on the same 20 fixed worlds · 3 coding calls per model · 1 trajectory per model', size=10)
    fig.text(.075, .835, 'Each dot is one world; horizontal bars show the mean. World variation is not run-to-run uncertainty.', size=9, color='#62666c')
    ax = axes[0]
    for index, (label, values, color) in enumerate(series):
        if values is None:
            ax.text(index, 45, 'Unscored', ha='center', color=color)
            continue
        jitter = [((i * 7) % 20 - 9.5) / 62 for i in range(20)]
        ax.scatter([index + j for j in jitter], values, color=color, s=22, alpha=.66, linewidth=0)
        mean = statistics.mean(values)
        ax.plot([index-.24, index+.24], [mean, mean], color=color, lw=3.5, solid_capstyle='butt')
        ax.text(index, max(values)+5, f'{mean:.2f}%', ha='center', weight='bold', color=color, size=10)
    ax.set(ylim=(0, 100), xlim=(-.6, 3.6), ylabel='Normalized coordination reward (%)',
           xticks=range(4), xticklabels=[s[0] for s in series], title='Final coordination reward')
    ax.tick_params(axis='x', labelsize=9)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.grid(axis='y', color='#e4e7eb', linewidth=.7)
    ax.set_axisbelow(True)
    ax = axes[1]
    max_delta = 5.
    for index, (label, values, color) in enumerate(series[1:]):
        if values is None:
            ax.text(index, 0, 'Unscored', ha='center', color=color)
            continue
        delta = [x-y for x, y in zip(values, ref)]
        max_delta = max(max_delta, max(abs(x) for x in delta) * 1.2)
        jitter = [((i * 7) % 20 - 9.5) / 62 for i in range(20)]
        ax.scatter([index+j for j in jitter], delta, color=color, s=23, alpha=.65, linewidth=0)
        mean = statistics.mean(delta)
        ax.plot([index-.24, index+.24], [mean, mean], color=color, lw=3.5, solid_capstyle='butt')
        ax.text(index, 1.01, f'Mean {mean:+.2f} pp', transform=ax.get_xaxis_transform(),
                ha='center', color=color, size=9, weight='bold')
    ax.axhline(0, color='#414750', lw=.9, linestyle='--')
    ax.set(ylim=(-max_delta, max_delta), xlim=(-.6, 2.6),
           ylabel='Change versus pass-through (percentage points)',
           xticks=range(3), xticklabels=[s[0] for s in series[1:]])
    ax.tick_params(axis='x', labelsize=9)
    ax.grid(axis='y', color='#e4e7eb', linewidth=.7)
    ax.set_axisbelow(True)
    fig.text(.075, .155, 'Scope: code-writing researchers improve a frozen three-agent RL team; these are not conversational-agent game scores.', size=9)
    fig.text(.075, .115, 'Reward is not a pass rate. Public fixed worlds, one checkpoint and short tool-free pilots do not establish broad model rankings.', size=9)
    fig.text(.075, .075, 'The scripted control is a construction-time heuristic, not a research-model result. Invalid or incomplete runs remain unscored.', size=9)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for ext in ('svg', 'png', 'pdf'):
        target = args.output.with_suffix('.'+ext)
        if target.exists():
            raise FileExistsError(target)
        metadata = {'Date': None} if ext == 'svg' else {}
        fig.savefig(target, dpi=180, facecolor='white', metadata=metadata)
    plt.close(fig)


if __name__ == '__main__':
    main()
