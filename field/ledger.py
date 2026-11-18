from dataclasses import dataclass

from field.query import ProbeResult, evaluate_probe
from field.requests import ProbeWaterRequest
from field.session import FieldSession
from registry import NotFoundError


@dataclass(frozen=True, slots=True)
class LedgerRow:
    position: int
    request: ProbeWaterRequest
    result: ProbeResult


@dataclass(frozen=True, slots=True)
class AuditLedger:
    release_id: str
    rows: tuple[LedgerRow, ...]


def build_ledger(session: FieldSession, requests: tuple[ProbeWaterRequest, ...]) -> AuditLedger:
    rows = []
    for position, request in enumerate(requests):
        try:
            result = evaluate_probe(session, request)
        except NotFoundError as exc:
            raise NotFoundError(f'ledger row {position}: {exc}') from exc
        rows.append(LedgerRow(position, request, result))
    return AuditLedger(session.manifest.release_id, tuple(rows))
