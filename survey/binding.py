from survey.probes import BoundProbe, ProbeRequest
from terrain.grid import TerrainGrid


def bind_probes(
    grid: TerrainGrid, requests: tuple[ProbeRequest, ...]
) -> tuple[BoundProbe, ...]:
    bound = []
    for request in requests:
        try:
            cell = grid.cell_at(request.row, request.column)
        except ValueError as exc:
            raise ValueError(f'probe {request.probe_id!r}: {exc}') from exc
        if cell is None:
            raise ValueError(f'probe {request.probe_id!r} is on a masked cell')
        bound.append(BoundProbe(request.probe_id, cell.cell_id))
    return tuple(bound)
