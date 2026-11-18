import sqlite3

from history.summary import BasinSummary
from registry import dump_record, load_record, require_fields
from release.manifest import ReleaseManifest, check_summary_binding, decode_manifest, encode_manifest
from release.store import read_release
from release.summary_codec import decode_summary, encode_summary


class BundleError(ValueError):
    """The supplied bundle cannot be opened as a fixed release."""


def encode_bundle(manifest: ReleaseManifest, summary: BasinSummary) -> bytes:
    check_summary_binding(manifest, summary)
    record = {
        'version': 1,
        'manifest': encode_manifest(manifest),
        'summary': encode_summary(summary),
    }
    return dump_record(record).encode('ascii')


def decode_bundle(payload: bytes) -> tuple[ReleaseManifest, BasinSummary]:
    if type(payload) is not bytes:
        raise BundleError('bundle must be supplied as bytes')
    try:
        fields = require_fields(load_record(payload.decode('utf-8')), 'version', 'manifest', 'summary')
        if type(fields['version']) is not int or fields['version'] != 1:
            raise ValueError('unsupported bundle version')
        manifest = decode_manifest(fields['manifest'])
        summary = decode_summary(fields['summary'])
        check_summary_binding(manifest, summary)
    except (ValueError, RecursionError) as exc:
        raise BundleError(f'unreadable bundle: {exc}') from exc
    return manifest, summary


def export_bundle(connection: sqlite3.Connection, release_id: str) -> bytes:
    return read_release(connection, release_id)
