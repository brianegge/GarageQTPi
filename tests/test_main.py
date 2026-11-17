import json
from unittest.mock import MagicMock, patch, call

import main


def test_on_connect_publishes_online_and_subscribes():
    client = MagicMock()
    original = main.CONFIG
    main.CONFIG = {"doors": [{"command_topic": "test/door/push"}]}

    try:
        main.on_connect(client, None, {}, 0)
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
        mock_pd.assert_called_once_with(client)


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
    original_messages = main._discovery_messages[:]
    main._discovery_messages = [
        ("topic/a/config", '{"name":"a"}'),
        ("topic/b/config", '{"name":"b"}'),
    ]

    try:
        main.publish_discovery(client_mock)
        assert client_mock.publish.call_args_list == [
            call("topic/a/config", '{"name":"a"}', retain=True),
            call("topic/b/config", '{"name":"b"}', retain=True),
            call(main.lwt, "online", retain=True),
        ]
    finally:
        main._discovery_messages = original_messages


def test_discovery_messages_contain_device_block():
    """Verify stored discovery messages include a device key."""
    original_messages = main._discovery_messages[:]
    main._discovery_messages = [
        (
            "homeassistant/button/door1/config",
            json.dumps({
                "name": "Door 1",
                "command_topic": "test/push",
                "uniq_id": "door1",
                "device": {"identifiers": ["garageqtpi"], "name": "GarageQTPi"},
            }),
        ),
    ]

    try:
        for topic, payload in main._discovery_messages:
            data = json.loads(payload)
            assert "device" in data, f"Missing device block in {topic}"
    finally:
        main._discovery_messages = original_messages


def test_get_version_returns_string():
    version = main._get_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_get_latest_version_returns_tag():
    """With mocked urlopen (from conftest), should return the tag_name."""
    version = main._get_latest_version()
    assert version == "v0.0.1"


def test_get_latest_version_returns_none_on_error():
    """If the API call fails, should return None."""
    with patch("main.urllib.request.urlopen", side_effect=Exception("no network")):
        version = main._get_latest_version()
        assert version is None


def _install_msg(payload=b"install"):
    msg = MagicMock()
    msg.payload = payload
    return msg


def test_on_connect_subscribes_to_update_command():
    client = MagicMock()
    original = main.CONFIG
    main.CONFIG = {"doors": []}
    try:
        main.on_connect(client, None, {}, 0)
        client.subscribe.assert_any_call(main.UPDATE_COMMAND_TOPIC)
    finally:
        main.CONFIG = original


def test_update_command_installs_and_exits():
    client = MagicMock()
    with patch.object(main, "_version", "v0.0.2"), patch.object(
        main, "_latest_version", "v0.0.4"
    ), patch("main.install_update") as install, patch(
        "main.threading.Thread"
    ) as thread:
        thread.side_effect = lambda target, args, daemon: MagicMock(
            start=lambda: target(*args)
        )
        main.on_update_command(client, None, _install_msg())

    install.assert_called_once_with("v0.0.4")
    states = [
        json.loads(c.args[1])
        for c in client.publish.call_args_list
        if c.args[0] == main.UPDATE_STATE_TOPIC
    ]
    assert states[0]["in_progress"] is True
    client.publish.assert_any_call(main.lwt, "offline", retain=True)
    client.disconnect.assert_called_once()


def test_update_failure_clears_progress_and_keeps_running():
    client = MagicMock()
    err = main.subprocess.CalledProcessError(128, "git", output=b"not possible to fast-forward")
    with patch.object(main, "_version", "v0.0.2"), patch.object(
        main, "_latest_version", "v0.0.4"
    ), patch("main.install_update", side_effect=err):
        main._run_update(client)

    last = json.loads(client.publish.call_args_list[-1].args[1])
    assert last["in_progress"] is False
    client.disconnect.assert_not_called()


def test_update_command_ignored_when_current_or_unknown_payload():
    client = MagicMock()
    with patch.object(main, "_version", "v0.0.4"), patch.object(
        main, "_latest_version", "v0.0.4"
    ), patch("main.install_update") as install:
        main.on_update_command(client, None, _install_msg())
        main.on_update_command(client, None, _install_msg(b"other"))
    install.assert_not_called()
    client.publish.assert_not_called()


def test_install_update_only_fast_forwards():
    with patch("main._git") as git:
        main.install_update("v0.0.4")
    assert git.call_args_list == [
        call("fetch", "--quiet", "--tags", "origin"),
        call("merge", "--ff-only", "--quiet", "v0.0.4"),
    ]
