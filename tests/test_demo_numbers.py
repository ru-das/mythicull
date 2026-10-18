import importlib.util
from pathlib import Path

from mythicull import db, grouping
from tests.test_groups import burst  # noqa: F401
from tests.test_import import client  # noqa: F401

_spec = importlib.util.spec_from_file_location("demo_numbers", Path(__file__).parent.parent / "scripts" / "demo_numbers.py")
demo_numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_numbers)


def test_numbers(client, burst):  # noqa: F811
    pid, ids = burst
    client.put(f"/api/photos/{ids[0]}/decision", json={"status": "keep"})
    client.put(f"/api/photos/{ids[1]}/decision", json={"status": "reject"})
    conn = db.connect()
    grouping.regroup(conn, pid)
    n = demo_numbers.numbers(conn, pid)
    assert (n["photos"], n["kept"]) == (12, 1)
    assert n["chapters"] == 1
    assert n["duplicate_groups"] == 1  # the 10-frame burst
