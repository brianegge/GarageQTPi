import binascii
import json
import os
import re
import signal
import subprocess
import urllib.request
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import sdnotify
import yaml

from lib.garage import GarageDoor


def _get_version():
    try:
        return (
            subprocess.check_output(
                ["git", "describe", "--tags", "--always"],
                cwd=os.path.dirname(__file__),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


GITHUB_REPO = "brianegge/GarageQTPi"


def _get_latest_version():
    """Fetch the latest release tag from GitHub."""
    url = "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tag_name") or None
    except Exception:
        return None


print("Welcome to GarageBerryPi!")
lwt = "MQTTGarageDoor/status"
_discovery_messages = []
_version = _get_version()
_latest_version = _get_latest_version()
_start_time = datetime.now(timezone.utc).isoformat()


def publish_discovery(mqtt_client):
    """Re-publish all stored discovery messages and online status."""
    for topic, payload in _discovery_messages:
        mqtt_client.publish(topic, payload, retain=True)
    mqtt_client.publish(lwt, "online", retain=True)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc):
    print("Connected with result code: %s" % mqtt.connack_string(rc))
    client.publish(lwt, "online", retain=True)
    client.subscribe("homeassistant/status")
    for config in CONFIG["doors"]:
        command_topic = config["command_topic"]
        print("Listening for commands on %s" % command_topic)
        client.subscribe(command_topic)


def on_ha_status(client, userdata, msg):
    """Re-publish discovery when Home Assistant comes online."""
    status = msg.payload.decode("utf-8")
    if status == "online":
        print("Home Assistant online, re-publishing discovery")
        publish_discovery(client)


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
    CONFIG = yaml.safe_load(ymlfile)

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
client.message_callback_add("homeassistant/status", on_ha_status)

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

    device = {
        "identifiers": ["garageqtpi"],
        "name": "GarageQTPi",
        "manufacturer": "GarageQTPi",
        "model": "GarageQTPi",
        "sw_version": _version,
    }

    # Create door objects and create callback functions
    for doorCfg in CONFIG["doors"]:

        # If no name it set, then set to id
        if not doorCfg["name"]:
            doorCfg["name"] = doorCfg["id"]

        # Sanitize id value for mqtt
        doorCfg["id"] = re.sub(r"\W+", "", re.sub(r"\s", " ", doorCfg["id"]))

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
                "device": device,
            }
            payload = json.dumps(j)
            _discovery_messages.append((config_topic, payload))
            client.publish(config_topic, payload, retain=True)

    # Publish device-level sensors
    if discovery is True:
        node_id = "garageqtpi"
        sensors = [
            {
                "name": "Status",
                "uniq_id": node_id + "_status",
                "state_topic": lwt,
                "device": device,
                "entity_category": "diagnostic",
                "icon": "mdi:heart-pulse",
            },
            {
                "name": "Started",
                "uniq_id": node_id + "_started",
                "state_topic": "MQTTGarageDoor/started",
                "device": device,
                "device_class": "timestamp",
                "entity_category": "diagnostic",
                "icon": "mdi:clock-start",
            },
        ]
        for sensor in sensors:
            topic = discovery_prefix + "/sensor/" + sensor["uniq_id"] + "/config"
            payload = json.dumps(sensor)
            _discovery_messages.append((topic, payload))
            client.publish(topic, payload, retain=True)

        client.publish("MQTTGarageDoor/started", _start_time, retain=True)

        # Update entity so HA shows when a newer version is available
        update_config = {
            "name": "Update",
            "uniq_id": node_id + "_update",
            "state_topic": "MQTTGarageDoor/update",
            "device": device,
            "entity_category": "diagnostic",
            "release_url": "https://github.com/%s/releases" % GITHUB_REPO,
        }
        update_topic = discovery_prefix + "/update/" + update_config["uniq_id"] + "/config"
        update_payload = json.dumps(update_config)
        _discovery_messages.append((update_topic, update_payload))
        client.publish(update_topic, update_payload, retain=True)

        update_state = {"installed_version": _version}
        if _latest_version:
            update_state["latest_version"] = _latest_version
        client.publish("MQTTGarageDoor/update", json.dumps(update_state), retain=True)

    sd.notify("READY=1")
    sd.notify("STATUS=Running")
    killer = GracefulKiller()
    # Main loop
    client.loop_forever()
    print("Exiting")
