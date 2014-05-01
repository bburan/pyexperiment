Experiment paradigms
====================

Overivew
--------

The framework that these paradigms are built on allow the user to:
    
* Define the variables required for an experiment including their default
  value, label when shown in the GUI and whether the value on each trial should
  be logged.

* The value of a variable can be specified as an expression:

    * The expression can be based on the value of other variables

    * The expression can use generators so it can maintain it's state from
      trial to trial.  This allows for variables whose value is based on what
      was previously presented.

    * The expression can use random number generators to randomly select a
      value.

* The value of any variable can be changed during an experiment.  To ensure
  that changes don't take effect until you've finished updating all necessary
  variables, the changes are queued and take effect only when you hit the
  ``apply`` button.


The ability to specify values as expressions allows for some very flexible,
powerful experiment designs.

Defining an experiment
----------------------

An experiment is defined by three main classes, the `Controller`, `Experiment`
and `Paradigm`.  For historical reasons the experiment class is also a container
for an additional class, the `Data` class.  

Controller
    Defines the core logic of the experiment and is responsible for:

    * Configuring and controlling the hardware (e.g. water pump, DSP devices,
      attenuators) 

    * Responding to user input via the GUI (e.g. button presses or entry of a
      new value in a widget)

    For example, when a user clicks on the "start" button to begin a new
    experiment, the controller will create a new data file, configure the
    hardware and periodically poll the hardware and save acquired data to the
    file.

Paradigm
    The paradigm is a container that defines the variables needed by the
    experiment.

Data
    An object containing data acquired during an experiment.

Experiment
    Creates the GUI plots and lays out the GUI


Using expressions
-----------------

Many parameters defined in the paradigm can be defined as an expression that is
evaluated once per trial.  This allows you to randomize certain parameters,
base their value on the value of another parameter, or adjust the experiment
based on the performance of the subject. 

* Randomizing the required poke duration for initiating a trial by drawing from
  a uniform distribution between 200 and 400 msec::

    poke_duration = 'uniform(0.2, 0.4)'

* Set the probability of a go trial (in a go-nogo paradigm) to 0.5, but ensure
  that no more than five consecutive nogos are presented in a row::

    go_probability = '0.5 if c_nogo < 5 else 1.0'

* Set the lever that's extended to the same side as the cue light being
  presented::

    lever_side = 'cue_side'

* Randomly select between a 1 kHz tone or a 1 kHz bandwidth noise centered at
  2 kHz::

      center_frequency = 'choice([1e3, 2e3])'
      bandwidth = '0 if center_frequency == 1e3 else 1e3'

* Present another nogo if the subject false alarmed, otherwise set go
  probability to 0.5 unless there have been 5 nogos in a row::

    go_probability = '0 if fa else (0.5 if c_nogo < 5 else 1)'

The expressions can be any Python statement that can be evaluated in a single
line.  All expressions are evaluated in a namespace that contains both Python's
builtin functions along with others deemed useful for behavior experiments.
The value of each parameter is computed only once when get_current_value is
called.  The result is cached.

Available expressions
.....................

TODO

How the expressions work
........................

To compute the value only once per trial, you would do the following steps:

.. ipython:: python

    paradigm.poke_duration = 'uniform(0.2, 0.4)'
    print controller.get_current_value('poke_duration')
    0.321
    print controller.get_current_value('poke_duration')
    0.321
    controller.refresh_context()
    print controller.get_current_value('poke_duration')
    0.462

Both the aversive and appetitive controllers invalidate the cache after each
trial, forcing a recomputation of all expressions:

    paradigm.poke_duration = 0.5
    controller.refresh_context()
    print controller.get_current_value('poke_duration')
    0.743

Why is the poke_duration still set to a random value?  Remember that you must
apply any changes you make to the paradigm before they are reflected in the
actual experiment itself.  When you apply a change, the context cache is
invalidated, so there is no need to call invalidate_current_context as well:

    controller.apply()
    controller.get_current_value('poke_duration')
    0.5

Before you start the next trial, you must ensure that all remaining expressions
on the stack get evaluated as well:

    controller.evaluate_pending_expressions()

This is handled by :func:`AbstractExperimentController._apply_context_changes`.
The function gets called whenever the items in current_context change (e.g.
either items get added, removed or changed). 

When you call :func:`AbstractExperimentcontroller.invalidate_context`, this sets
current_context to an empty dictionary (e.g. the values are no longer valid
because they reflect the old trial and need to be recomputed).  When you call
:func:`AbstractExperimentController.evaluate_pending_expressions`, the new value
of each parameter is computed and added to current_context.  As the values are
added to current_context,
:func:`AbstractExperimentController._apply_context_changes` is called for each
addition and it checks to see if the value has changed since the last trial.  If
so, it calls `Controller.set_parameter_name` function with the new value.

.. note::
    
    If the value of a parameter is an expression, it will get recomputed before
    each trial.  However, if the result of the expression is the same as the
    prior trial, `Controller.set_parameter_name` will not be called.

Note that on the very first call to
`AbstractExperimentController.get_current_value` and
`AbstractExperimentController.evaluate_pending_expressions`, the prior value of
all context variables is None.  Therefore, the `Controller.set_parameter_name`
is called for every parameter defined in the paradigm.
