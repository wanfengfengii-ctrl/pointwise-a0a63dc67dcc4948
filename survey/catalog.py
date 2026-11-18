from dataclasses import dataclass
import sqlite3

from registry import ConflictError, NotFoundError, dump_record, identifier, load_record, require_fields, write_transaction
from survey.probes import BoundProbe, validate_bound_probes


@dataclass(frozen=True, slots=True)
class InspectionPlan:
    plan_id: str
    revision_id: str
    probes: tuple[BoundProbe, ...]


def initialize_plan_catalog(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS inspection_plans (
            plan_id TEXT NOT NULL PRIMARY KEY,
            revision_id TEXT NOT NULL REFERENCES terrain_revisions (revision_id),
            probe_record TEXT NOT NULL
        )
    ''')


def _read_plan_row(connection: sqlite3.Connection, plan_id: str):
    row = connection.execute('''
        SELECT revision_id, probe_record FROM inspection_plans WHERE plan_id = ?
    ''', (plan_id,)).fetchone()
    if row is None:
        raise NotFoundError(f'unknown plan {plan_id!r}')
    return row


def save_plan(connection: sqlite3.Connection, plan: InspectionPlan) -> str:
    plan_id = identifier(plan.plan_id, 'plan id')
    revision_id = identifier(plan.revision_id, 'revision id')
    validate_bound_probes(plan.probes)
    payload = dump_record([
        {'probe_id': probe.probe_id, 'cell_id': probe.cell_id} for probe in plan.probes
    ])
    with write_transaction(connection):
        inserted = connection.execute('''
            INSERT INTO inspection_plans (plan_id, revision_id, probe_record) VALUES (?, ?, ?)
            ON CONFLICT (plan_id) DO NOTHING
        ''', (plan_id, revision_id, payload))
        if not inserted.rowcount:
            row = _read_plan_row(connection, plan_id)
            if (row[0], row[1]) != (revision_id, payload):
                raise ConflictError(f'plan {plan_id!r} already has a different binding')
    return plan_id


def get_plan(connection: sqlite3.Connection, plan_id: str) -> InspectionPlan:
    plan_id = identifier(plan_id, 'plan id')
    row = _read_plan_row(connection, plan_id)
    records = load_record(row[1])
    if type(records) is not list:
        raise ValueError('invalid stored probe list')
    probes = []
    for record in records:
        fields = require_fields(record, 'probe_id', 'cell_id')
        probes.append(BoundProbe(fields['probe_id'], fields['cell_id']))
    bound = tuple(probes)
    validate_bound_probes(bound)
    return InspectionPlan(plan_id, identifier(row[0], 'revision id'), bound)
