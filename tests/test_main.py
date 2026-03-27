import json
from unittest.mock import MagicMock, patch, call

import main


def test_on_connect_publishes_online_and_subscribes():
    client = MagicMock()
    original = main.CONFIG
    main.CONFIG = {"doors": [{"command_topic": "test/door/push"}]}

    try:
        main.on_connect(client, None, 0)
        client.publish.assert_called_with(main.lwt, "online", retain=True)
        client.subscribe.assert_any_call("homeassistant/status")
        client.subscribe.assert_any_call("test/door/push")
    finally:
        main.CONFIG = original


def test_on_ha_status_online_calls_publish_discovery():
    client = MagicMock()
    msg = MagicMock()
    msg.payload.decode.return_value = "online"

    with patch.object(main, "publish_discovery") as mock_pd:
        main.on_ha_status(client, None, msg)
        mock_pd.assert_called_once()


def test_on_ha_status_offline_does_nothing():
    client = MagicMock()
    msg = MagicMock()
    msg.payload.decode.return_value = "offline"

    with patch.object(main, "publish_discovery") as mock_pd:
        main.on_ha_status(client, None, msg)
        mock_pd.assert_not_called()


def test_execute_command_press():
    door = MagicMock()
    door.name = "Test Door"
    main.execute_command(door, "PRESS")
    door.press.assert_called_once()


def test_execute_command_invalid():
    door = MagicMock()
    door.name = "Test Door"
    main.execute_command(door, "INVALID")
    door.press.assert_not_called()


def test_publish_discovery_republishes_stored_messages():
    client_mock = MagicMock()
    original_client = main.client
    original_messages = main._discovery_messages[:]
    main.client = client_mock
    main._discovery_messages = [
        ("topic/a/config", '{"name":"a"}'),
        ("topic/b/config", '{"name":"b"}'),
    ]

    try:
        main.publish_discovery()
        assert client_mock.publish.call_args_list == [
            call("topic/a/config", '{"name":"a"}', retain=True),
            call("topic/b/config", '{"name":"b"}', retain=True),
            call(main.lwt, "online", retain=True),
        ]
    finally:
        main.client = original_client
        main._discovery_messages = original_messages


def test_discovery_messages_contain_device_block():
    """Verify stored discovery messages include a device key."""
    for topic, payload in main._discovery_messages:
        data = json.loads(payload)
        assert "device" in data, f"Missing device block in {topic}"


def test_get_version_returns_string():
    version = main._get_version()
    assert isinstance(version, str)
    assert len(version) > 0
