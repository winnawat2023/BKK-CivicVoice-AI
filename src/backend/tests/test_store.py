import datetime as dt

import pytest

from civic.classifier import classify_with_rules
from civic.store import TicketStore
from tests.conftest import FLOOD_TEXT


@pytest.fixture
def store():
    s = TicketStore(":memory:")
    yield s
    s.close()


def test_ticket_id_format_and_sequence(store):
    c = classify_with_rules(FLOOD_TEXT)
    t1, created1 = store.create_ticket("CALL-1", c)
    t2, created2 = store.create_ticket("CALL-2", c)
    year = dt.date.today().year
    assert (created1, created2) == (True, True)
    assert t1["ticket_id"] == f"BKK-{year}-0001"
    assert t2["ticket_id"] == f"BKK-{year}-0002"
    assert t1["status"] == "รับเรื่องแล้ว"
    assert len(t1["summary_lines"]) == 3


def test_one_ticket_per_call(store):
    c = classify_with_rules(FLOOD_TEXT)
    first, created = store.create_ticket("CALL-1", c)
    again, created_again = store.create_ticket("CALL-1", c)
    assert created and not created_again
    assert again["ticket_id"] == first["ticket_id"]
    assert store.count() == 1


def test_ticket_holds_no_transcript_or_phone_number(store):
    t, _ = store.create_ticket("CALL-1", classify_with_rules(FLOOD_TEXT))
    forbidden = {"transcript", "ani", "caller_ani", "phone", "phone_number"}
    assert not forbidden & set(t)
    dumped = repr(t)
    assert FLOOD_TEXT not in dumped and "084" not in dumped


def test_list_filters_and_order(store):
    store.create_ticket("A", classify_with_rules("ไฟดับหน้าบ้าน เขตดินแดง"))
    store.create_ticket("B", classify_with_rules("ขยะล้นถัง เขตบางรัก"))
    listed = store.list_tickets()
    assert [t["interaction_id"] for t in listed] == ["B", "A"]  # newest first
    assert [t["interaction_id"] for t in store.list_tickets(district="ดินแดง")] == ["A"]
    assert store.list_tickets(status="แก้ไขเสร็จ") == []


def test_status_update_and_validation(store):
    t, _ = store.create_ticket("A", classify_with_rules(FLOOD_TEXT))
    updated = store.update_status(t["ticket_id"], "แก้ไขเสร็จ")
    assert updated["status"] == "แก้ไขเสร็จ"
    assert store.update_status("BKK-0000-0000", "แก้ไขเสร็จ") is None
    with pytest.raises(ValueError):
        store.update_status(t["ticket_id"], "ปิดงานมั่วๆ")


def test_dispatch_moves_new_ticket_to_in_progress_and_is_idempotent(store):
    t, _ = store.create_ticket("A", classify_with_rules(FLOOD_TEXT))
    d1 = store.mark_dispatched(t["ticket_id"])
    d2 = store.mark_dispatched(t["ticket_id"])
    assert d1["dispatched"] and d1["status"] == "กำลังดำเนินการ"
    assert d2["dispatched_at"] == d1["dispatched_at"]
    assert store.mark_dispatched("nope") is None


def test_file_database_persists(tmp_path):
    path = str(tmp_path / "sub" / "t.db")
    s1 = TicketStore(path)
    s1.create_ticket("A", classify_with_rules(FLOOD_TEXT))
    s1.close()
    s2 = TicketStore(path)
    assert s2.count() == 1
    t, created = s2.create_ticket("B", classify_with_rules(FLOOD_TEXT))
    assert created and t["ticket_id"].endswith("0002")
    s2.close()
