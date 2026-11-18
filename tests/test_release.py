from contextlib import closing
from fractions import Fraction
import sqlite3

from field.query import query_probe
from field.session import open_session
from history.basins import compute_summary
from registry import ConflictError, NotFoundError
from release.bundle import export_bundle
from release.publish import publish
from release.store import read_release
from survey.catalog import get_plan
from survey.plans import freeze_plan
from terrain.revisions import get_revision, put_terrain
from tests.fixtures import RegistryTestCase, cell, probe


class ReleaseTests(RegistryTestCase):
    def test_fixed_basin(self):
        bundle = self.issue([[cell(0), cell(1, 2)]], [probe('low', 0, 0), probe('high', 0, 1)])
        session = open_session(bundle)
        self.assertEqual(session.manifest.release_id, 'e1')
        self.assertEqual(session.manifest.source.revision_id, 'r1')
        self.assertEqual(session.manifest.source.plan_id, 'p1')
        for name in ('low', 'high'):
            result = query_probe(session, name, 2)
            self.assertEqual((result.status, result.basin_id, result.volume), ('wet', 0, Fraction(4)))

    def test_no_row_wrap(self):
        bundle = self.issue([[None, cell(0)], [cell(0, 2), None]], [probe('upper', 0, 1), probe('lower', 1, 0)])
        upper = query_probe(bundle, 'upper', 2)
        lower = query_probe(bundle, 'lower', 2)
        self.assertEqual((upper.basin_id, upper.volume), (1, Fraction(2)))
        self.assertEqual((lower.basin_id, lower.volume), (2, Fraction(4)))

    def test_fraction_round_trip(self):
        original = self.issue([[cell('1/7', '2/3')]], [probe('visit', 0, 0)])
        self.disconnect()
        with closing(sqlite3.connect(self.path)) as reopened:
            reexported = export_bundle(reopened, 'e1')
        self.assertEqual(reexported, original)
        result = query_probe(reexported, 'visit', '1/2')
        self.assertEqual((result.basin_id, result.volume), (0, Fraction(5, 21)))
        self.assertIsInstance(result.volume, Fraction)

    def test_pinned_parent(self):
        put_terrain(self.db, 'r1', [[cell(0), cell(1, 2)]])
        freeze_plan(self.db, 'p1', 'r1', [probe('visit', 0, 1)])
        put_terrain(self.db, 'r2', [[cell(0), cell(3, 2)]])
        self.assertEqual(publish(self.db, 'late', 'p1'), 'late')
        session = open_session(export_bundle(self.db, 'late'))
        self.assertEqual(session.manifest.source.revision_id, 'r1')
        self.assertEqual(query_probe(session, 'visit', 2).volume, Fraction(4))
        with self.assertRaisesRegex(ValueError, 'does not match'):
            compute_summary(get_revision(self.db, 'r2'), get_plan(self.db, 'p1'))
        with self.assertRaises(NotFoundError):
            publish(self.db, 'unbound', 'absent')
        with self.assertRaises(NotFoundError):
            export_bundle(self.db, 'unbound')

    def test_precommit_failure(self):
        previous = self.issue([[cell(0)]], [probe('visit', 0, 0)])

        def fail_before_commit():
            raise RuntimeError('interrupted before commit')

        with self.assertRaisesRegex(RuntimeError, 'interrupted before commit'):
            publish(self.db, 'interrupted', 'p1', before_commit=fail_before_commit)
        with self.assertRaises(NotFoundError):
            export_bundle(self.db, 'interrupted')
        self.assertEqual(export_bundle(self.db, 'e1'), previous)
        self.assertEqual(query_probe(previous, 'visit', 2).volume, Fraction(2))

    def test_reopen_and_retry(self):
        previous = self.issue([[cell(0)]], [probe('visit', 0, 0)])
        observations = []

        def observe_precommit_then_fail():
            with closing(sqlite3.connect(self.path)) as reader:
                observations.append(read_release(reader, 'e1'))
                with self.assertRaises(NotFoundError):
                    read_release(reader, 'retry')
            raise RuntimeError('stop at commit boundary')

        with self.assertRaisesRegex(RuntimeError, 'stop at commit boundary'):
            publish(self.db, 'retry', 'p1', before_commit=observe_precommit_then_fail)
        self.assertEqual(observations, [previous])
        self.disconnect()
        with closing(sqlite3.connect(self.path)) as reopened:
            with self.assertRaises(NotFoundError):
                read_release(reopened, 'retry')
            with self.assertRaises(NotFoundError):
                export_bundle(reopened, 'retry')
            self.assertEqual(export_bundle(reopened, 'e1'), previous)
            self.assertEqual(publish(reopened, 'retry', 'p1'), 'retry')
            retry_bundle = export_bundle(reopened, 'retry')
        self.assertEqual(open_session(retry_bundle).manifest.release_id, 'retry')
        self.assertEqual(query_probe(retry_bundle, 'visit', 2).volume, Fraction(2))

    def test_duplicate_id(self):
        previous = self.issue([[cell(0)]], [probe('old', 0, 0)])
        put_terrain(self.db, 'r2', [[cell(1, 3)]])
        freeze_plan(self.db, 'p2', 'r2', [probe('new', 0, 0)])
        with self.assertRaises(ConflictError):
            publish(self.db, 'e1', 'p2')
        stored = export_bundle(self.db, 'e1')
        self.assertEqual(stored, previous)
        self.assertEqual(open_session(stored).manifest.source.plan_id, 'p1')
        self.assertEqual(query_probe(stored, 'old', 2).volume, Fraction(2))
