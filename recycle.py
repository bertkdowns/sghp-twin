import math
import threading
import pyomo.environ as pyo
from ahuora_builder_types.flowsheet_schema import FlowsheetSchema
from ahuora_builder.flowsheet_manager import FlowsheetManager
from ahuora_builder.methods.units_handler import attach_unit, get_attached_unit, get_attached_unit_str
from ahuora_builder.methods.property_map_manipulation import update_property
from pyomo.environ import units as u
from pint import UnitRegistry, Unit, Quantity

# This is used to recycle a value from one variable output to a variable input, between solves.
# This is because trying to model a recycle in steady state is sometimes unstable
# as you get into infinite loops where the heat just keeps going up and up.
# By recycling the value slowly, the PLC control system can be used to adjust and find a steady state.

class Recycle:
    def __init__(self, from_var: pyo.Var, to_var: pyo.Var, recycle_rate: float = 0.3):
        """
        from_var: variable to recycle from (an outlet, must be calculated)
        to_var: variable to recycle to (an inlet, must be a fixed var)
        recycle_rate: rate at which to recycle the value (0.0 to 1.0). 1.0 means recycle the entire value immediately,
        0 means never recycle, just use the original value.
        in between it averages between them. This controls the response time of the system (first order model).

        Eventually, we could make this more complex, e.g by adding a time delay aspect.
        """
        self.from_var = from_var
        self.to_var = to_var
        self.recycle_rate = recycle_rate

    def recycle(self):
        from_value = pyo.value(self.from_var)
        to_value = pyo.value(self.to_var)
        new_value = self.recycle_rate * from_value + (1 - self.recycle_rate) * to_value
        self.to_var.set_value(new_value)

        if math.fabs((from_value - to_value)/abs(from_value + to_value) * 2) > 0.01:  # Only log if values are more than 1% different
            print(f"Recycling: {from_value} -> {new_value} @ {self.to_var.name} {self.recycle_rate} = {new_value}")

def add_recycles(manager: FlowsheetManager):
    """
    Add "virtual" recycles to the model. Split at each tear stream, and deactivate the expanded arcs.
    Then add a recycle object to manually recycle those values.
    """
    recycles = []
    for arc in manager.tears._tears:
        # deactivate the expanded block
        arc.expanded_block.deactivate()

        source = arc.source
        for name, var in source.vars.items():
            index_set = var.index_set()
            
            for svar in index_set:
                from_var = var[svar]
                to_var = arc.destination.vars[name][svar]
                
                recycle = Recycle(from_var, to_var)
                recycles.append(recycle)
                to_var.fix()
    return recycles
    
            

# Note that for this to work you have to be careful where you put the recycles, and make sure there aren't any constraints around it
# that cause an over or under constrained set.