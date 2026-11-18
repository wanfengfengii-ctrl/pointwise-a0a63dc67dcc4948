from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from field.export import export_ledger, format_result
from field.query import query_probe
from field.session import open_session
from minewater import initialize, read_input
from registry import dump_record
from release.bundle import export_bundle
from release.publish import publish
from survey.plans import freeze_plan
from terrain.revisions import put_terrain


def main() -> None:
    samples = Path(__file__).resolve().parent / 'samples'
    with TemporaryDirectory(prefix='minewater-demo-') as directory:
        path = Path(directory) / 'survey.sqlite'
        with closing(sqlite3.connect(path)) as connection:
            initialize(connection)
            revision = put_terrain(connection, 'demo-section', read_input(samples / 'saddles.json'))
            plan = freeze_plan(connection, 'demo-shift', revision, read_input(samples / 'probes.json'))
            release = publish(connection, 'demo-edition', plan)
            bundle = export_bundle(connection, release)

    session = open_session(bundle)
    names = ('west', 'center', 'east', 'west-saddle', 'east-saddle')
    points = {name: format_result(query_probe(session, name, 2)) for name in names}
    requests = [
        {'probe_id': name, 'water': water}
        for water in (2, '5/2')
        for name in names
    ]
    print(dump_record({
        'revision_id': session.manifest.source.revision_id,
        'plan_id': session.manifest.source.plan_id,
        'points_at_2m': points,
        'ledger': export_ledger(session, requests),
    }))


if __name__ == '__main__':
    main()
