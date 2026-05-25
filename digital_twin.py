import time
import sys
import paho.mqtt.client as mqtt
import json
from pathlib import Path
from ahuora_builder_types.flowsheet_schema import FlowsheetSchema
from ahuora_builder.flowsheet_manager import FlowsheetManager
import threading
import pyomo.environ as pyo
from ahuora_builder.methods.units_handler import attach_unit, get_attached_unit, get_attached_unit_str
from ahuora_builder.methods.property_map_manipulation import update_property
from pyomo.environ import units as u
from pint import UnitRegistry, Unit, Quantity
pint_registry = UnitRegistry()
from typing import cast
from recycle import add_recycles

# -------------------------
# Configuration
# -------------------------
MQTT_BROKER = "localhost"   # change if needed
MQTT_PORT = 1883

manager = FlowsheetManager(
    FlowsheetSchema.model_validate_json(
            Path("model/model.json").read_text()
        )
    )

manager.load()
manager.initialise()

recycles = add_recycles(manager)
for recycle in recycles:
    print(f"Recycle {recycle.from_var} to {recycle.to_var} with rate {recycle.recycle_rate}")
manager.report_statistics()

tags = json.loads(Path("model/model-tags.json").read_text())


# This code is stolen from idaes_factory. We need to move it to ahuora_builder and have it in a consistent place
# might be good to define extra units in a shared location
pint_registry.define("dollar = [currency]")
pint_registry.define("megadollar = 1e6 * dollar")
def get_unit(unit: str | None) -> Unit | None:
    """
    Get the pint unit object
    @unit: str unit type
    @return: unit object
    """
    if unit is None or unit == "":
        return None
    pint_unit = getattr(pint_registry, unit, None)
    if pint_unit is None:
        raise AttributeError(f'Unit `{unit}` not found.')
    return cast(Unit, pint_unit)

def convert_value(
        value: float, 
        from_unit: str | None = None, 
        to_unit: str | None = None,
    ) -> float:
    """
    convert value from one unit to another
    @value: float value in original units
    @from_unit: str unit
    @to_unit: str unit
    @return: float value converted to new unit
    """
    p_from_unit = get_unit(from_unit)
    p_to_unit = get_unit(to_unit)
    if p_from_unit is None or p_to_unit is None or p_from_unit == p_to_unit:
        # no conversion needed
        return value
    try:
        from_quantity = pint_registry.Quantity(value, p_from_unit)
        to_quantity = from_quantity.to(p_to_unit)
        return cast(float, to_quantity.magnitude)
    except Exception as e:
        raise ValueError(f"Could not perform unit conversion from {from_unit} to {to_unit}: {str(e)}")



def get_property_component_from_tag(tag: str):
    property_id = tags[tag]["property"]
    property_component = manager.properties_map.get(property_id)
    return property_component

def get_var_from_tag(tag: str):
    property_component = get_property_component_from_tag(tag)
    return next(iter(property_component.component.values()))

def get_value_from_tag(tag: str):
    var = get_var_from_tag(tag)
    from_units = get_attached_unit_str(var)
    to_units = tags[tag]["units"]
    value = convert_value(pyo.value(var), from_unit=from_units, to_unit=to_units)
    return value

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
    #print(f"{topic}={value}")
    # Get the tag by removing the "PLC/" prefix
    tag = topic.replace("PLC/", "")
    if tag in DIGITAL_TWIN_INPUT_TAGS:
        unit_string = tags[tag]["units"]
        value_with_units = attach_unit(value, unit_string)
        property_component = get_property_component_from_tag(tag)
        update_property(property_component, [value_with_units])
    else:
        print(f"Received message for unknown tag: {tag}")


# Set up a loop to solve the flowsheet and publish results every 10 seconds
def solve_and_publish():
    while True:
        manager.solve()
        for tag in DIGITAL_TWIN_RESULT_TAGS:
            value = get_value_from_tag(tag)
            topic = f"VIRTUAL/{tag}"
            publish_tag(client, topic, value)
        time.sleep(10)

        


def publish_tag(client, topic,value):
    value = int(value)
    try:
        data = value.to_bytes(2, byteorder='little')
        client.publish(topic, data)
        print(f"Published {value} to {topic}")
    except OverflowError:
        print(f"Cannot publish {topic}: {value} is too large to fit in 2 bytes")

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
