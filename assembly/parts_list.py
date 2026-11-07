"""The parts list: derived from an assembly evaluation, never edited by hand.

Each row is one kind of thing to buy or print, with its quantity and the assembly instances
it covers, so the list cannot drift from the assembly it came from: `source_sha256` names
the assembly file the rows were derived from.
"""
import csv
import io
import json
from pathlib import Path

COLUMNS = ('Category', 'Item', 'Quantity', 'Specification', 'Source', 'Instances')
ORDER = ('Printed part', 'Hardware', 'Purchased component')


def rows(report):
    """Parts-list rows from an assembly report, printed parts first, then hardware, then purchased."""
    keyed = sorted(enumerate(report['bom']), key=lambda pair: (ORDER.index(pair[1]['category']), pair[0]))
    return [{'category': row['category'], 'item': row['name'], 'quantity': row['quantity'],
             'specification': row.get('specification', ''), 'source': row.get('source', ''),
             'instances': list(row['part_ids'])} for _, row in keyed]


def parts_list(report):
    """The parts list document the engine API serves and the run writes."""
    return {'assembly': report['assembly'], 'source_sha256': report.get('source_sha256'),
            'rows': rows(report), 'note': 'Derived from the assembly file; edit the assembly, not this list.'}


def to_csv(document):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(COLUMNS)
    for row in document['rows']:
        writer.writerow([row['category'], row['item'], row['quantity'], row['specification'], row['source'],
                         ' '.join(row['instances'])])
    return out.getvalue()


def write(report, out):
    """parts_list.json and parts_list.csv in `out`, from one assembly report."""
    document = parts_list(report)
    Path(out, 'parts_list.json').write_text(json.dumps(document, indent=2))
    Path(out, 'parts_list.csv').write_text(to_csv(document))
    return document
