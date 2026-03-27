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
