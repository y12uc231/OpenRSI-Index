"""Plot all submissions, keeping the declared selected system unchanged."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent


def main():
    data = json.loads((ROOT / 'study-analysis.json').read_text())
    for folder, key in [('sol-continuation-001', 'main_manifest_sha256'),
                        ('sol-trajectory-diagnostic-001', 'diagnostic_manifest_sha256')]:
        directory = ROOT / 'results' / folder
        manifest = (directory / 'MANIFEST.json').read_bytes()
        if hashlib.sha256(manifest).hexdigest() != data[key]:
            raise ValueError('analysis_manifest_mismatch')
        for name, digest in json.loads(manifest)['files'].items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError('changed_export')
    rows = data['rows'][1:]
    navy, teal, orange, gray = '#294b71', '#00836d', '#b65525', '#67717c'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none'})
    fig = plt.figure(figsize=(12, 9))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.25], left=.11, right=.91,
                          top=.80, bottom=.18, hspace=.65)
    ax = fig.add_subplot(gs[0])
    fig.text(.06, .945, 'Does the development ranking hold on other worlds?',
             fontsize=19, weight='bold', color=navy)
    fig.text(.06, .90, 'Every submitted program · fixed code · no final scores returned to the model', fontsize=11)
    fig.text(.06, .858, 'Secondary diagnostic declared before final outcomes. The primary selection remains the unchanged policy.',
             fontsize=10, color=gray)
    missing_line = 0
    for suite, name, color, marker in [('dev', 'Development (4 worlds)', orange, 's'),
                                       ('evaluation', 'Original worlds (20)', navy, '^'),
                                       ('transfer', 'Fresh worlds (20)', teal, 'o')]:
        values = [r['suites'][suite]['minus_reference']['mean_difference'] for r in rows]
        values = [v * 100 if v is not None else float('nan') for v in values]
        ax.plot(range(len(rows)), values, label=name, color=color, marker=marker, linewidth=1.5, markersize=6)
        for i, value in enumerate(values):
            if not np.isfinite(value):
                ax.text(i, .03 + .07 * missing_line, 'Unscored: ' + suite,
                        transform=ax.get_xaxis_transform(), fontsize=7, ha='center', color=color)
        missing_line += 1
    ax.axhline(0, color=gray, linewidth=.9, linestyle='--')
    ax.set_xticks(range(len(rows)), ['Original Sol'] + [f'Call {i}' for i in range(1, 7)])
    ax.set_ylabel('Gain over unchanged policy\n(percentage points)')
    ax.set_title('Mean reward differences on each fixed set', loc='left', fontsize=11, pad=12)
    ax.grid(axis='y', alpha=.18)
    ax.legend(frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(.5, -.20), fontsize=9)

    ax = fig.add_subplot(gs[1])
    arrays = [[w['difference'] * 100 if w['difference'] is not None else float('nan')
               for w in r['suites']['transfer']['minus_reference']['worlds']] for r in rows]
    matrix = np.asarray(arrays)
    finite = matrix[np.isfinite(matrix)]
    bound = max(1.0, float(max(abs(finite)))) if len(finite) else 1.0
    cmap = plt.get_cmap('BrBG').copy()
    cmap.set_bad('#bfc4cb')
    rendered = ax.imshow(matrix, cmap=cmap, vmin=-bound, vmax=bound, aspect='auto')
    names = ['Original Sol'] + [f'Call {i}' for i in range(1, 7)]
    names = [name + (' (unscored suite)' if row['suites']['transfer']['status'] != 'scored' else '')
             for name, row in zip(names, rows)]
    ax.set_yticks(range(len(rows)), names)
    ids = [w['world_id'] for w in rows[0]['suites']['transfer']['minus_reference']['worlds']]
    ax.set_xticks(range(len(ids)), [str(w) for w in ids], rotation=60, ha='right', fontsize=8)
    ax.set_xlabel('Fresh world ID')
    ax.set_title('Every paired fresh-world difference; brown is worse, green is better', loc='left', fontsize=11, pad=12)
    colorbar = fig.colorbar(rendered, ax=ax, fraction=.022, pad=.025)
    colorbar.set_label('Percentage points', fontsize=9)
    if not np.isfinite(matrix).all():
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(facecolor='#bfc4cb', label='Unscored paired world')],
                  loc='lower right', fontsize=8)
    fig.text(.06, .065, 'All rows are retained in generation order. They are dependent code revisions, not independent researcher trials.',
             fontsize=9, color=gray)
    fig.text(.06, .035, 'A high fresh-set score in this diagnostic is a retrospective observation, not an independently validated choice.',
             fontsize=9, color=gray)
    for suffix in ('.png', '.svg'):
        fig.savefig(ROOT / ('trajectory' + suffix), dpi=180, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
