from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from minewater import initialize, read_input
from release.bundle import export_bundle
from release.publish import publish
from survey.plans import freeze_plan
from terrain.revisions import put_terrain


SAMPLES = Path(__file__).resolve().parents[1] / 'samples'


def cell(height, area=1):
    return {'height': height, 'area': area}


def probe(name, row, column):
    return {'probe_id': name, 'row': row, 'column': column}


def reading(name, water):
    return {'probe_id': name, 'water': water}


def saddle_inputs():
    return read_input(SAMPLES / 'saddles.json'), read_input(SAMPLES / 'probes.json')


class RegistryTestCase(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory(prefix='minewater-test-'))
        self.path = Path(directory) / 'survey.sqlite'
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.disconnect)
        initialize(self.db)

    def disconnect(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def issue(self, rows, probes, *, revision='r1', plan='p1', release='e1'):
        put_terrain(self.db, revision, rows)
        freeze_plan(self.db, plan, revision, probes)
        publish(self.db, release, plan)
        return export_bundle(self.db, release)
