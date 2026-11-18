from dataclasses import dataclass

from history.summary import BasinSummary, SummarySource
from registry import identifier, require_fields
from survey.catalog import InspectionPlan
from survey.probes import binding_fingerprint
from terrain.revisions import TerrainRevision


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    release_id: str
    source: SummarySource
    probe_ids: tuple[str, ...]


def build_manifest(
    release_id: str, plan: InspectionPlan, revision: TerrainRevision, summary: BasinSummary
) -> ReleaseManifest:
    release_id = identifier(release_id, 'release id')
    if plan.revision_id != revision.revision_id:
        raise ValueError('manifest revision does not match the fixed plan')
    source = SummarySource(plan.plan_id, revision.revision_id, binding_fingerprint(plan.probes))
    manifest = ReleaseManifest(release_id, source, tuple(probe.probe_id for probe in plan.probes))
    check_summary_binding(manifest, summary)
    return manifest


def check_summary_binding(manifest: ReleaseManifest, summary: BasinSummary) -> None:
    if manifest.source != summary.source:
        raise ValueError('manifest and summary have different sources')
    names = tuple(name for name, _ in summary.probe_nodes)
    if manifest.probe_ids != names:
        raise ValueError('manifest and summary have different probe lists')


def encode_source(source: SummarySource) -> dict:
    return {'plan_id': source.plan_id, 'revision_id': source.revision_id, 'binding_digest': source.binding_digest}


def decode_source(record: object) -> SummarySource:
    fields = require_fields(record, 'plan_id', 'revision_id', 'binding_digest')
    source = SummarySource(fields['plan_id'], fields['revision_id'], fields['binding_digest'])
    source.validate()
    return source


def encode_manifest(manifest: ReleaseManifest) -> dict:
    return {
        'release_id': manifest.release_id,
        'source': encode_source(manifest.source),
        'probe_ids': list(manifest.probe_ids),
    }


def decode_manifest(record: object) -> ReleaseManifest:
    fields = require_fields(record, 'release_id', 'source', 'probe_ids')
    release_id = identifier(fields['release_id'], 'release id')
    source = decode_source(fields['source'])
    if type(fields['probe_ids']) is not list:
        raise ValueError('manifest probe list must be an array')
    names = tuple(identifier(name, 'probe id') for name in fields['probe_ids'])
    if len(set(names)) != len(names):
        raise ValueError('manifest probe names must be unique')
    return ReleaseManifest(release_id, source, names)
