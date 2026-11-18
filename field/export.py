from field.ledger import AuditLedger, build_ledger
from field.query import ProbeResult
from field.requests import parse_ledger_requests
from field.session import FieldSession, as_session
from terrain.codec import encode_rational


def format_result(result: ProbeResult) -> dict:
    if result.status == 'dry':
        return {'status': 'dry'}
    return {
        'status': 'wet',
        'basin_id': result.basin_id,
        'volume': encode_rational(result.volume),
    }


def format_ledger(ledger: AuditLedger) -> dict:
    rows = []
    for row in ledger.rows:
        rows.append({
            'position': row.position,
            'probe_id': row.request.probe_id,
            'water': encode_rational(row.request.water),
            'result': format_result(row.result),
        })
    return {'release_id': ledger.release_id, 'rows': rows}


def export_ledger(bundle_or_session: bytes | FieldSession, requests: object) -> dict:
    session = as_session(bundle_or_session)
    parsed = parse_ledger_requests(requests)
    return format_ledger(build_ledger(session, parsed))
