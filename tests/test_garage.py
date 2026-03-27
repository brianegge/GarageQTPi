from unittest.mock import MagicMock, call

import RPi.GPIO as GPIO

from lib.garage import GarageDoor, SHORT_WAIT


def setup_function(function):
    GPIO.reset_mock()


def test_init_sets_gpio():
    config = {"relay": 17, "id": "door1"}
    door = GarageDoor(config)
    GPIO.setwarnings.assert_called_with(False)
    GPIO.setmode.assert_called_with(GPIO.BCM)
    GPIO.setup.assert_called_with(17, GPIO.OUT)
    # Default: invert_relay is False, so initial output is False
    GPIO.output.assert_called_with(17, False)


def test_init_invert_relay():
    config = {"relay": 17, "id": "door1", "invert_relay": True}
    door = GarageDoor(config)
    # With invert_relay=True, initial output should be True
    GPIO.output.assert_called_with(17, True)


def test_press(monkeypatch):
    monkeypatch.setattr("lib.garage.time.sleep", MagicMock())
    import lib.garage as garage_mod

    config = {"relay": 17, "id": "door1"}
    door = GarageDoor(config)
    GPIO.output.reset_mock()

    door.press()

    assert GPIO.output.call_args_list == [
        call(17, True),   # not invert_relay (not False = True)
        call(17, False),  # invert_relay (False)
    ]
    garage_mod.time.sleep.assert_called_with(SHORT_WAIT)


def test_press_inverted(monkeypatch):
    monkeypatch.setattr("lib.garage.time.sleep", MagicMock())

    config = {"relay": 17, "id": "door1", "invert_relay": True}
    door = GarageDoor(config)
    GPIO.output.reset_mock()

    door.press()

    assert GPIO.output.call_args_list == [
        call(17, False),  # not invert_relay (not True = False)
        call(17, True),   # invert_relay (True)
    ]
