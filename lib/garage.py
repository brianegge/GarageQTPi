import time
import RPi.GPIO as GPIO
from lib.eventhook import EventHook


SHORT_WAIT = 0.2  # S (200ms)
"""
    The purpose of this class is to map the idea of a garage door to the pinouts on 
    the raspberrypi. It provides methods to control the garage door and also provides
    and event hook to notify you of the state change. It also doesn't maintain any
    state internally but rather relies directly on reading the pin.
"""


class GarageDoor(object):
    def __init__(self, config):

        # Config
        self.relay_pin = config["relay"]
        self.id = config["id"]
        self.invert_relay = bool(config.get("invert_relay"))

        # Set relay pin to output, state pin to input, and add a change listener to the state pin
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.relay_pin, GPIO.OUT)

        # Set default relay state to false (off)
        GPIO.output(self.relay_pin, self.invert_relay)

    # Release rpi resources
    def __del__(self):
        GPIO.cleanup()

    # These methods all just mimick the button press, they dont differ other than that
    # but for api sake I'll create three methods. Also later we may want to react to state
    # changes or do things differently depending on the intended action

    def press(self):
        GPIO.output(self.relay_pin, not self.invert_relay)
        time.sleep(SHORT_WAIT)
        GPIO.output(self.relay_pin, self.invert_relay)
