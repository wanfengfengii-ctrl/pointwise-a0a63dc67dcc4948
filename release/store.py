from collections.abc import Callable
import sqlite3

from registry import ConflictError, NotFoundError, identifier, write_transaction


def initialize_release_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS releases (
            release_id TEXT NOT NULL PRIMARY KEY,
            bundle BLOB NOT NULL
        )
    ''')


def commit_release(
    connection: sqlite3.Connection,
    release_id: str,
    payload: bytes,
    *,
    before_commit: Callable[[], None] | None = None,
) -> str:
    release_id = identifier(release_id, 'release id')
    if type(payload) is not bytes or not payload:
        raise ValueError('a complete encoded bundle is required')
    with write_transaction(connection):
        inserted = connection.execute('''
            INSERT INTO releases (release_id, bundle) VALUES (?, ?)
            ON CONFLICT (release_id) DO NOTHING
        ''', (release_id, payload))
        if not inserted.rowcount:
            raise ConflictError(f'release {release_id!r} already exists')
        if before_commit is not None:
            before_commit()
    return release_id


def read_release(connection: sqlite3.Connection, release_id: str) -> bytes:
    release_id = identifier(release_id, 'release id')
    row = connection.execute('SELECT bundle FROM releases WHERE release_id = ?', (release_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'unknown release {release_id!r}')
    return row[0]
