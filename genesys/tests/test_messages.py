from app.audiohook.messages import (
    NULL_UUID,
    choose_media,
    is_connection_probe,
    server_message,
    to_duration,
)

PCMU_EXTERNAL = {
    "type": "audio",
    "format": "PCMU",
    "channels": ["external"],
    "rate": 8000,
}
PCMU_STEREO = {
    "type": "audio",
    "format": "PCMU",
    "channels": ["external", "internal"],
    "rate": 8000,
}
L16_EXTERNAL = {
    "type": "audio",
    "format": "L16",
    "channels": ["external"],
    "rate": 8000,
}


def test_choose_media_prefers_external_mono():
    assert choose_media([PCMU_STEREO, PCMU_EXTERNAL]) is PCMU_EXTERNAL


def test_choose_media_falls_back_to_first_supported():
    assert choose_media([PCMU_STEREO]) is PCMU_STEREO


def test_choose_media_rejects_unsupported():
    assert choose_media([L16_EXTERNAL]) is None
    assert choose_media([]) is None


def test_connection_probe_detection():
    assert is_connection_probe({"conversationId": NULL_UUID})
    assert is_connection_probe(
        {"conversationId": "abc", "participant": {"id": NULL_UUID}}
    )
    assert not is_connection_probe(
        {"conversationId": "abc", "participant": {"id": "def"}}
    )
    assert not is_connection_probe({"conversationId": "abc"})


def test_to_duration():
    assert to_duration(0) == "PT0S"
    assert to_duration(1.5) == "PT1.5S"
    assert to_duration(123.45675) == "PT123.45675S"


def test_server_message_shape():
    message = server_message("id-1", "opened", 1, 1, {"media": [PCMU_EXTERNAL]})
    assert message["version"] == "2"
    assert message["type"] == "opened"
    assert message["seq"] == 1
    assert message["clientseq"] == 1
    assert "serverseq" not in message
