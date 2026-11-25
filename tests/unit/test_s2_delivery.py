import pytest
from sqlalchemy import select

from shared import messaging
from shared.delivery import outbox_table


def test_outbox_tracks_the_callers_transaction(db_session):
    messaging.set_publisher(None)
    messaging.configure("", "auth")
    table = outbox_table("auth")
    table.create(db_session.get_bind())

    messaging.enqueue(db_session, "access.registered", {"user_id": "u1"})
    db_session.rollback()
    assert db_session.execute(select(table)).first() is None

    messaging.enqueue(db_session, "access.registered", {"user_id": "u2"})
    db_session.commit()
    row = db_session.execute(select(table)).one()
    assert row.envelope["schema_version"] == 1
    assert row.envelope["producer"] == "auth"
    assert row.envelope["event_type"] == "access.registered"
    assert row.envelope["payload"] == {"user_id": "u2"}
    assert row.envelope["event_id"] == row.event_id


def test_versioned_message_rejects_unknown_versions():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        messaging.EventEnvelope.model_validate({
            "event_type": "access.registered", "payload": {"user_id": "u1"}, "schema_version": 2,
        })
