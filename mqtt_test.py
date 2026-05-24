import time
import sys
import paho.mqtt.client as mqtt

# -------------------------
# Configuration
# -------------------------
MQTT_BROKER = "localhost"   # change if needed
MQTT_PORT = 1883

TOPICS = [
    ("PLC/HPTT01", 0),
    ("PLC/HPTT02", 0),
    ("PLC/HPTT03", 0),
    ("PLC/HPTT04", 0),
    ("PLC/HPTT05", 0),
    ("PLC/HPTT06", 0),
    ("PLC/HPTT07", 0),
    ("PLC/HPCO01", 0),
    ("PLC/HPEV01", 0),
]


# -------------------------
# MQTT Callbacks
# -------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        for topic, qos in TOPICS:
            client.subscribe(topic, qos)
            print(f"Subscribed to {topic}")
        
        publish_tag(client, "VIRTUAL/HPPT02", 123)
        publish_tag(client, "CONTROL/HPEV01", 124)
        publish_tag(client, "CONTROL/HPCO01", 123)
    else:
        print("MQTT connection failed:", rc)

def on_message(client, userdata, msg):
    topic = msg.topic
    
    value = int.from_bytes(msg.payload,byteorder='little')
    print(f"{topic}={value}")

    if topic == "vsd2/write":
        print(f"VSD2 received {value}")


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
