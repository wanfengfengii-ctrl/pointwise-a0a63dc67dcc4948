from dataclasses import dataclass
import sqlite3

from registry import ConflictError, NotFoundError, identifier, write_transaction
from terrain.codec import decode_grid_record, encode_grid_record
from terrain.grid import TerrainGrid
from terrain.validation import validate_terrain


@dataclass(frozen=True, slots=True)
class TerrainRevision:
    revision_id: str
    grid: TerrainGrid


def initialize_revisions(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS terrain_revisions (
            revision_id TEXT NOT NULL PRIMARY KEY,
            grid_record TEXT NOT NULL
        )
    ''')


def put_terrain(connection: sqlite3.Connection, revision_id: str, rows: object) -> str:
    revision_id = identifier(revision_id, 'revision id')
    payload = encode_grid_record(validate_terrain(rows))
    with write_transaction(connection):
        inserted = connection.execute('''
            INSERT INTO terrain_revisions (revision_id, grid_record) VALUES (?, ?)
            ON CONFLICT (revision_id) DO NOTHING
        ''', (revision_id, payload))
        if not inserted.rowcount:
            stored = _read_grid_record(connection, revision_id)
            if stored != payload:
                raise ConflictError(f'revision {revision_id!r} already has a different grid')
    return revision_id


def _read_grid_record(connection: sqlite3.Connection, revision_id: str) -> str:
    row = connection.execute(
        'SELECT grid_record FROM terrain_revisions WHERE revision_id = ?', (revision_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f'unknown revision {revision_id!r}')
    return row[0]


def get_revision(connection: sqlite3.Connection, revision_id: str) -> TerrainRevision:
    revision_id = identifier(revision_id, 'revision id')
    payload = _read_grid_record(connection, revision_id)
    return TerrainRevision(revision_id, decode_grid_record(payload))
