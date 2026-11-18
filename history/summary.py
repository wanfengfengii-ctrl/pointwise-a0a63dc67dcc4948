from dataclasses import dataclass
from fractions import Fraction

from history.moments import BasinMoments
from registry import identifier


@dataclass(frozen=True, slots=True)
class SummarySource:
    plan_id: str
    revision_id: str
    binding_digest: str

    def validate(self) -> None:
        identifier(self.plan_id, 'plan id')
        identifier(self.revision_id, 'revision id')
        digest = self.binding_digest
        if type(digest) is not str or len(digest) != 64 or any(
            character not in '0123456789abcdef' for character in digest
        ):
            raise ValueError('invalid probe binding digest')


@dataclass(frozen=True, slots=True)
class BasinEvent:
    level: Fraction
    basin_id: int
    introduced: BasinMoments
    predecessors: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BasinSummary:
    source: SummarySource
    events: tuple[BasinEvent, ...]
    probe_nodes: tuple[tuple[str, int], ...]


def validate_summary_structure(summary: BasinSummary) -> None:
    summary.source.validate()
    active_by_basin: dict[int, int] = {}
    last_key = None
    for index, event in enumerate(summary.events):
        if not isinstance(event.level, Fraction):
            raise ValueError('event level must be rational')
        if type(event.basin_id) is not int or event.basin_id < 0:
            raise ValueError('invalid basin number')
        key = (event.level, event.basin_id)
        if last_key is not None and key <= last_key:
            raise ValueError('events must be ordered by level and basin number')
        last_key = key
        introduced = event.introduced
        if not isinstance(introduced.area, Fraction) or not isinstance(introduced.height_moment, Fraction):
            raise ValueError('event moments must be rational')
        if introduced.area <= 0 or introduced.height_moment != event.level * introduced.area:
            raise ValueError('invalid moments for the cells introduced at an event')
        for previous in event.predecessors:
            if type(previous) is not int or not 0 <= previous < index:
                raise ValueError('event references an invalid predecessor')
            predecessor = summary.events[previous]
            if predecessor.level >= event.level or predecessor.basin_id < event.basin_id:
                raise ValueError('predecessor violates the level or basin boundary')
            if active_by_basin.get(predecessor.basin_id) != previous:
                raise ValueError('predecessor is no longer active')
            del active_by_basin[predecessor.basin_id]
        if event.basin_id in active_by_basin:
            raise ValueError('event duplicates an active basin number')
        active_by_basin[event.basin_id] = index

    seen = set()
    for name, event_index in summary.probe_nodes:
        identifier(name, 'probe id')
        if name in seen:
            raise ValueError(f'duplicate summarized probe {name!r}')
        if type(event_index) is not int or not 0 <= event_index < len(summary.events):
            raise ValueError('probe references an invalid event')
        seen.add(name)
