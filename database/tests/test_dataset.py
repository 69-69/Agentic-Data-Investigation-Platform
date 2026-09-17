"""Offline fixture contracts. PostgreSQL-specific checks live in verify.sql."""
import hashlib
import importlib.util
import json
import unittest
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generate', ROOT / 'synthetic-data/generate.py')
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate.build_dataset()
        cls.rows = {table: [dict(zip(generate.COLUMNS[table], row)) for row in rows]
                    for table, rows in cls.data.items()}
        cls.tx = cls.rows['transactions']

    def window(self, start, end):
        return [t for t in self.tx if start <= t['transaction_date'][:10] < end]

    def test_counts_and_unique_primary_keys(self):
        self.assertEqual({t: len(rows) for t, rows in self.data.items()}, {
            'customers': 400, 'transactions': 10560, 'pipeline_runs': 56,
            'data_quality_events': 4, 'deployments': 3})
        for rows in self.data.values():
            self.assertEqual(len(rows), len({row[0] for row in rows}))

    def test_customer_references_and_timestamps(self):
        customers = {r['id']: r for r in self.rows['customers']}
        for t in self.tx:
            self.assertIn(t['customer_id'], customers)
            self.assertEqual(t['region'], customers[t['customer_id']]['region'])
            self.assertLessEqual(customers[t['customer_id']]['created_at'], t['transaction_date'])
            self.assertLessEqual(t['transaction_date'], t['created_at'])
            self.assertGreater(float(t['amount']), 0)

    def test_decline_is_one_week_and_recovers(self):
        counts = Counter(t['transaction_date'][:10] for t in self.tx)
        self.assertEqual({d for d, c in counts.items() if c < 200},
                         {f'2026-06-{d:02}' for d in range(15, 22)})
        self.assertEqual(len(self.window('2026-06-08', '2026-06-15')), 1400)
        self.assertEqual(len(self.window('2026-06-15', '2026-06-22')), 700)
        self.assertEqual(counts['2026-06-22'], 200)

    def test_pipeline_reconciliation(self):
        counts = Counter(t['transaction_date'][:10] for t in self.tx)
        elevated = []
        for run in self.rows['pipeline_runs']:
            day = run['started_at'][:10]
            self.assertEqual(run['records_processed'], counts[day])
            if run['records_rejected'] > 2:
                elevated.append(run)
                self.assertEqual(run['records_rejected'], 102)
                self.assertEqual(run['status'], 'partial')
                self.assertEqual(run['error_code'], 'SCHEMA_VALIDATION')
            self.assertLess(run['started_at'], run['completed_at'])
        self.assertEqual(len(elevated), 7)
        self.assertEqual(sum(r['records_rejected'] for r in elevated), 714)
        self.assertEqual(sum(r['records_processed'] for r in elevated), 700)
        self.assertEqual({r['started_at'][:10] for r in elevated},
                         {f'2026-06-{d:02}' for d in range(15, 22)})

    def test_duplicates_only_in_documented_window(self):
        columns = [c for c in generate.COLUMNS['transactions'] if c not in ('id', 'created_at')]
        groups = Counter(tuple(t[c] for c in columns) for t in self.tx)
        duplicates = {key: count for key, count in groups.items() if count > 1}
        self.assertEqual(len(duplicates), 60)
        self.assertEqual(sum(count - 1 for count in duplicates.values()), 60)
        date_index = columns.index('transaction_date')
        self.assertEqual(Counter(key[date_index][:10] for key in duplicates),
                         {'2026-06-24': 20, '2026-06-25': 20, '2026-06-26': 20})

    def test_regional_declines_have_control_region_and_baseline(self):
        for start, end, expected_east in [('2026-06-29', '2026-07-06', 14),
                                           ('2026-07-06', '2026-07-13', 280)]:
            rows = self.window(start, end)
            for region in generate.REGIONS:
                region_rows = [t for t in rows if t['region'] == region]
                self.assertEqual(len(region_rows), 350)
                self.assertEqual(sum(t['status'] == 'declined' for t in region_rows),
                                 expected_east if region == 'east' else 14)

    def test_quality_anomalies_and_event_counts(self):
        missing = [t for t in self.tx if t['merchant_category'] is None]
        malformed = [t for t in self.tx if t['channel'] not in ('web', 'mobile', 'branch')]
        self.assertEqual(Counter(t['transaction_date'][:10] for t in missing),
                         {'2026-07-15': 10, '2026-07-16': 10})
        self.assertEqual(Counter(t['transaction_date'][:10] for t in malformed), {'2026-07-17': 10})
        self.assertEqual([r['affected_records'] for r in self.rows['data_quality_events']], [714, 60, 20, 10])

    def test_deployment_precedes_anomaly(self):
        release = self.rows['deployments'][0]
        self.assertEqual(release['service_name'], 'transaction_ingestion')
        onset = datetime.fromisoformat('2026-06-15T00:00:00+00:00')
        self.assertEqual(onset - datetime.fromisoformat(release['deployed_at']), timedelta(minutes=15))

    def test_byte_reproducibility_and_manifest(self):
        first = generate.artifacts()
        self.assertEqual(first, generate.artifacts())
        self.assertEqual(first[0].encode(), (ROOT / 'seed/synthetic-v1.sql').read_bytes())
        self.assertEqual(first[1].encode(), (ROOT / 'seed/manifest.json').read_bytes())
        manifest = json.loads(first[1])
        self.assertEqual(manifest['sha256'], hashlib.sha256(first[0].encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
