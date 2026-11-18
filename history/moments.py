from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from terrain.grid import GridCell


@dataclass(frozen=True, slots=True)
class BasinMoments:
    area: Fraction
    height_moment: Fraction

    def volume_at(self, water: Fraction) -> Fraction:
        return water * self.area - self.height_moment


def measure_cells(cells: Iterable[GridCell]) -> BasinMoments:
    area = Fraction(0)
    height_moment = Fraction(0)
    for cell in cells:
        area += cell.area
        height_moment += cell.area * cell.height
    return BasinMoments(area, height_moment)
