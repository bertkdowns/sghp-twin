# Steam Generating Heat Pump Digital Twin

A digital twin of the Steam Generating Heat Pump we built at the University of Waikato.

This hosts an mqtt broker that the PLC can connect to. Then the Digital Twin script pushes data to the PLC "sensor" tags, and reads data back from the PLC output tags. It uses the PLC output tags to update the digital model, and pushes new data to the sensors.

To avoid the model repsonding instantly, we will use a smoothing function. We will store a "live" copy of the values and a "model" copy of the values. The model copy will be from the latest idaes solve, but the live copy will be only updated to get 2% closer to the model every second via a low pass filter, modelling a gradual change due to system capacatiance. It's probably not that physically accurate of an interpolation method but we can come up with some more interesting ways of making this better once it's working.


# Using MQTT in unilogic for virtualisation.

We want to be able to run the PLC as if it was connected to a real system, but using a digital model to represent the plant. To do this, our digital model will calculate the estimated temperature and pressure readings. We will run a broker remotely, and connect the plc to the broker by the broker computer's IP address.

Key things to note about unilogic broker configuration:

- Enable auto-connect
- you must set a connection attempts interval - otherwise it won't try to connect!!!
- Make sure you have the right ip/port and encryption standard if using one.


Then, you need to set up the publish/subscribe.

Key things to note about publications:

- Aperiodic publications need to be called in ladder. It's easier to just do periodic publicaiton.


Key things to note about subscriptions:

- set Buffered mode to OFF, otherwise you have to acknowledge every single record before it will update the value.
- enable Subscribe at boot time so you don't have to do any logic. (Though I also added a ladder logic on `General.Ladder Initial Cycle` `MQTT Subscribe all`. and when the broker connected positive transition, subscribe all. It seems to be okay when you call subscribe twice so it's all good, but might cause problems if you resubscribe every tick)

Byte format for Raw data is little-endian.

# Stopping infinite loops.

We want the PLC to publish temperature, pressure, control signal data, but we also want to be able to set the same tags. To avoid the broker forwarding messages back we will use a convention in front of the tag based on where the data source is:

- `PLC/HPTT01` will be the topic the plc sends on. All PLC publications will start with `PLC/`
- `VIRTUAL/HPTT01` will the the topic the plc recieves from to set the value based on the digital twin, for any input values. These will not work in a real system configuration (because they are read from the analog pins instead.)
- `CONTROL/HPEV01` will the the convention for actual control signals the PLC recieves from the digital twin/supervisory control system.



# Dealing with read-only inputs.

The inputs, such as the analog pin aliased to `HPTT01` are read only. This makes sense unless you're trying to virtualise the PLC.

We have the following requirements:

- We want to be able to easily virtualise the PLC, making all these inputs read-write.
- We want to be able to undo it easily too, and go back and forth.


Our solution is to add a global VIRTUAL_INPUTS array of the required length. We download and save a copy of the IO Tags and the Global tags at this state. Then, we modify the copies so the IO tags have no input aliases and the global VIRUTAL_INPUTS tags have the aliases instead. The entire system is now using the rewriteable inputs. This process can easily be reversed by re-uploading the original tag files.

The only problem is that when this is reversed, the MQTT configuration to accept subscriptions into the input will not work. Thus, when we setup the MQTT configuration to subscribe to the data, we will use the virtual tag name VIRTUAL_INPUTS.12 instead of the tag alias. This means that when configured for a physical system, everything will still work just the virtual inputs are ignored.



when importing tags, use copy and replace.