from contextlib import contextmanager
import json
import sqlite3


class NotFoundError(LookupError):
    """A requested fixed record or probe is unknown."""


class ConflictError(ValueError):
    """A fixed identifier already has a conflicting registration."""


def identifier(value: object, role: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f'{role} must be a nonempty trimmed string')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError(f'{role} must be valid Unicode') from exc
    return value


def require_fields(value: object, *names: str) -> dict:
    if type(value) is not dict or value.keys() != set(names):
        raise ValueError(f'expected object with fields {", ".join(names)}')
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f'duplicate JSON field {key!r}')
        record[key] = value
    return record


def load_record(text: str) -> object:
    return json.loads(text, object_pairs_hook=_unique_object)


def dump_record(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def write_transaction(connection: sqlite3.Connection):
    if connection.in_transaction:
        raise ValueError('registry writes require a connection with no active transaction')
    connection.execute('BEGIN IMMEDIATE')
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
