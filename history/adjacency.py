from collections.abc import Collection, Iterator

from terrain.coordinates import GridShape, cell_id_at, coordinates_of


def orthogonal_neighbors(shape: GridShape, cell_id: int) -> Iterator[int]:
    row, column = coordinates_of(shape, cell_id)
    for other_row, other_column in (
        (row - 1, column), (row, column - 1), (row, column + 1), (row + 1, column)
    ):
        if shape.contains(other_row, other_column):
            yield cell_id_at(shape, other_row, other_column)


def wet_components(shape: GridShape, wet_cells: Collection[int]) -> Iterator[frozenset[int]]:
    remaining = set(wet_cells)
    for seed in sorted(remaining):
        if seed not in remaining:
            continue
        remaining.remove(seed)
        pending = [seed]
        reached = {seed}
        while pending:
            current = pending.pop()
            for neighbor in orthogonal_neighbors(shape, current):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    reached.add(neighbor)
                    pending.append(neighbor)
        yield frozenset(reached)
