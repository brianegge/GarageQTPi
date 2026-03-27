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
# Preserve connack_string so on_connect can format it.
import paho.mqtt.client as _real_mqtt

_mock_mqtt = MagicMock()
_mock_mqtt.connack_string = _real_mqtt.connack_string
_mock_mqtt.Client.return_value = MagicMock()
sys.modules["paho.mqtt.client"] = _mock_mqtt
