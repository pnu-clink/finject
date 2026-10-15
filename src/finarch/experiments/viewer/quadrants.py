"""Read saved cross-run comparisons for the experiments viewer; never write runs."""
import argparse
import json
import sys
from pathlib import Path

from finarch.documentation import research_ic_value_quadrant as research


def build_report(run_root, project_root=research.ROOT):
    # [EV23.2] Reuse the standalone collector's cohort and denominator checks.
    snapshot, sources, inventory = research.build_snapshot(project_root, run_root=run_root)
    research.require(all(research.sha(Path(project_root) / name) == value
                         for name, value in sources.items()), 'SOURCE_CHANGED_DURING_BUILD')
    snapshot['viewer'] = True
    return {'html': research.render_page(snapshot, viewer=True),
            'metadata': {'generated_at': snapshot['generated_at'],
                         'datasets': [{'label': dataset['label'], 'cohorts': len(dataset['cohorts'])}
                                      for dataset in snapshot['datasets']],
                         'inventory_summary': snapshot['inventory_summary'],
                         'inventory': inventory, 'source_files': len(sources), 'model_calls': 0}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_report(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        result = {'error': str(error), 'status': 404 if str(error) == 'NO_COMPARABLE_SAVED_RESULTS' else 409}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
