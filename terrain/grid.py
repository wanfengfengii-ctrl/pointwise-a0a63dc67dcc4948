from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from terrain.coordinates import GridShape, cell_id_at


@dataclass(frozen=True, slots=True)
class GridCell:
    cell_id: int
    height: Fraction
    area: Fraction


@dataclass(frozen=True, slots=True)
class TerrainGrid:
    shape: GridShape
    cells: tuple[GridCell | None, ...]

    def __post_init__(self) -> None:
        if type(self.cells) is not tuple or len(self.cells) != self.shape.cell_count:
            raise ValueError('grid cells must fill the fixed rectangular shape')
        for cell_id, cell in enumerate(self.cells):
            if cell is not None and (not isinstance(cell, GridCell) or cell.cell_id != cell_id):
                raise ValueError('grid cells must have their fixed row-major numbers')

    def cell_at(self, row: int, column: int) -> GridCell | None:
        return self.cells[cell_id_at(self.shape, row, column)]

    def valid_cells(self) -> Iterator[GridCell]:
        for cell in self.cells:
            if cell is not None:
                yield cell
