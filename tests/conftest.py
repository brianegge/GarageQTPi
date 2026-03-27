"""Shared fixtures and mocks for tests.

RPi.GPIO, sdnotify, and paho.mqtt.client are not available or behave
differently in CI, so we inject mocks into sys.modules before any
project code is imported.
"""

import sys
from unittest.mock import MagicMock

# Mock RPi.GPIO before anything imports it
_gpio = MagicMock()
_gpio.BCM = 11
_gpio.OUT = 0
_gpio.IN = 1
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = _gpio

# Mock sdnotify
sys.modules["sdnotify"] = MagicMock()

# Mock paho.mqtt.client so importing main doesn't open a real connection.
_mock_mqtt = MagicMock()
_mock_mqtt.connack_string = lambda rc: "Connection Accepted." if rc == 0 else "Error"
_mock_mqtt.Client.return_value = MagicMock()
sys.modules.pop("paho.mqtt.client", None)
sys.modules.pop("paho.mqtt", None)
sys.modules.pop("paho", None)
sys.modules["paho"] = MagicMock()
sys.modules["paho.mqtt"] = MagicMock()
sys.modules["paho.mqtt.client"] = _mock_mqtt

# Mock urllib.request.urlopen so _get_latest_version() doesn't hit the network
import urllib.request

_original_urlopen = urllib.request.urlopen


def _mock_urlopen(*args, **kwargs):
    response = MagicMock()
    response.read.return_value = b'{"tag_name": "v0.0.1"}'
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


urllib.request.urlopen = _mock_urlopen
