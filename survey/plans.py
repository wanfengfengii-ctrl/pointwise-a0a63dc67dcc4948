import sqlite3

from registry import identifier
from survey.binding import bind_probes
from survey.catalog import InspectionPlan, save_plan
from survey.probes import validate_probe_requests
from terrain.revisions import get_revision


def freeze_plan(
    connection: sqlite3.Connection, plan_id: str, revision_id: str, probes: object
) -> str:
    plan_id = identifier(plan_id, 'plan id')
    revision = get_revision(connection, revision_id)
    requests = validate_probe_requests(probes)
    fixed_points = bind_probes(revision.grid, requests)
    plan = InspectionPlan(plan_id, revision.revision_id, fixed_points)
    return save_plan(connection, plan)
