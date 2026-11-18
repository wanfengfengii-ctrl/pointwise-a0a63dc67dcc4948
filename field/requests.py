from dataclasses import dataclass
from fractions import Fraction

from registry import identifier, require_fields
from terrain.codec import decode_rational


@dataclass(frozen=True, slots=True)
class ProbeWaterRequest:
    probe_id: str
    water: Fraction


def parse_probe_request(probe_id: object, water: object) -> ProbeWaterRequest:
    return ProbeWaterRequest(identifier(probe_id, 'probe id'), decode_rational(water))


def parse_ledger_requests(records: object) -> tuple[ProbeWaterRequest, ...]:
    if type(records) not in (list, tuple):
        raise ValueError('ledger requests must be an ordered array')
    requests = []
    for position, item in enumerate(records):
        try:
            fields = require_fields(item, 'probe_id', 'water')
            requests.append(parse_probe_request(fields['probe_id'], fields['water']))
        except ValueError as exc:
            raise ValueError(f'ledger row {position}: {exc}') from exc
    return tuple(requests)
