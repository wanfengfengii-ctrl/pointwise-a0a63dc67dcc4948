from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridShape:
    rows: int
    columns: int

    def __post_init__(self) -> None:
        if type(self.rows) is not int or type(self.columns) is not int:
            raise ValueError('grid dimensions must be integers')
        if self.rows <= 0 or self.columns <= 0:
            raise ValueError('grid dimensions must be positive')

    @property
    def cell_count(self) -> int:
        return self.rows * self.columns

    def contains(self, row: int, column: int) -> bool:
        return (
            type(row) is int
            and type(column) is int
            and 0 <= row < self.rows
            and 0 <= column < self.columns
        )


def cell_id_at(shape: GridShape, row: int, column: int) -> int:
    if not shape.contains(row, column):
        raise ValueError(f'coordinate ({row!r}, {column!r}) is outside the grid')
    return row * shape.columns + column


def coordinates_of(shape: GridShape, cell_id: int) -> tuple[int, int]:
    if type(cell_id) is not int or not 0 <= cell_id < shape.cell_count:
        raise ValueError(f'cell number {cell_id!r} is outside the grid')
    return divmod(cell_id, shape.columns)
