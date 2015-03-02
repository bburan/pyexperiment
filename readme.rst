PyExperiment
============

Experiment framework that provides rapid experiment GUI design and prototyping
using Enthought's Traits and TraitsUI system.  With a few lines of code, you
can define the parameters for your experiment and have them logged instantly to
a table in a HDF5 file as you run through each trial.  The framework supports:

* Specifying parameters as an expression, allowing for:

  * Dynamically computing the value of a parameter as a function of one or more
    other parameters.

  * Roving a parameter from trial to trial.

  * Using generators to provide a pre-determined parameter order (e.g.
    ascending, descending and/or blocked sequences).

* The value of parameters on each trial are automatically logged to a HDF5
  table.  Each row contains the value of all parameters for that given trial
  and the value of the expression that generated the parameter value (e.g. if
  you have a parameter called ``poke_duration`` that is set to ``random(0.2,
  0.4)``, it will save both the computed value as well as the expression
  string.

* Parameter expressions can be updated on-the-fly via the GUI (using an
  apply/revert button to ensure that changes are registered at the appropriate
  time).

* Built-in safety checks to ensure that you do not accidentally enter an
  invalid expression or circular reference in which the values of two
  parameters depend on each other.


Usage
-----

To use this framework you need to inherit from the
``experiment.AbstractController`` class and provide logic that is specific to
your experiment.  The superclass provides logic for handling changes to values
of the parameters on each trial.  These changes occur when the user modifies
the value in the GUI and hits the apply button or the value of the parameter is
specified by an expression whose output changse from trial to trial.

When the value changes, the controller needs to know how to handle this change.
For example, if you are using a infusion pump whose rate is programmable, then
you probably need to send a command via the serial port to update the pump rate
setting.  To provide this logic, define a method called ``set_parameter_name``
that takes a single argument (the updated value).

For example::

    def set_pump_rate(self, value):
        self.serial.writeln('RATE {:.4f}'.format(value))

At the beginning of every trial ``refresh_context`` should be called to set up
the paradigm variables.  Since the evaluation of expressions may depend, in
part, on values you provide via ``set_current_value``, expressions are not
evaluated until you call ``get_current_value``.  At some point before starting
the trial you should be sure to call ``evaluate_pending_expressions`` to be
sure the remaining values get computed.
