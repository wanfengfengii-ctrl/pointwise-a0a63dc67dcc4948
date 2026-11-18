from history.moments import BasinMoments
from history.summary import BasinEvent, BasinSummary, validate_summary_structure
from registry import require_fields
from release.manifest import decode_source, encode_source
from terrain.codec import decode_rational_record, encode_rational


def encode_summary(summary: BasinSummary) -> dict:
    validate_summary_structure(summary)
    events = []
    for event in summary.events:
        events.append({
            'level': encode_rational(event.level),
            'basin_id': event.basin_id,
            'area': encode_rational(event.introduced.area),
            'height_moment': encode_rational(event.introduced.height_moment),
            'predecessors': list(event.predecessors),
        })
    return {
        'source': encode_source(summary.source),
        'events': events,
        'probe_nodes': [[name, event_index] for name, event_index in summary.probe_nodes],
    }


def decode_summary(record: object) -> BasinSummary:
    fields = require_fields(record, 'source', 'events', 'probe_nodes')
    source = decode_source(fields['source'])
    if type(fields['events']) is not list or type(fields['probe_nodes']) is not list:
        raise ValueError('summary requires event and probe arrays')
    events = []
    for raw in fields['events']:
        event = require_fields(raw, 'level', 'basin_id', 'area', 'height_moment', 'predecessors')
        if type(event['predecessors']) is not list:
            raise ValueError('event predecessors must be an array')
        events.append(BasinEvent(
            decode_rational_record(event['level']),
            event['basin_id'],
            BasinMoments(
                decode_rational_record(event['area']),
                decode_rational_record(event['height_moment']),
            ),
            tuple(event['predecessors']),
        ))
    probes = []
    for item in fields['probe_nodes']:
        if type(item) is not list or len(item) != 2:
            raise ValueError('invalid summary probe reference')
        probes.append((item[0], item[1]))
    summary = BasinSummary(source, tuple(events), tuple(probes))
    validate_summary_structure(summary)
    return summary
