"""Plot the verified public continuation export with matplotlib; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.results / 'MANIFEST.json').read_text())

    def read(name):
        raw = (args.results / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['files'][name]:
            raise ValueError('Export artifact changed')
        return json.loads(raw)

    summary = read('summary.json')
    comparison = read('comparison.json')
    if summary['status'] != 'completed' or summary['audit_status'] != 'verified':
        raise ValueError('Completed verified results required')
    rows = summary['development']
    navy, teal, orange, gray = '#294b71', '#00836d', '#b65525', '#67717c'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.8),
                             gridspec_kw={'width_ratios': [1.15, 1, 1.15]})
    fig.subplots_adjust(left=.065, right=.975, bottom=.26, top=.74, wspace=.35)
    fig.text(.065, .94, 'Can six more Sol revisions improve the trained team?',
             size=19, weight='bold', color=navy)
    fig.text(.065, .885, 'One warm-started research attempt · six coding calls · fixed network weights', size=11)
    fig.text(.065, .83, 'Controller selected on four development worlds before final testing. Reward percentages are not pass rates.', size=10, color=gray)

    ax = axes[0]
    baseline = rows[0]['primary_score'] * 100
    ax.axhline(baseline, color=gray, linestyle='--', linewidth=1, label='Pass-through')
    values = [r['primary_score'] * 100 if r['status'] == 'scored' else float('nan') for r in rows[1:]]
    ax.plot(range(7), values, color=navy, marker='o', linewidth=1.4, label='Submitted code')
    for i, row in enumerate(rows[1:]):
        if row['status'] != 'scored':
            ax.text(i, .03, 'Invalid', ha='center', va='bottom', rotation=90,
                    transform=ax.get_xaxis_transform(), color=orange, size=8)
    ax.set_xticks(range(7), ['Start', '1', '2', '3', '4', '5', '6'])
    ax.set_ylim(bottom=0)
    ax.set_xlabel('New coding round')
    ax.set_ylabel('Coordination reward (%)')
    ax.set_title('Development: all submissions', loc='left', size=11, pad=12)
    ax.legend(frameon=False, fontsize=8, loc='lower left')
    ax.grid(axis='y', alpha=.2)

    ax = axes[1]
    labels = [('reference', 'Pass-through', gray), ('incumbent', 'Original Sol', navy),
              ('selected', 'Selected', teal)]
    for i, (label, name, color) in enumerate(labels):
        row = next(r for r in summary['final'] if r['suite'] == 'transfer' and r['label'] == label)
        data = read('evaluations/' + row['evaluation'] + '.json')
        if data['status'] != 'scored':
            ax.text(i, .05, 'Unscored', ha='center', rotation=90,
                    transform=ax.get_xaxis_transform(), color=orange)
            continue
        ys = [r['score'] * 100 for r in data['worlds']]
        xs = [i + ((j % 5)-2) * .043 for j in range(len(ys))]
        ax.scatter(xs, ys, color=color, s=22, alpha=.55, linewidths=0)
        mean = data['primary_score'] * 100
        ax.plot([i-.22, i+.22], [mean, mean], color=color, linewidth=3)
        ax.annotate(f'{mean:.2f}%', (i, mean), xytext=(0, 7),
                    textcoords='offset points', ha='center', size=9, weight='bold')
    ax.set_xticks(range(3), [r[1] for r in labels], fontsize=9)
    ax.set_xlim(-.5, 2.5)
    ax.set_ylim(bottom=0)
    ax.set_ylabel('Coordination reward (%)')
    ax.set_title('Fresh worlds: every outcome', loc='left', size=11, pad=12)
    ax.grid(axis='y', alpha=.2)

    ax = axes[2]
    data = comparison['transfer']['selected_minus_reference']
    if data['mean_difference'] is not None:
        xs = [r['world_id'] for r in data['worlds']]
        ys = [r['difference'] * 100 for r in data['worlds']]
        ax.axhline(0, color=gray, linewidth=.8)
        ax.vlines(xs, 0, ys, colors=[teal if y >= 0 else orange for y in ys], alpha=.7)
        ax.scatter(xs, ys, c=[teal if y >= 0 else orange for y in ys], s=25)
        bound = max(1.0, max(abs(y) for y in ys)) * 1.15
        ax.set_ylim(-bound, bound)
        mean = data['mean_difference'] * 100
        ax.axhline(mean, color=navy, linestyle='--', linewidth=1.2)
        ax.text(.02, .98, f'Mean: {mean:+.2f} pp\n'
                f'{data["better"]} better · {data["equal"]} tied · {data["worse"]} worse',
                transform=ax.transAxes, va='top', fontsize=9,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .85})
        ax.set_xticks([30000, 30005, 30010, 30015, 30019],
                      ['30000', '30005', '30010', '30015', '30019'], rotation=45, fontsize=8)
    else:
        ax.text(.5, .5, 'Incomplete comparison\nNo mean reported', transform=ax.transAxes, ha='center')
    ax.set_xlabel('World ID')
    ax.set_ylabel('Selected − pass-through (percentage points)')
    ax.set_title('Fresh worlds: paired changes', loc='left', size=11, pad=12)
    ax.grid(axis='y', alpha=.2)
    fig.text(.065, .135, 'Middle and right panels show game worlds, not researcher attempts. Selected equals pass-through; its result is reused.', size=9, color=gray)
    fig.text(.065, .09, 'The original 20-world results are reported separately as regression checks. No confidence intervals or model-ranking claim.', size=9, color=gray)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.svg', '.png'):
        fig.savefig(args.output.with_suffix(suffix), dpi=180, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
