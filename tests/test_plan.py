from contextlib import closing
from fractions import Fraction
import sqlite3

from minewater import initialize
from registry import ConflictError, NotFoundError
from survey.catalog import get_plan
from survey.plans import freeze_plan
from survey.probes import BoundProbe
from terrain.revisions import get_revision, put_terrain
from tests.fixtures import RegistryTestCase, cell, probe


class PlanTests(RegistryTestCase):
    def test_bind_revision(self):
        self.assertEqual(put_terrain(self.db, 'r1', [[cell(0), cell(1, 2)]]), 'r1')
        self.assertEqual(freeze_plan(self.db, 'p1', 'r1', [probe('right', 0, 1)]), 'p1')
        plan = get_plan(self.db, 'p1')
        self.assertEqual(plan.revision_id, 'r1')
        self.assertEqual(plan.probes, (BoundProbe('right', 1),))
        self.assertEqual(get_revision(self.db, 'r1').grid.cell_at(0, 1).area, Fraction(2))

    def test_row_major_sparse(self):
        rows = [[cell(0), None, cell(1)], [None, None, cell(-1, '3/2')]]
        put_terrain(self.db, 'sparse', rows)
        freeze_plan(self.db, 'p1', 'sparse', [probe('lower', 1, 2), probe('upper', 0, 2)])
        grid = get_revision(self.db, 'sparse').grid
        self.assertEqual([item.cell_id for item in grid.valid_cells()], [0, 2, 5])
        self.assertIsNone(grid.cell_at(1, 0))
        self.assertEqual(grid.cell_at(1, 2).area, Fraction(3, 2))
        self.assertEqual(get_plan(self.db, 'p1').probes, (BoundProbe('lower', 5), BoundProbe('upper', 2)))

    def test_repeat_initialization(self):
        put_terrain(self.db, 'r1', [[cell('1/2')]])
        freeze_plan(self.db, 'p1', 'r1', [probe('visit', 0, 0)])
        initialize(self.db)
        put_terrain(self.db, 'crew-r2', [[cell('-3/7', '2/3')]])
        self.disconnect()
        with closing(sqlite3.connect(self.path)) as reopened:
            initialize(reopened)
            initialize(reopened)
            self.assertEqual(get_plan(reopened, 'p1').revision_id, 'r1')
            self.assertEqual(get_revision(reopened, 'r1').grid.cell_at(0, 0).height, Fraction(1, 2))
            crew_cell = get_revision(reopened, 'crew-r2').grid.cell_at(0, 0)
            self.assertEqual((crew_cell.height, crew_cell.area), (Fraction(-3, 7), Fraction(2, 3)))

    def test_revision_replay_and_conflict(self):
        put_terrain(self.db, 'fixed', [[cell('1/2', '4/3')]])
        self.assertEqual(put_terrain(self.db, 'fixed', [[cell([2, 4], [8, 6])]]), 'fixed')
        with self.assertRaises(ConflictError):
            put_terrain(self.db, 'fixed', [[cell('3/2', '4/3')]])
        self.assertEqual(get_revision(self.db, 'fixed').grid.cell_at(0, 0).height, Fraction(1, 2))

    def test_zero_area(self):
        put_terrain(self.db, 'good', [[cell(0)]])
        with self.assertRaisesRegex(ValueError, 'area must be positive'):
            put_terrain(self.db, 'bad', [[cell(1, 0)]])
        with self.assertRaises(NotFoundError):
            get_revision(self.db, 'bad')
        self.assertEqual(freeze_plan(self.db, 'p1', 'good', [probe('safe', 0, 0)]), 'p1')

    def test_invalid_terrain_encodings(self):
        for rows in ([], [[]], [[cell(0)], [cell(1), None]], [[{'height': 0}]],
                     [[cell('1/0')]], [[cell(True)]], [[cell(1, -1)]], [[cell(1, 0.5)]]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    put_terrain(self.db, 'invalid', rows)
                with self.assertRaises(NotFoundError):
                    get_revision(self.db, 'invalid')

    def test_probe_on_masked_cell(self):
        put_terrain(self.db, 'r1', [[None, cell(0)]])
        with self.assertRaisesRegex(ValueError, 'masked cell'):
            freeze_plan(self.db, 'p1', 'r1', [probe('check', 0, 0)])
        with self.assertRaises(NotFoundError):
            get_plan(self.db, 'p1')
        self.assertEqual(freeze_plan(self.db, 'p1', 'r1', [probe('check', 0, 1)]), 'p1')
        self.assertEqual(get_plan(self.db, 'p1').probes, (BoundProbe('check', 1),))

    def test_invalid_binding(self):
        put_terrain(self.db, 'r1', [[cell(0), cell(1)]])
        with self.assertRaises(NotFoundError):
            freeze_plan(self.db, 'missing-parent', 'unknown', [probe('check', 0, 0)])
        with self.assertRaisesRegex(ValueError, 'duplicate probe'):
            freeze_plan(self.db, 'repeat', 'r1', [probe('check', 0, 0), probe('check', 0, 1)])
        with self.assertRaisesRegex(ValueError, 'outside the grid'):
            freeze_plan(self.db, 'outside', 'r1', [probe('check', 0, 2)])
        for invalid in ('missing-parent', 'repeat', 'outside'):
            with self.assertRaises(NotFoundError):
                get_plan(self.db, invalid)
        freeze_plan(self.db, 'repeat', 'r1', [probe('first', 0, 0), probe('alias', 0, 0)])
        fixed = get_plan(self.db, 'repeat')
        self.assertEqual(fixed.probes, (BoundProbe('first', 0), BoundProbe('alias', 0)))
        with self.assertRaises(ConflictError):
            freeze_plan(self.db, 'repeat', 'r1', [probe('first', 0, 1)])
        self.assertEqual(get_plan(self.db, 'repeat'), fixed)
