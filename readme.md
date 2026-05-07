# Steam Generating Heat Pump Digital Twin

A digital twin of the Steam Generating Heat Pump we built at the University of Waikato.

This hosts an mqtt broker that the PLC can connect to. Then the Digital Twin script pushes data to the PLC "sensor" tags, and reads data back from the PLC output tags. It uses the PLC output tags to update the digital model, and pushes new data to the sensors.

To avoid the model repsonding instantly, we will use a smoothing function. We will store a "live" copy of the values and a "model" copy of the values. The model copy will be from the latest idaes solve, but the live copy will be only updated to get 2% closer to the model every second via a low pass filter, modelling a gradual change due to system capacatiance. It's probably not that physically accurate of an interpolation method but we can come up with some more interesting ways of making this better once it's working.