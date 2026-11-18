from dataclasses import dataclass
from fractions import Fraction

from field.requests import ProbeWaterRequest, parse_probe_request
from field.session import FieldSession, as_session
from history.moments import BasinMoments
from registry import NotFoundError


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: str
    basin_id: int | None = None
    volume: Fraction | None = None


def evaluate_probe(session: FieldSession, request: ProbeWaterRequest) -> ProbeResult:
    anchor = session.probe_nodes.get(request.probe_id)
    if anchor is None:
        raise NotFoundError(f'unknown probe {request.probe_id!r}')
    events = session.summary.events
    if events[anchor].level >= request.water:
        return ProbeResult('dry')

    selected = anchor
    for event_index in range(anchor + 1, len(events)):
        event = events[event_index]
        if event.level >= request.water:
            break
        if selected in event.predecessors:
            selected = event_index

    current = selected
    area = Fraction(0)
    height_moment = Fraction(0)
    pending = [current]
    visited: set[int] = set()
    while pending:
        event_index = pending.pop()
        if event_index in visited:
            continue
        visited.add(event_index)
        event = events[event_index]
        area += event.introduced.area
        height_moment += event.introduced.height_moment
        pending.extend(event.predecessors)
    volume = BasinMoments(area, height_moment).volume_at(request.water)
    return ProbeResult('wet', events[selected].basin_id, volume)


def query_probe(
    bundle_or_session: bytes | FieldSession, probe_id: str, water: object
) -> ProbeResult:
    session = as_session(bundle_or_session)
    return evaluate_probe(session, parse_probe_request(probe_id, water))
