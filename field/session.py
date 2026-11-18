from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from history.summary import BasinSummary
from release.bundle import decode_bundle
from release.manifest import ReleaseManifest


@dataclass(frozen=True, slots=True)
class FieldSession:
    manifest: ReleaseManifest
    summary: BasinSummary
    probe_nodes: Mapping[str, int]


def open_session(bundle: bytes) -> FieldSession:
    manifest, summary = decode_bundle(bundle)
    return FieldSession(manifest, summary, MappingProxyType(dict(summary.probe_nodes)))


def as_session(bundle_or_session: bytes | FieldSession) -> FieldSession:
    if isinstance(bundle_or_session, FieldSession):
        return bundle_or_session
    return open_session(bundle_or_session)
