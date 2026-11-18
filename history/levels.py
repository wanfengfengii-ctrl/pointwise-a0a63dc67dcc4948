from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from fractions import Fraction

from terrain.grid import GridCell


@dataclass(frozen=True, slots=True)
class ActivationLevel:
    height: Fraction
    cells: tuple[GridCell, ...]


def activation_levels(cells: Iterable[GridCell]) -> Iterator[ActivationLevel]:
    by_height: dict[Fraction, list[GridCell]] = {}
    for cell in cells:
        by_height.setdefault(cell.height, []).append(cell)
    for height in sorted(by_height):
        yield ActivationLevel(height, tuple(by_height[height]))
