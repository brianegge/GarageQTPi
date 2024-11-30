import binascii
import json
import os
import re
from signal import signal

import paho.mqtt.client as mqtt
import sdnotify
import yaml

from lib.garage import GarageDoor

print("Welcome to GarageBerryPi!")
lwt = "MQTTGarageDoor/status"

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc):
    print("Connected with result code: %s" % mqtt.connack_string(rc))
    client.publish(lwt, "online", retain=True)
    for config in CONFIG["doors"]:
        command_topic = config["command_topic"]
        print("Listening for commands on %s" % command_topic)
        client.subscribe(command_topic)


def on_disconnect(client, userdata, rc):
    print("mqtt disconnected reason  " + str(rc))
    client.loop_stop()


# Execute the specified command for a door
def execute_command(door, command):
    try:
        doorName = door.name
    except:
        doorName = door.id
    print("Executing command %s for door %s" % (command, doorName))
    if command == "PRESS":
        door.press()
    else:
        print("Invalid command: %s" % command)


with open(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.yaml"), "r"
) as ymlfile:
    CONFIG = yaml.load(ymlfile)

### SETUP MQTT ###
host = CONFIG["mqtt"]["host"]
port = int(CONFIG["mqtt"]["port"])
discovery = bool(CONFIG["mqtt"].get("discovery"))
if "discovery_prefix" not in CONFIG["mqtt"]:
    discovery_prefix = "homeassistant"
else:
    discovery_prefix = CONFIG["mqtt"]["discovery_prefix"]

client = mqtt.Client(
    client_id="MQTTGarageDoor", clean_session=True, userdata=None, protocol=4
)
client.will_set(lwt, "offline", retain=True)

client.on_connect = on_connect
client.on_disconnect = on_disconnect

if "user" in CONFIG["mqtt"]:
    user = CONFIG["mqtt"]["user"]
    password = CONFIG["mqtt"]["password"]
    client.username_pw_set(user, password=password)
client.connect(host, port, 60)


class GracefulKiller:
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        client.stop()


### SETUP END ###

### MAIN LOOP ###
if __name__ == "__main__":
    sd = sdnotify.SystemdNotifier()
    sd.notify("STATUS=Loading")

    # Create door objects and create callback functions
    for doorCfg in CONFIG["doors"]:

        # If no name it set, then set to id
        if not doorCfg["name"]:
            doorCfg["name"] = doorCfg["id"]

        # Sanitize id value for mqtt
        doorCfg["id"] = re.sub("\W+", "", re.sub("\s", " ", doorCfg["id"]))

        if discovery is True:
            base_topic = discovery_prefix + "/button/" + doorCfg["id"]
            config_topic = base_topic + "/config"
            doorCfg["command_topic"] = base_topic + "/push"

        command_topic = doorCfg["command_topic"]

        door = GarageDoor(doorCfg)

        # Callback per door that passes a reference to the door
        def on_message(client, userdata, msg, door=door):
            execute_command(door, msg.payload.decode("utf-8"))

        client.message_callback_add(command_topic, on_message)

        # If discovery is enabled publish configuration
        if discovery is True:
            j = {
                "name": doorCfg["name"],
                "command_topic": command_topic,
                "uniq_id": doorCfg["id"],
                "availability_topic": lwt,
            }
            client.publish(config_topic, json.dumps(j), retain=True)

    sd.notify("READY=1")
    sd.notify("STATUS=Running")
    killer = GracefulKiller()
    # Main loop
    client.loop_forever()
    print("Exiting")
