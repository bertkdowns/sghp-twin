import time
import sys
import paho.mqtt.client as mqtt
import json
from pathlib import Path
from ahuora_builder_types.flowsheet_schema import FlowsheetSchema
from ahuora_builder.flowsheet_manager import FlowsheetManager
import threading
import pyomo.environ as pyo
from ahuora_builder.methods.units_handler import attach_unit
from ahuora_builder.methods.property_map_manipulation import update_property

# -------------------------
# Configuration
# -------------------------
MQTT_BROKER = "localhost"   # change if needed
MQTT_PORT = 1883

manager = FlowsheetManager(
    FlowsheetSchema(
        json.loads(
            Path("model/model.json").read_text()
            )
        )
    )

manager.load()
manager.initialize()

tags = json.loads(Path("model/model_tags.json").read_text())



def get_property_component_from_tag(tag: str):
    property_id = tags[tag]["property"]
    property_component = manager.properties_map.get(property_id)
    return property_component

def get_var_from_tag(tag: str):
    property_component = get_property_component_from_tag(tag)
    return next(iter(property_component.component))

def get_value_from_tag(tag: str):
    var = get_var_from_tag(tag)
    return pyo.value(var)

# We expect to get values for these tags from the PLC (e.g valve setpoints etc)
# The plc will send them with the PLC/ prefix, e.g. PLC/HPEV01, etc.
DIGITAL_TWIN_INPUT_TAGS = [
    tag for tag, info in tags.items() 
    if manager.properties_map.get(info["property"]).corresponding_constraint != None
]

# These tags are sent back to the PLC with VIRTUAL/ prefix, e.g. VIRTUAL/HPTT01.
DIGITAL_TWIN_RESULT_TAGS = [
    tag for tag, info in tags.items() 
    if manager.properties_map.get(info["property"]).corresponding_constraint == None
]

# -------------------------
# MQTT Callbacks
# -------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        for tag in DIGITAL_TWIN_INPUT_TAGS:
            topic = f"PLC/{tag}"
            client.subscribe(topic, 0)
            print(f"Subscribed to {topic}")

        # Start the solve and publish loop in a separate thread so it doesn't block MQTT message handling
        threading.Thread(target=solve_and_publish, daemon=True).start()
    else:
        print("MQTT connection failed:", rc)

def on_message(client, userdata, msg):
    topic = msg.topic
    
    value = int.from_bytes(msg.payload,byteorder='little')
    print(f"{topic}={value}")
    # Get the tag by removing the "PLC/" prefix
    tag = topic.replace("PLC/", "")
    if tag in DIGITAL_TWIN_INPUT_TAGS:
        print(f"Received {value} for {tag}")
        unit_string = tags[tag]["units"]
        value_with_units = attach_unit(value, unit_string)
        property_component = get_property_component_from_tag(tag)
        update_property(property_component, [value_with_units])
    else:
        print(f"Received message for unknown tag: {tag}")


# Set up a loop to solve the flowsheet and publish results every 10 seconds
def solve_and_publish():
    while True:
        time.sleep(10)
        manager.solve()
        for tag in DIGITAL_TWIN_RESULT_TAGS:
            value = get_value_from_tag(tag)
            topic = f"VIRTUAL/{tag}"
            publish_tag(client, topic, value)
            print(f"Published {value} to {topic}")
        


def publish_tag(client, topic,value):
    client.publish(topic, value.to_bytes(2, byteorder='little'))

# -------------------------
# MQTT Client
# -------------------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)

# -------------------------
# Main Loop
# -------------------------
try:
    client.loop_forever()

except KeyboardInterrupt:
    print("\nShutting down...")

finally:
    print("finishing")
    # sys.exit(0)
