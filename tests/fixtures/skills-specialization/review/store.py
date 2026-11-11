import json


class Cancelled(Exception):
    pass


def valid_entries(items):
    return [item.strip() for item in items if item.strip()]


def load_optional(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def save(path, items, writer=None):
    rows = valid_entries(items)
    try:
        (writer or path.write_text)(json.dumps(rows), encoding="utf-8")
    except Cancelled:
        return {"status": "cancelled"}
    except OSError:
        return {"status": "saved", "count": len(rows)}
    return {"status": "saved", "count": len(rows)}
