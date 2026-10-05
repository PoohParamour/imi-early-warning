"""Independent review checks; writes evidence without changing experiment design.

Usage: .venv/bin/python scripts/review_checks.py --before /path/to/review/snapshot
The optional snapshot contains logs/, processed/, and interim/ captured before review.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/review'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def notebook_function(filename, name, namespace):
    notebook = json.loads((ROOT / 'notebooks' / filename).read_text())
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        for node in ast.parse(''.join(cell['source'])).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec'), namespace)
                return namespace[name]
    raise AssertionError(f'Function not found: {filename}:{name}')


def main(before=None):
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {}
    metrics = ROOT / 'logs/metrics'
    raw = ROOT / 'data/raw'
    sources = json.loads((raw / 'sources.json').read_text())['sources']
    for item in sources:
        assert digest(raw / item['file']) == item['sha256']
        for prefix in ('request_bodies', 'request_manifest'):
            if prefix + '_file' in item:
                assert digest(raw / item[prefix + '_file']) == item[prefix + '_sha256']
    evidence['raw_sha256'] = {p.name: digest(p) for p in raw.iterdir() if p.is_file()}
    evidence['source_records_verified'] = len(sources)

    man03 = pd.read_csv(metrics / '03_processed_manifest.csv').iloc[0]
    man04 = pd.read_csv(metrics / '04_run_manifest.csv').iloc[0]
    assert digest(ROOT / man03.file) == man03.sha256 == man04.modeling_table_sha256
    assert digest(ROOT / man04.file) == man04.sha256
    evidence['manifest_chain'] = {'03': man03.sha256, '04': man04.sha256}
    model = pd.read_csv(ROOT / man03.file, dtype={'commodity_code': str},
                        parse_dates=['month_ce', 'forecast_origin', 'target_month', 'target_available_date'])
    origins = pd.read_csv(metrics / '04_origins.csv', dtype={'commodity_code': str},
                          parse_dates=['month_ce', 'forecast_origin', 'train_last_t'])
    panels = {k: f.sort_values('month_ce') for k, f in model.groupby(['commodity_code', 'horizon'])}
    max_threshold_error = 0.0
    train_functions = [notebook_function(name, 'training_rows', {'pd': pd})
                       for name in ('04_modeling.ipynb', '05b_iteration2.ipynb')]
    train06 = notebook_function('06_deployment.ipynb', 'train_rows', {'pd': pd, 'modeling': model})
    for row in origins.itertuples():
        expected = panels[row.commodity_code, row.horizon]
        expected = expected[expected.target_month <= row.month_ce]
        for function in train_functions:
            actual = function(panels[row.commodity_code, row.horizon], row)
            assert set(actual.index) == set(expected.index)
        assert set(train06(row.commodity_code, row.horizon, row.forecast_origin).index) == set(expected.index)
        assert len(expected) == row.train_n and expected.month_ce.max() == row.train_last_t
        error = abs(np.quantile(expected.target_y_pct, .8) - row.high_risk_threshold)
        max_threshold_error = max(max_threshold_error, error)
        assert np.isclose((expected.target_y_pct > 0).mean(), row.train_up_share)
    evidence['training_origins_checked'] = len(origins)
    evidence['max_threshold_error'] = max_threshold_error

    # Audit selection-time label availability without reselecting alpha or models.
    rows = []
    for (group, horizon), panel in panels.items():
        validation = panel[panel.month_ce.between('2015-01-01', '2018-12-01')]
        available = validation.target_available_date.max()
        test = panel[panel.month_ce >= '2019-01-01']
        affected = test[test.forecast_origin < available]
        rows.append({'commodity_code': group, 'horizon': horizon,
                     'last_validation_target_available': available.date(),
                     'first_test_origin': test.forecast_origin.min().date(),
                     'affected_test_origins': len(affected),
                     'affected_base_months': '|'.join(affected.month_ce.dt.strftime('%Y-%m'))})
    availability = pd.DataFrame(rows)
    availability.to_csv(OUT / 'selection_availability.csv', index=False)
    evidence['selection_timing'] = {'affected_origins': int(availability.affected_test_origins.sum()),
                                     'test_origins': int((origins.split == 'test').sum())}

    edge_cases = [([2, 2], [0, 0], 0), ([0, 0], [2, 2], 0),
                  ([2, 0], [2, 0], 1), ([0, 0], [0, 0], np.nan)]
    for filename in ('05_evaluation.ipynb', '05b_iteration2.ipynb'):
        score = notebook_function(filename, 'alert_scores', {'np': np})
        for y, pred, expected in edge_cases:
            result = score(pd.DataFrame({'y_true': y, 'y_pred': pred, 'high_risk_threshold': 1}))
            assert (np.isnan(expected) and np.isnan(result['F1'])) or result['F1'] == expected
    evidence['alert_edge_cases_passed'] = 8

    evidence['environment'] = {}
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        name, pin = line.split('==')
        assert version(name) == pin
        evidence['environment'][name] = version(name)
    for name in ('numpy', 'nbconvert', 'nbclient'):
        evidence['environment'][name] = version(name)

    notebook_checks = []
    for path in sorted((ROOT / 'notebooks').glob('*.ipynb')):
        notebook = json.loads(path.read_text())
        code = [c for c in notebook['cells'] if c['cell_type'] == 'code']
        assert all(c['execution_count'] is not None for c in code)
        assert not any(o['output_type'] == 'error' for c in code for o in c.get('outputs', []))
        for c in code:
            for n in ast.parse(''.join(c['source'])).body:
                if isinstance(n, ast.Assign):
                    for target in n.targets:
                        if isinstance(target, ast.Name) and target.id.startswith('DOWNLOAD_'):
                            assert ast.literal_eval(n.value) is False
        notebook_checks.append({'notebook': path.name, 'executed_code_cells': len(code), 'errors': 0})
    evidence['notebook_checks'] = notebook_checks

    if before:
        comparisons = []
        for old in sorted((Path(before) / 'logs/metrics').glob('*.csv')):
            new = metrics / old.name
            a, b = pd.read_csv(old), pd.read_csv(new)
            common = list(a.columns.intersection(b.columns))
            changed = [c for c in common if not a[c].equals(b[c])]
            comparisons.append({'file': old.name, 'rows_before': len(a), 'rows_after': len(b),
                                'byte_identical': digest(old) == digest(new),
                                'changed_columns': '|'.join(changed),
                                'added_columns': '|'.join(b.columns.difference(a.columns))})
        pd.DataFrame(comparisons).to_csv(OUT / 'rerun_comparison.csv', index=False)
        evidence['rerun_byte_identical_tables'] = sum(c['byte_identical'] for c in comparisons)
        evidence['rerun_tables'] = len(comparisons)
        # Historical log entries must remain byte-for-byte intact as a prefix.
        assert (ROOT / 'logs/process_log.md').read_bytes().startswith((Path(before) / 'logs/process_log.md').read_bytes())
        for name in ('modeling_table.csv', 'latest_features.csv'):
            assert digest(ROOT / 'data/processed' / name) == digest(Path(before) / 'processed' / name)
    (OUT / 'review_evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('raw_sha256','environment')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path)
    main(parser.parse_args().before)
