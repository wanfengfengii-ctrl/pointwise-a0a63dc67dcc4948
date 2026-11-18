from registry import require_fields
from terrain.codec import decode_rational
from terrain.coordinates import GridShape, cell_id_at
from terrain.grid import GridCell, TerrainGrid


def validate_terrain(rows: object) -> TerrainGrid:
    if type(rows) not in (list, tuple) or not rows:
        raise ValueError('terrain must have at least one row')
    first = rows[0]
    if type(first) not in (list, tuple) or not first:
        raise ValueError('terrain must have at least one column')
    shape = GridShape(len(rows), len(first))
    cells = []
    for row_index, row in enumerate(rows):
        if type(row) not in (list, tuple) or len(row) != shape.columns:
            raise ValueError(f'row {row_index} does not match the rectangular grid')
        for column, raw_cell in enumerate(row):
            if raw_cell is None:
                cells.append(None)
                continue
            cell_id = cell_id_at(shape, row_index, column)
            try:
                record = require_fields(raw_cell, 'height', 'area')
                height = decode_rational(record['height'])
                area = decode_rational(record['area'])
                if area <= 0:
                    raise ValueError('area must be positive')
            except ValueError as exc:
                raise ValueError(f'cell {cell_id}: {exc}') from exc
            cells.append(GridCell(cell_id, height, area))
    return TerrainGrid(shape, tuple(cells))
