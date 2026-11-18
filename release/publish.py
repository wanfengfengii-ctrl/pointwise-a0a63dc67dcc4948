from collections.abc import Callable
import sqlite3

from history.basins import compute_summary
from registry import identifier
from release.bundle import encode_bundle
from release.manifest import build_manifest
from release.store import commit_release
from survey.catalog import get_plan
from terrain.revisions import get_revision


def publish(
    connection: sqlite3.Connection,
    release_id: str,
    plan_id: str,
    *,
    before_commit: Callable[[], None] | None = None,
) -> str:
    release_id = identifier(release_id, 'release id')
    plan = get_plan(connection, plan_id)
    revision = get_revision(connection, plan.revision_id)
    summary = compute_summary(revision, plan)
    manifest = build_manifest(release_id, plan, revision, summary)
    payload = encode_bundle(manifest, summary)
    return commit_release(connection, release_id, payload, before_commit=before_commit)
