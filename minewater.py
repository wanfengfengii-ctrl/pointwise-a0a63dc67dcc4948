import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

from field.export import export_ledger, format_result
from field.query import query_probe
from registry import dump_record, load_record, write_transaction
from release.bundle import export_bundle
from release.publish import publish
from release.store import initialize_release_store
from survey.catalog import initialize_plan_catalog
from survey.plans import freeze_plan
from terrain.revisions import initialize_revisions, put_terrain


def initialize(connection: sqlite3.Connection) -> None:
    with write_transaction(connection):
        initialize_revisions(connection)
        initialize_plan_catalog(connection)
        initialize_release_store(connection)


def read_input(path: Path) -> object:
    return load_record(path.read_text(encoding='utf-8'))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='minewater', description='Fixed mine drainage inspection releases')
    commands = parser.add_subparsers(dest='command', required=True)
    initial = commands.add_parser('init', help='initialize a survey database')
    initial.add_argument('database', type=Path)
    terrain = commands.add_parser('terrain', help='register a terrain revision')
    terrain.add_argument('database', type=Path)
    terrain.add_argument('revision_id')
    terrain.add_argument('grid', type=Path)
    freeze = commands.add_parser('freeze', help='freeze inspection points')
    freeze.add_argument('database', type=Path)
    freeze.add_argument('plan_id')
    freeze.add_argument('revision_id')
    freeze.add_argument('probes', type=Path)
    issue = commands.add_parser('publish', help='publish a fixed release')
    issue.add_argument('database', type=Path)
    issue.add_argument('release_id')
    issue.add_argument('plan_id')
    bundle = commands.add_parser('bundle', help='write the fixed bundle to stdout')
    bundle.add_argument('database', type=Path)
    bundle.add_argument('release_id')
    probe = commands.add_parser('probe', help='query a point from a bundle')
    probe.add_argument('bundle', type=Path)
    probe.add_argument('probe_id')
    probe.add_argument('water')
    ledger = commands.add_parser('ledger', help='export ordered ledger rows from a bundle')
    ledger.add_argument('bundle', type=Path)
    ledger.add_argument('requests', type=Path)
    return parser


def _handle_registry(args: argparse.Namespace) -> None:
    with closing(sqlite3.connect(args.database)) as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        if args.command == 'init':
            initialize(connection)
        elif args.command == 'terrain':
            print(put_terrain(connection, args.revision_id, read_input(args.grid)))
        elif args.command == 'freeze':
            print(freeze_plan(connection, args.plan_id, args.revision_id, read_input(args.probes)))
        elif args.command == 'publish':
            print(publish(connection, args.release_id, args.plan_id))
        elif args.command == 'bundle':
            sys.stdout.buffer.write(export_bundle(connection, args.release_id))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'probe':
            result = query_probe(args.bundle.read_bytes(), args.probe_id, args.water)
            print(dump_record(format_result(result)))
        elif args.command == 'ledger':
            ledger = export_ledger(args.bundle.read_bytes(), read_input(args.requests))
            print(dump_record(ledger))
        else:
            _handle_registry(args)
    except (OSError, ValueError, LookupError, sqlite3.Error) as exc:
        parser.exit(2, f'minewater: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
