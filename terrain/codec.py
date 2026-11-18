from fractions import Fraction

from registry import dump_record, load_record, require_fields
from terrain.coordinates import GridShape
from terrain.grid import GridCell, TerrainGrid


def decode_rational(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if type(value) is str:
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid rational number') from exc
    if type(value) in (list, tuple) and len(value) == 2:
        numerator, denominator = value
        if type(numerator) is int and type(denominator) is int and denominator > 0:
            return Fraction(numerator, denominator)
    raise ValueError('expected an integer, rational string, or positive-denominator integer pair')


def encode_rational(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def decode_rational_record(value: object) -> Fraction:
    if type(value) is not list:
        raise ValueError('stored rational value must be a canonical integer pair')
    rational = decode_rational(value)
    if encode_rational(rational) != value:
        raise ValueError('stored rational value must be reduced')
    return rational


def encode_grid_record(grid: TerrainGrid) -> str:
    cells = []
    for cell in grid.cells:
        if cell is None:
            cells.append(None)
        else:
            cells.append([encode_rational(cell.height), encode_rational(cell.area)])
    return dump_record({'rows': grid.shape.rows, 'columns': grid.shape.columns, 'cells': cells})


def decode_grid_record(payload: str) -> TerrainGrid:
    record = require_fields(load_record(payload), 'rows', 'columns', 'cells')
    shape = GridShape(record['rows'], record['columns'])
    raw_cells = record['cells']
    if type(raw_cells) is not list or len(raw_cells) != shape.cell_count:
        raise ValueError('invalid stored grid dimensions')
    cells = []
    for cell_id, raw in enumerate(raw_cells):
        if raw is None:
            cells.append(None)
            continue
        if type(raw) is not list or len(raw) != 2:
            raise ValueError('invalid stored grid cell')
        height = decode_rational_record(raw[0])
        area = decode_rational_record(raw[1])
        if area <= 0:
            raise ValueError(f'stored cell {cell_id} has nonpositive area')
        cells.append(GridCell(cell_id, height, area))
    return TerrainGrid(shape, tuple(cells))
