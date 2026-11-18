from collections.abc import Iterable

from history.adjacency import wet_components
from history.levels import ActivationLevel, activation_levels
from history.moments import measure_cells
from history.summary import BasinEvent, BasinSummary, SummarySource, validate_summary_structure
from survey.catalog import InspectionPlan
from survey.probes import BoundProbe, binding_fingerprint
from terrain.coordinates import GridShape
from terrain.revisions import TerrainRevision


def build_history(
    shape: GridShape,
    source: SummarySource,
    probes: tuple[BoundProbe, ...],
    levels: Iterable[ActivationLevel],
) -> BasinSummary:
    wet: set[int] = set()
    # Each wet cell belongs to exactly one currently active partition.  A
    # partition is identified by the event that produced its latest head.
    owners: dict[int, int] = {}
    probe_cells = {probe.cell_id for probe in probes}
    probe_nodes: dict[int, int] = {}
    events: list[BasinEvent] = []

    for batch in levels:
        added = {cell.cell_id: cell for cell in batch.cells}
        wet.update(added)
        for component in wet_components(shape, wet):
            introduced = component.intersection(added)
            if not introduced:
                continue
            basin_id = min(component)
            # Every still-active partition absorbed by this component keeps
            # its own event as a predecessor; none may be dropped, otherwise
            # its cells vanish from the merged basin's volume.
            previous = tuple(sorted({
                owners[cell_id] for cell_id in component if cell_id not in introduced
            }))
            event_index = len(events)
            events.append(BasinEvent(
                batch.height,
                basin_id,
                measure_cells(added[cell_id] for cell_id in sorted(introduced)),
                previous,
            ))
            for cell_id in component:
                owners[cell_id] = event_index
            for cell_id in introduced.intersection(probe_cells):
                probe_nodes[cell_id] = event_index

    roots = []
    for probe in probes:
        if probe.cell_id not in probe_nodes:
            raise ValueError(f"probe {probe.probe_id!r} has no activation event")
        roots.append((probe.probe_id, probe_nodes[probe.cell_id]))
    summary = BasinSummary(source, tuple(events), tuple(roots))
    validate_summary_structure(summary)
    return summary


def compute_summary(revision: TerrainRevision, plan: InspectionPlan) -> BasinSummary:
    if revision.revision_id != plan.revision_id:
        raise ValueError("calculation revision does not match the fixed plan")
    source = SummarySource(plan.plan_id, revision.revision_id, binding_fingerprint(plan.probes))
    return build_history(
        revision.grid.shape, source, plan.probes, activation_levels(revision.grid.valid_cells())
    )
