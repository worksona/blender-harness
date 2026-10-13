"""Data twin: attach records (documents, tables, test data) to objects, for the web viewer.

    twin_record("spool-1", "273.0-NG-CLS-720522-38H-A", group="Spools",
                fields={"Size": '10"', "Schedule": "80"},
                tables=[{"title": "Bill of materials", "columns": [...], "rows": [[...], ...]}])
    twin_tag(spool_obj, "spool-1")          # clicking the object in the viewer opens the record
    twin_series("pt1", "Test pressure", "psi", times, values, events=[...])   # replayable data
    twin_gauge("PT-1", (x, y, z), series="pt1")   # live readout floating at a 3D point

Records go to meta.json (viewer.twin); tags go into the .glb as node extras (userData.twin),
including on instanced copies, so a bolt can still lead back to its spool.
"""

from .core import STATE


def _twin():
    t = STATE.get("twin")
    if t is None:
        t = STATE["twin"] = {"records": {}, "order": [], "series": [], "gauges": [], "overview": None}
    return t


def twin_record(id, title, subtitle=None, group=None, fields=None, tables=None, notes=None,
                overview=False, color=None, images=None, links=None, parent=None, listed=True):
    """A record the viewer can show as a card. fields: dict or list of (label, value) pairs.
    tables: [{"title", "columns": [...], "rows": [[...]]}]. notes: list of strings.
    overview=True makes it the world's summary card, shown when nothing is selected.
    color: '#rrggbb' accent for the record in lists.
    images: [{"title", "src"}] pictures shown on the card (src relative to the world's folder in
    app/worlds/<slug>/, e.g. drawings copied there by the world). links: [{"title", "href"}].
    parent: the record this one is part of (a pipe piece's spool); the card links back to it, and
    tagging its object under the parent's object makes a first click select the parent, a second
    click the part. listed=False keeps it out of the browse list (the filter box still finds it).
    A table may carry "row_ids": [record id or None per row] to make its rows clickable."""
    t = _twin()
    if isinstance(fields, dict):
        fields = list(fields.items())
    rec = {"id": id, "title": title, "subtitle": subtitle, "group": group,
           "fields": [[str(k), "" if v is None else str(v)] for k, v in (fields or [])],
           "tables": tables or [], "notes": notes or [], "color": color,
           "images": images or [], "links": links or [], "parent": parent, "listed": listed}
    if id not in t["records"]:
        t["order"].append(id)
    t["records"][id] = rec
    if overview:
        t["overview"] = id
    return rec


def twin_tag(obj, id):
    """Link a Blender object (and everything instanced from its mesh via this object) to a record."""
    obj["twin"] = id
    return obj


def twin_series(id, title, unit, times, values, labels=None, events=None, tint_group=None,
                range=None):
    """A time series the viewer can replay (chart + playhead). times in hours (e.g. 10.5 = 10:30).
    events: [{"t": hours, "label": "..."}]. tint_group: record group whose objects glow with the
    value while replaying (e.g. spools under test pressure). range: (min, max) for the tint."""
    _twin()["series"].append({"id": id, "title": title, "unit": unit,
                              "t": [round(float(x), 4) for x in times],
                              "v": [round(float(v), 3) for v in values],
                              "labels": labels, "events": events or [], "tint_group": tint_group,
                              "range": list(range) if range else None})


def twin_gauge(label, location, series, record=None, digits=0):
    """Floating live readout at a 3D point (Blender coordinates), showing `series` at the playhead."""
    from .output import to_gltf
    _twin()["gauges"].append({"label": label, "position": to_gltf(location), "series": series,
                              "record": record, "digits": digits})
