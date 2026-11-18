from dataclasses import dataclass
from hashlib import sha256

from registry import dump_record, identifier, require_fields


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    probe_id: str
    row: int
    column: int


@dataclass(frozen=True, slots=True)
class BoundProbe:
    probe_id: str
    cell_id: int


def validate_probe_requests(records: object) -> tuple[ProbeRequest, ...]:
    if type(records) not in (list, tuple):
        raise ValueError('probes must be an ordered array')
    requests = []
    seen = set()
    for raw in records:
        if isinstance(raw, ProbeRequest):
            request = raw
        else:
            record = require_fields(raw, 'probe_id', 'row', 'column')
            request = ProbeRequest(record['probe_id'], record['row'], record['column'])
        name = identifier(request.probe_id, 'probe id')
        if name in seen:
            raise ValueError(f'duplicate probe {name!r}')
        if type(request.row) is not int or type(request.column) is not int:
            raise ValueError(f'coordinates of probe {name!r} must be integers')
        seen.add(name)
        requests.append(request)
    return tuple(requests)


def validate_bound_probes(probes: tuple[BoundProbe, ...]) -> None:
    seen = set()
    for probe in probes:
        if not isinstance(probe, BoundProbe):
            raise ValueError('plan requires bound probes')
        name = identifier(probe.probe_id, 'probe id')
        if name in seen:
            raise ValueError(f'duplicate bound probe {name!r}')
        if type(probe.cell_id) is not int or probe.cell_id < 0:
            raise ValueError(f'invalid fixed cell number for {name!r}')
        seen.add(name)


def binding_fingerprint(probes: tuple[BoundProbe, ...]) -> str:
    record = [[probe.probe_id, probe.cell_id] for probe in probes]
    return sha256(dump_record(record).encode('ascii')).hexdigest()
