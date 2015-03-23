import os
os.environ['ETS_TOOLKIT'] = 'null'

import logging
log = logging.getLogger(__name__)

from traits.api import (HasTraits, Dict, List, Any, Bool, on_trait_change, Int,
                        Enum)
from traitsui.api import TabularEditor, Controller
from traitsui.tabular_adapter import TabularAdapter
from pyface.api import confirm, YES, error, FileDialog, OK

from .evaluate import ExpressionNamespace
from . import util

COLOR_NAMES = {
    'light green': '#98FB98',
    'dark green': '#2E8B57',
    'light red': '#FFC8CB',
    'dark red': '#FA8072',
    'gray': '#D3D3D3',
    'light blue': '#ADD8E6',
    'white': '#FFFFFF',
    }


def depends_on(*dependencies):
    '''
    Decorator for methods on the abstract controller that need to ensure that
    the value of an expression is computed and applied first.
    '''
    def decorator(f):
        def wrapper(self, *args, **kw):
            for d in dependencies:
                self.get_current_value(d)
            return f(self, *args, **kw)
        return wrapper
    return decorator


class ContextAdapter(TabularAdapter):

    columns = ['Parameter', 'Value', 'Variable']

    def get_image(self, obj, trait, row, column):
        if column == 0 and self.item[-2]:
            return '@icons:tuple_node'

    def get_width(self, obj, trait, column):
        return 100

    def get_bg_color(self, obj, trait, row, column=0):
        if self.item is not None and self.item[-1]:
            return COLOR_NAMES['light green']
        else:
            return COLOR_NAMES['white']


context_editor = TabularEditor(adapter=ContextAdapter(), editable=False)


class ApplyRevertControllerMixin(HasTraits):
    '''
    Logic for updating parameters on the fly via a GUI
    '''
    # Boolean flag indicating whether there are any changes to paradigm
    # variables that have not been applied.  Currently the apply/revert logic is
    # not smart enough to handle cases where the user makes a sequence of
    # changes that results in the final value being equivalent to the original
    # value.
    pending_changes = Bool(False)

    # A shadow copy of the paradigm where the current values used for the
    # experiment are stored.  The copy of the paradigm at info.object.paradigm
    # is a separate copy that is currently being edited via the GUI.  Updated
    # expressions and values as entered via the GUI are copied over only when
    # the apply button is pressed.
    shadow_paradigm = Any

    # List of expressions that have not yet been evaluated.
    pending_expressions = Dict

    # The current value of all context variables
    current_context = Dict

    # Label of the corresponding variable to use in the GUI
    context_labels = Dict

    # Should the context variable be logged?
    context_log = Dict

    # Copy of the old context.  Used for comparing with the current context to
    # determine if a value has changed.  If a value has not changed, then
    # the set_<parametername> method will not be called.
    old_context = Dict

    # List of name, value, label tuples (used for displaying in the GUI)
    current_context_list = List

    extra_context = Dict

    def is_running(self):
        raise NotImplementedError

    @on_trait_change('model.paradigm.+container*.+context, +context')
    def handle_change(self, instance, name, old, new):
        # When a paradigm value has changed while the experiment is running,
        # indicate that changes are pending
        if not self.is_running():
            return
        log.debug('Detected change to %s', name)
        trait = instance.trait(name)
        if trait.immediate:
            self.set_current_value(name, new)
        else:
            self.pending_changes = True

    def refresh_context(self, extra_context=None, evaluate=False):
        '''
        Stores a copy of `current_context` in `old_context`, wipes
        `current_context`, and reloads the expressions from the paradigm.

        This will force the program to re-evaluate any values that may have
        changed.  Be sure to call `evaluate_pending_expressions` to finish.

        Parameters
        ----------
        extra_context : { None or dict }
            Dictionary of parameter-value pairs that should be included in the
            expression context.
        evaluate : bool
            Automatically re-evaluate expressions.  This can usually be set to
            True unless you need to provide additional context (e.g. via
            `set_current_value`) before computing some expressions.  If set to
            False, be sure to call `evaluate_pending_expressions` before the
            next trial begins.
        '''
        log.debug('Refreshing context')
        self.old_context = self.current_context.copy()
        self.current_context = self.trait_get(context=True)
        try:
            self.current_context.update(self.model.data.trait_get(context=True))
        except AttributeError:
            pass
        self.namespace.reset_values(self.current_context)
        if extra_context is not None:
            for k, v in extra_context.items():
                self.set_current_value(k, v)
        if evaluate:
            self.evaluate_pending_expressions()

    def apply(self, info=None):
        '''
        This method is called when the apply button is pressed
        '''
        log.debug('Applying requested changes')
        try:
            # First, we do a quick check to ensure the validity of the
            # expressions the user entered by evaluating them.  If the
            # evaluation passes, we will make the assumption that the
            # expressions are valid as entered.  However, this will *not* catch
            # all edge cases or situations where actually applying the change
            # causes an error.
            pending_expressions = self.model.paradigm.trait_get(context=True)
            current_context = self.model.data.trait_get(context=True)

            ns = ExpressionNamespace(pending_expressions, current_context)
            ns.evaluate_values(dry_run=True)

            # If we've made it this far, then let's go ahead and copy the
            # changes over to our shadow_paradigm.  We'll apply the requested
            # changes immediately if a trial is not currently running.
            self.shadow_paradigm.copy_traits(self.model.paradigm)
            self.pending_changes = False
            self.namespace = ns

            # Subclasses need to define this function (e.g.
            # abstract_positive_controller and abstract_aversive_controller)
            # because only those subclases know when it's safe to apply the
            # changes (e.g. the positive paradigms will check to make sure that
            # a trial is not running before applying the changes).
            self.context_updated()
        except Exception, e:
            # A problem occured when attempting to apply the context.
            # the changes and notify the user.  Hopefully we never reach this
            # point.
            log.exception(e)
            mesg = '''
            Unable to apply your requested changes due to an error.  No changes
            have been made. Please review the changes you have requested to
            ensure that they are indeed valid.'''
            import textwrap
            mesg = textwrap.dedent(mesg).strip().replace('\n', ' ')
            mesg += '\n\nError message: ' + str(e)
            error(info.ui.control, message=mesg, title='Error applying changes')

    def context_updated(self):
        '''
        This can be overriden in subclasses to implement logic for updating the
        experiment when the apply button is pressed
        '''
        pass

    def revert(self, info=None):
        '''
        Revert GUI fields to original values
        '''
        log.debug('Reverting requested changes')
        self.model.paradigm.copy_traits(self.shadow_paradigm)
        self.pending_changes = False

    def value_changed(self, name):
        new_value = self.get_current_value(name)
        old_value = self.old_context.get(name, None)
        return new_value != old_value

    def get_current_value(self, name):
        '''
        Get the current value of a context variable.  If the context variable
        has not been evaluated yet, compute its value from the
        pending_expressions stack.  Additional context variables may be
        evaluated as needed.
        '''
        return self.namespace.evaluate_value(name)

    def set_current_value(self, name, value):
        self.current_context[name] = value

    def evaluate_pending_expressions(self, extra_context=None):
        '''
        Evaluate all pending expressions and store results in `current_context`.

        If extra_content is provided, it will be included in the local
        namespace. If extra_content defines the value of a parameter also
        present in pending_expressions, the value stored in extra_context takes
        precedence.
        '''
        log.debug('Evaluating pending expressions')
        try:
            self.current_context.update(self.model.data.trait_get(context=True))
        except AttributeError:
            pass
        self.namespace.evaluate_values(extra_context)

    @on_trait_change('current_context_items')
    def _apply_context_changes(self, event):
        '''
        Automatically apply changes as expressions are evaluated and their
        result added to the context
        '''
        names = event.added.keys()
        names.extend(event.changed.keys())
        for name in names:
            old_value = self.old_context.get(name, None)
            new_value = self.current_context.get(name)
            if old_value != new_value:
                mesg = 'changed {} from {} to {}'
                log.debug(mesg.format(name, old_value, new_value))

                # I used to have this in a try/except block (i.e. using the
                # Python idiom of "it's better to ask for forgiveness than
                # permission").  However, it quickly became apparent that this
                # was masking Exceptions that may be raised in the body of the
                # setter functions.  We should let these exceptions bubble to
                # the surface so the user has more information about what
                # happened.
                setter = 'set_{}'.format(name)
                if hasattr(self, setter):
                    getattr(self, setter)(new_value)
                    log.debug('setting %s', name)
                else:
                    log.debug('no setter for %s', name)

    @on_trait_change('current_context_items')
    def _update_current_context_list(self):
        context = []
        for name, value in self.current_context.items():
            label = self.context_labels.get(name, '')
            changed = not self.old_context.get(name, None) == value
            log = self.context_log[name]
            if type(value) in ((type([]), type(()))):
                str_value = ', '.join('{}'.format(v) for v in value)
                str_value = '[{}]'.format(str_value)
            else:
                str_value = '{}'.format(value)
            context.append((name, str_value, label, log, changed))
        self.current_context_list = sorted(context)

    def _add_context(self, instance):
        for name, trait in instance.traits(context=True).items():
            log.debug('Found context variable {}'.format(name))
            self.context_labels[name] = trait.label
            self.context_log[name] = trait.log

    def initialize_context(self):
        log.debug('Initializing context')

        # Go through the various objects and pull in context information from
        # each.  There really should be a better way to accomplish the same
        # purpose.
        try:
            self._add_context(self.model.data)
        except AttributeError:
            pass
        try:
            self._add_context(self.model.paradigm)
        except AttributeError:
            pass
        try:
            self._add_context(self.model.self)
        except AttributeError:
            pass

        self.shadow_paradigm = self.model.paradigm.clone_traits()
        expressions = self.shadow_paradigm.trait_get(context=True)
        self.namespace = ExpressionNamespace(expressions,
                                             extra_context=self.extra_context)

    def log_trial(self, **kwargs):
        '''
        Add entry to trial log table
        '''
        log.debug('Logging trial')
        for key, value in self.context_log.items():
            if value:
                kwargs[key] = self.current_context[key]
        for key, value in self.shadow_paradigm.trait_get(context=True).items():
            kwargs['expression_{}'.format(key)] = '{}'.format(value)
        self.model.data.log_trial(**kwargs)

    def get_dtypes(self):
        '''
        Return list of dtypes that may be added manually in the controller code.
        This is in addition to the dtypes auto-discovered on the paradigm.
        '''
        return self.extra_dtypes if hasattr(self, 'extra_dtypes') else []

    def register_dtypes(self):
        dtypes = self.model.paradigm.get_dtypes()
        dtypes.extend(self.get_dtypes())
        e_names = self.model.paradigm.trait_get(context=True).keys()
        e_names = ['expression_{}'.format(e) for e in e_names]
        e_types = ['S256']*len(e_names)
        dtypes.extend(zip(e_names, e_types))
        self.model.data.register_dtypes(dtypes)


class AbstractController(ApplyRevertControllerMixin, Controller):

    current_trial = Int(0)
    stop_requested = Bool(False)
    pause_requested = Bool(False)

    '''
    These four states determine what actions are allowed:

        uninitialized
            The experiment is not ready to start because some hardware or
            software required for running the experiment has not been
            configured yet.

        initialized
            The experiment is ready to start as soon as the user hits the start
            button.

        running
            The experiment is running.  At this point, any changes to
            parameters must be applied by hitting the "apply" button.  In
            addition, closing the experiment window will generate a
            confirmation pop-up.

        paused
            The experient is paused.

        halted
            The experiment is done and all data has been saved.
    '''

    state = Enum('uninitialized', 'initialized', 'running', 'paused', 'halted')

    def init(self, info):
        super(AbstractController, self).init(info)
        self.model = info.object

    def ok_to_shutdown(self):
        return not self.is_running()

    def is_running(self):
        return self.state == 'running'

    def close(self, info, is_ok):
        '''
        Prevent user from closing window while an experiment is running since
        some data is not saved to file until the stop button is pressed.
        '''
        # First, check to see if it's OK to shutdown the experiemnt.  Since
        # each experiment will define their own rules, it's up to the
        # subclass to define the proper implementation of this method.
        if self.ok_to_shutdown():
            return True

        # We can abort a close event by returning False.  Confirm that the user
        # really did want to close the window.
        mesg = 'Are you sure you want to exit?'

        # The function confirm returns an integer that represents the response
        # that the user requested.  YES is a constant (also imported from the
        # same module as confirm) corresponding to the return value of confirm
        # when the user presses the "yes" button on the dialog.  If any other
        # button (e.g. "no", "abort", etc.) is pressed, the return value will be
        # something other than YES and we will assume that the user has
        # requested not to quit the experiment.
        if confirm(info.ui.control, mesg) != YES:
            return False
        else:
            # Call the shutdown routines to ensure that data is saved.
            self.stop(info)
            return True

    def log_event(self, event, ts=None):
        if ts is None:
            ts = self.get_ts()
        self.model.data.log_event(ts, event)
        log.debug("EVENT: %.2f, %s", ts, event)

    def start(self, info=None):
        self.initialize_context()
        self.setup_experiment(info)
        self.start_experiment(info)
        self.state = 'running'

    def stop(self, info=None):
        self.state = 'halted'
        self.stop_experiment()

    def pause(self, info=None):
        raise NotImplementedError

    def resume(self, info=None):
        self.state = 'running'
        self.pause_requested = False
        self.next_trial()

    def request_stop(self, info=None):
        self.stop_requested = True

    def request_pause(self, info=None):
        self.pause_requested = True

    def next_trial(self):
        '''
        At the beginning of every trial `refresh_context` should be called to
        set up the paradigm variables.  Since the evaluation of expressions may
        depend, in part, on values you provide via `set_current_value`,
        expressions are not evaluated until you call `get_current_value`.  At
        some point before starting the trial you should be sure to call
        `evaluate_pending_expressions` to be sure the remaining values get
        computed.
        '''
        raise NotImplementedError
        self.refresh_context()
        self.current_trial += 1

    def setup_experiment(self, info=None):
        '''
        At a bare minimum this function should call `self.register_dtypes` to
        ensure that the trial_log table is properly initialized with the
        correct type for each column.

        Often you may need to override this method initialize hardware.
        '''
        self.register_dtypes()
        self.state = 'initialized'

    def start_experiment(self, info=None):
        '''
        Can be as simple as calling `self.next_trial`.
        '''
        self.next_trial()

    def stop_experiment(self, info=None):
        '''
        Stop experiment should be inside a guard block (self.is_running()) to
        ensure that multiple calls to this method (e.g. from other threads or
        from repeated pressing of the stop button) do not enter this block.
        '''
        raise NotImplementedError
        if self.is_running():
            self.model.data.save()

    def save_paradigm(self, path, wildcard, info=None):
        wildcard_base = wildcard.split('|')[1][1:]
        fd = FileDialog(action='save as', default_directory=path,
                        wildcard=wildcard)
        if fd.open() == OK and fd.path:
            if not fd.path.endswith(wildcard_base):
                fd.path += wildcard_base
            self.model.paradigm.write_json(fd.path)

    def load_paradigm(self, path, wildcard, info=None):
        fd = FileDialog(action='open', default_directory=path,
                        wildcard=wildcard)
        if fd.open() == OK and fd.path:
            self.model.paradigm.read_json(fd.path)
