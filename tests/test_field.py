from fractions import Fraction
import json
import random

from field.export import export_ledger, format_result
from field.query import query_probe
from field.session import open_session
from history.basins import build_history, compute_summary
from history.levels import activation_levels
from history.moments import BasinMoments
from history.summary import BasinEvent, BasinSummary, SummarySource
from registry import NotFoundError
from release.bundle import BundleError, encode_bundle, export_bundle
from release.manifest import ReleaseManifest, build_manifest
from survey.catalog import get_plan
from terrain.revisions import get_revision
from tests.fixtures import RegistryTestCase, cell, probe, reading, saddle_inputs


def flood_oracle(raw_rows, origin, level):
    wet = {}
    for row, raw_row in enumerate(raw_rows):
        for column, raw in enumerate(raw_row):
            if raw is not None and Fraction(raw['height']) < level:
                wet[(row, column)] = raw
    if origin not in wet:
        return 'dry', None, None
    reachable = {origin}
    while True:
        extended = set(reachable)
        for candidate in wet:
            if any(abs(candidate[0] - row) + abs(candidate[1] - column) == 1 for row, column in reachable):
                extended.add(candidate)
        if extended == reachable:
            break
        reachable = extended
    columns = len(raw_rows[0])
    basin_id = min(row * columns + column for row, column in reachable)
    volume = sum((
        Fraction(wet[position]['area']) * (level - Fraction(wet[position]['height']))
        for position in reachable
    ), Fraction(0))
    return 'wet', basin_id, volume


class FieldTests(RegistryTestCase):
    def test_equal_saddles(self):
        rows, probes = saddle_inputs()
        bundle = self.issue(rows, probes)
        self.disconnect()
        session = open_session(bundle)
        names = ('west', 'center', 'east')
        requests = [reading(name, level) for level in (2, '5/2') for name in names]
        expected = [
            {'status': 'wet', 'basin_id': 0, 'volume': [2, 1]},
            {'status': 'wet', 'basin_id': 2, 'volume': [2, 1]},
            {'status': 'wet', 'basin_id': 4, 'volume': [6, 1]},
            {'status': 'wet', 'basin_id': 0, 'volume': [14, 1]},
            {'status': 'wet', 'basin_id': 0, 'volume': [14, 1]},
            {'status': 'wet', 'basin_id': 0, 'volume': [14, 1]},
        ]
        actual = [format_result(query_probe(session, **request)) for request in requests]
        self.assertEqual(actual, expected, 'BASIN_HANDOFF_MISMATCH: offline probe results')
        expected_ledger = {'release_id': 'e1', 'rows': [
            {'position': index, 'probe_id': request['probe_id'],
             'water': [2, 1] if index < 3 else [5, 2], 'result': expected[index]}
            for index, request in enumerate(requests)
        ]}
        actual_ledger = export_ledger(session, requests)
        self.assertEqual(actual_ledger, expected_ledger, 'BASIN_HANDOFF_MISMATCH: offline ledger')
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'saddle_audit',
            'input': {'terrain': rows, 'probes': probes, 'requests': requests},
            'expected': expected,
            'actual': actual,
            'downstream_expected': expected_ledger,
            'downstream_actual': actual_ledger,
            'code_paths': ['history/basins.py', 'release/publish.py', 'release/bundle.py',
                           'field/query.py', 'field/ledger.py', 'field/export.py'],
            'oracle': 'At 2 m the three depths give 2, 2, 6 m³. At 5/2 m the five contributions are 5/2, 1/2, 3, 1/2, 15/2 m³ and sum to 14 m³.',
        }, ensure_ascii=True, separators=(',', ':')))

    def test_boundary_probes(self):
        rows, probes = saddle_inputs()
        bundle = self.issue(rows, probes)
        for name in ('west-saddle', 'east-saddle'):
            with self.subTest(probe=name):
                at = query_probe(bundle, name, 2)
                self.assertEqual((at.status, at.basin_id, at.volume), ('dry', None, None))
                over = query_probe(bundle, name, '5/2')
                self.assertEqual((over.status, over.basin_id, over.volume), ('wet', 0, Fraction(14)))

    def test_equal_height_permutation(self):
        rows, probes = saddle_inputs()
        stored = self.issue(rows, probes)
        revision = get_revision(self.db, 'r1')
        plan = get_plan(self.db, 'p1')
        cells = tuple(revision.grid.valid_cells())
        forward = tuple(activation_levels(cells))
        reverse = tuple(activation_levels(reversed(cells)))
        self.assertEqual([item.cell_id for item in forward[-1].cells], [1, 3])
        self.assertEqual([item.cell_id for item in reverse[-1].cells], [3, 1])
        source = compute_summary(revision, plan).source
        reversed_summary = build_history(revision.grid.shape, source, plan.probes, reverse)
        manifest = build_manifest('e1', plan, revision, reversed_summary)
        reversed_bundle = encode_bundle(manifest, reversed_summary)
        self.assertEqual(reversed_bundle, stored)
        before = query_probe(reversed_bundle, 'east', 2)
        after = query_probe(reversed_bundle, 'east', '5/2')
        self.assertEqual((before.basin_id, before.volume), (4, Fraction(6)))
        self.assertEqual((after.basin_id, after.volume), (0, Fraction(14)))

    def test_flood_oracle(self):
        rows = [
            [cell(0, '1/2'), cell(2, '3/2'), cell('-1/2', 2), None, cell(2, '2/3')],
            [None, cell(2), cell('1/3', '5/4'), None, None],
            [cell(-1, '3/2'), None, cell(2, '7/3'), cell(0), None],
        ]
        probes = [probe(f'{row}-{column}', row, column)
                  for row, raw_row in enumerate(rows) for column, raw in enumerate(raw_row) if raw is not None]
        bundle = self.issue(rows, probes)
        self.disconnect()
        session = open_session(bundle)
        for water in ('-2', '-1', '-3/4', '0', '1/6', '1/3', '7/6', '2', '13/6', '5/2'):
            for point in probes:
                name = point['probe_id']
                with self.subTest(water=water, probe=name):
                    origin = (point['row'], point['column'])
                    expected = flood_oracle(rows, origin, Fraction(water))
                    actual = query_probe(session, name, water)
                    self.assertEqual((actual.status, actual.basin_id, actual.volume), expected)

    def test_ledger_order(self):
        rows, probes = saddle_inputs()
        bundle = self.issue(rows, probes)
        ledger = export_ledger(bundle, [reading('east', '5/2'), reading('west', 2),
                                        reading('east', 2), reading('east-saddle', 2)])
        self.assertEqual(ledger, {'release_id': 'e1', 'rows': [
            {'position': 0, 'probe_id': 'east', 'water': [5, 2],
             'result': {'status': 'wet', 'basin_id': 0, 'volume': [14, 1]}},
            {'position': 1, 'probe_id': 'west', 'water': [2, 1],
             'result': {'status': 'wet', 'basin_id': 0, 'volume': [2, 1]}},
            {'position': 2, 'probe_id': 'east', 'water': [2, 1],
             'result': {'status': 'wet', 'basin_id': 4, 'volume': [6, 1]}},
            {'position': 3, 'probe_id': 'east-saddle', 'water': [2, 1], 'result': {'status': 'dry'}},
        ]})
        self.assertEqual(export_ledger(bundle, []), {'release_id': 'e1', 'rows': []})

    def test_revision_isolation(self):
        rows, probes = saddle_inputs()
        original = self.issue(rows, probes)
        rows[0][3]['height'] = 3
        updated = self.issue(rows, probes, revision='r2', plan='p2', release='e2')
        self.disconnect()
        older = open_session(original)
        newer = open_session(updated)
        self.assertEqual((older.manifest.release_id, older.manifest.source.revision_id), ('e1', 'r1'))
        self.assertEqual((newer.manifest.release_id, newer.manifest.source.revision_id), ('e2', 'r2'))
        updated_expected = {'west': (0, Fraction(6)), 'center': (0, Fraction(6)), 'east': (4, Fraction(15, 2))}
        for name, expected in updated_expected.items():
            old_result = query_probe(older, name, '5/2')
            new_result = query_probe(newer, name, '5/2')
            self.assertEqual((old_result.basin_id, old_result.volume), (0, Fraction(14)))
            self.assertEqual((new_result.basin_id, new_result.volume), expected)

    def test_reexport_frozen(self):
        rows, probes = saddle_inputs()
        original = self.issue(rows, probes)
        rows[0][3]['height'] = 3
        updated = self.issue(rows, probes, revision='r2', plan='p2', release='e2')
        resent = export_bundle(self.db, 'e1')
        self.disconnect()
        self.assertEqual(resent, original)
        self.assertNotEqual(resent, updated)
        session = open_session(resent)
        self.assertEqual(session.manifest.source.revision_id, 'r1')
        self.assertEqual(export_ledger(session, [reading('east', '5/2')]), {'release_id': 'e1', 'rows': [
            {'position': 0, 'probe_id': 'east', 'water': [5, 2],
             'result': {'status': 'wet', 'basin_id': 0, 'volume': [14, 1]}},
        ]})

    def test_unknown_probe(self):
        bundle = self.issue([[cell(0)]], [probe('known', 0, 0)])
        with self.assertRaisesRegex(NotFoundError, 'unknown probe'):
            query_probe(bundle, 'missing', 2)
        with self.assertRaisesRegex(NotFoundError, "ledger row 1: unknown probe 'missing'"):
            export_ledger(bundle, [reading('known', 2), reading('missing', 1)])
        corrected = export_ledger(bundle, [reading('known', 2), reading('known', 1)])
        self.assertEqual([row['result']['volume'] for row in corrected['rows']], [[2, 1], [1, 1]])

    def test_invalid_inputs(self):
        bundle = self.issue([[cell(0)]], [probe('known', 0, 0)])
        with self.assertRaises(BundleError):
            query_probe(b'not a bundle', 'known', 2)
        with self.assertRaises(BundleError):
            export_ledger(b'{"version":1,"version":1}', [])
        for water in (True, 1.25, 'bad', '1/0', [1, 0], [1, -2]):
            with self.subTest(water=water):
                with self.assertRaises(ValueError):
                    query_probe(bundle, 'known', water)
                with self.assertRaisesRegex(ValueError, 'ledger row 1'):
                    export_ledger(bundle, [reading('known', 2), reading('known', water)])
        record = json.loads(bundle)
        record['manifest']['source']['revision_id'] = 'other'
        with self.assertRaisesRegex(BundleError, 'different sources'):
            open_session(json.dumps(record).encode('utf-8'))
        record = json.loads(bundle)
        record['summary']['probe_nodes'][0][1] = 999
        with self.assertRaisesRegex(BundleError, 'invalid event'):
            open_session(json.dumps(record).encode('utf-8'))
        record = json.loads(bundle)
        record['summary']['events'][0]['area'] = [2, 2]
        with self.assertRaisesRegex(BundleError, 'reduced'):
            open_session(json.dumps(record).encode('utf-8'))

    def test_successive_merges(self):
        # INCIDENT.md: 3x3, only cells 0, 1, 2, 3, 6 valid.  Cells 0, 2, 6
        # stand at 0 m with areas 1, 2, 3; cells 1 and 3 have area 1 and swap
        # heights between the two revisions.
        def rows(cell_one, cell_three):
            return [
                [cell(0, 1), cell(cell_one, 1), cell(0, 2)],
                [cell(cell_three, 1), None, None],
                [cell(0, 3), None, None],
            ]

        expected = {
            'forward': {2: (0, Fraction(2)), '5/2': (0, Fraction(8)), '7/2': (0, Fraction(23))},
            'reverse': {2: (0, Fraction(2)), '5/2': (0, Fraction(21, 2)), '7/2': (0, Fraction(23))},
        }
        for label, (one, three), revision, plan, release in (
            ('forward', (2, 3), 'ra', 'pa', 'ea'),
            ('reverse', (3, 2), 'rb', 'pb', 'eb'),
        ):
            with self.subTest(composition=label):
                bundle = self.issue(
                    rows(one, three), [probe('visit', 0, 0)],
                    revision=revision, plan=plan, release=release,
                )
                for water, (basin_id, volume) in expected[label].items():
                    result = query_probe(bundle, 'visit', water)
                    self.assertEqual(
                        (result.status, result.basin_id, result.volume),
                        ('wet', basin_id, volume),
                        f'BASIN_HANDOFF_MISMATCH: successive merges at {water}',
                    )

    def test_seeded_exhaustive_oracle(self):
        rng = random.Random(20240607)
        heights = ('-1', '0', '1/3', '1', '3/2', '2')
        areas = ('1/2', '1', '2', '5/3')
        for trial in range(24):
            row_count = rng.randint(1, 3)
            column_count = rng.randint(1, 4)
            rows = []
            for _ in range(row_count):
                raw_row = []
                for _ in range(column_count):
                    if rng.random() < 0.15:
                        raw_row.append(None)
                    else:
                        raw_row.append(cell(rng.choice(heights), rng.choice(areas)))
                rows.append(raw_row)
            points = [probe(f'{row}-{column}', row, column)
                      for row, raw_row in enumerate(rows)
                      for column, raw in enumerate(raw_row) if raw is not None]
            if not points:
                continue
            with self.subTest(trial=trial):
                bundle = self.issue(
                    rows, points,
                    revision=f'r{trial}', plan=f'p{trial}', release=f'e{trial}',
                )
                wet_heights = {Fraction(raw['height'])
                               for raw_row in rows for raw in raw_row if raw is not None}
                waters = set()
                for height in wet_heights:
                    waters.update((height, height - Fraction(1, 2), height + Fraction(1, 2)))
                for water in sorted(waters):
                    for point in points:
                        expected = flood_oracle(rows, (point['row'], point['column']), water)
                        result = query_probe(bundle, point['probe_id'], water)
                        self.assertEqual(
                            (result.status, result.basin_id, result.volume), expected,
                            f'BASIN_HANDOFF_MISMATCH: trial {trial} at {water}',
                        )

    def test_legacy_summary_format_readable(self):
        # Packages written before the merge fix use the same v1 wire shape:
        # level, basin number, introduced moments and a predecessor list that
        # never exceeded one entry.  They must stay readable and evaluable
        # without the source grid, and re-encode byte-for-byte.
        source = SummarySource('old-plan', 'old-revision', 'a' * 64)
        legacy_events = (
            BasinEvent(Fraction(0), 0, BasinMoments(Fraction(1), Fraction(0)), ()),
            BasinEvent(Fraction(1), 2, BasinMoments(Fraction(2), Fraction(2)), ()),
            BasinEvent(Fraction(2), 0, BasinMoments(Fraction(1), Fraction(2)), (0,)),
            BasinEvent(Fraction(3), 0, BasinMoments(Fraction(1), Fraction(3)), (2,)),
        )
        summary = BasinSummary(source, legacy_events, (('left', 0), ('right', 1)))
        legacy = encode_bundle(ReleaseManifest('legacy', source, ('left', 'right')), summary)
        session = open_session(legacy)
        dry = query_probe(session, 'left', 0)
        rising = [
            (result.basin_id, result.volume)
            for result in (query_probe(session, 'left', water) for water in ('1/2', '3/2', '5/2', '7/2'))
        ]
        self.assertEqual((dry.status, dry.basin_id, dry.volume), ('dry', None, None))
        self.assertEqual(rising, [
            (0, Fraction(1, 2)),
            (0, Fraction(3, 2)),
            (0, Fraction(3)),
            (0, Fraction(11, 2)),
        ])
        # The other branch keeps its own partition: it never joins the left
        # basin, whose later events list no matching predecessor.
        self.assertEqual(query_probe(session, 'right', '3/2').volume, Fraction(1))
        self.assertEqual(query_probe(session, 'right', 2).volume, Fraction(2))
        self.assertEqual(query_probe(session, 'right', '7/2').volume, Fraction(5))
        self.assertEqual(encode_bundle(session.manifest, session.summary), legacy)

    def test_new_merge_summary_readable(self):
        # A package that records two absorbed partitions in one predecessor
        # list decodes, validates and evaluates offline.
        source = SummarySource('merge-plan', 'merge-revision', 'b' * 64)
        events = (
            BasinEvent(Fraction(0), 0, BasinMoments(Fraction(1), Fraction(0)), ()),
            BasinEvent(Fraction(0), 2, BasinMoments(Fraction(1), Fraction(0)), ()),
            BasinEvent(Fraction(2), 0, BasinMoments(Fraction(1), Fraction(2)), (0, 1)),
        )
        summary = BasinSummary(source, events, (('left', 0), ('right', 1)))
        bundle = encode_bundle(ReleaseManifest('merge', source, ('left', 'right')), summary)
        session = open_session(bundle)
        self.assertEqual(query_probe(session, 'left', 0).status, 'dry')
        self.assertEqual(query_probe(session, 'left', '3/2').volume, Fraction(3, 2))
        self.assertEqual(query_probe(session, 'left', 3).volume, Fraction(7))
        self.assertEqual(query_probe(session, 'right', 3).volume, Fraction(7))
