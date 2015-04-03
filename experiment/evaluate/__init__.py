from __future__ import division

import logging
log = logging.getLogger(__name__)

import re
from time import time
import types

import numpy as np
from traits.api import TraitType

from . import choice
from . import expr


class ParameterExpression(object):
    '''
    The namespace in which the function is evaluated includes all variables
    defined with `context=True` metadata in the `Paradigm`, `Controller` or
    `Data` class.
    '''

    # List of modules that are available to the expression namespace
    GLOBALS = {
        'time': time,
        'np': np,
    }

    # Include random sequence generators defined in this module
    GLOBALS.update(choice.options)

    # Include various convenience functions defined in the expressions module
    GLOBALS.update(expr.options)

    DEPENDENCY_PATTERN = re.compile(r'u\((.*), ([_A-Za-z][_A-Za-z0-9]*)\)')

    def __init__(self, value):
        self._original_expression = value
        self._next_when = None
        if isinstance(value, basestring):
            match = self.DEPENDENCY_PATTERN.match(value)
            if match is not None:
                self._expression, self._next_when = match.groups()
            else:
                self._expression = value

            self._code = compile(self._expression, '<string>', 'eval')
            self._cached_value = None
            self._generator = None
            self._dependencies = list(self._code.co_names)
            if self._next_when is not None:
                self._dependencies += [self._next_when]
            try:
                # Do a quick check to see if any syntax errors pop out.
                # NameError is going to be a common one (especially when we are
                # making it dependent on other modules).  If we can successfully
                # evaluate it and it does not depend on any values, then we
                # might as well cache the resulting value.
                eval(self._code, self.GLOBALS)
            except NameError:
                # This is the one error we will allow since it may suggest the
                # expression requires values not present in the global
                # namespace (but we don't know that for sure ...)
                pass
        else:
            self._dependencies = []
            self._expression = str(value)
            self._cached_value = value
            self._code = None
            self._generator = None

    def evaluate(self, local_context=None, dry_run=False, next_value=True):
        '''
        Evaluate expression given the provided context

        Parameters
        ----------
        local_context : { None, dict }
            Context to pass to `eval`
        dry_run : bool
            Don't cache result of eval.  Important if we have a generator
            expression and are doing an initial check to make sure that the
            list of expressions are valid.
        '''
        if self._generator is not None:
            if next_value:
                self._cached_value = self._generator.next()
            return self._cached_value

        if self._code is not None:
            value = eval(self._code, self.GLOBALS, local_context)
            if not dry_run and isinstance(value, types.GeneratorType):
                self._generator = value
                self._cached_value = self._generator.next()
            else:
                self._cached_value = value
        return self._cached_value

    def reset(self):
        if self._generator is not None:
            self._cached_value = None
            self._generator = None

    def __str__(self):
        return str(self._original_expression)

    def __repr__(self):
        return "{}".format(self._expression)

    # One must define both the == and != rich comparision methods for
    # on_trait_change to properly register trait changes while ignoring
    # situations where two ParameterExpressions have identical values.
    def __eq__(self, other):
        if not isinstance(other, ParameterExpression):
            return NotImplemented
        return self._expression == other._expression

    def __ne__(self, other):
        if not isinstance(other, ParameterExpression):
            return NotImplemented
        return self._expression != other._expression

    def __getstate__(self):
        '''
        Code objects cannot be pickled
        '''
        state = self.__dict__.copy()
        del state['_code']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if not self._cache_valid:
            self._code = compile(self._expression, '<string>', 'eval')
        else:
            self._code = None


class ExpressionNamespace(object):

    def __init__(self, expressions, extra_context=None, controller=None):
        self._cached_expressions = expressions
        self._catch = []
        for e in self._cached_expressions.values():
            if isinstance(e, ParameterExpression):
                if e._next_when is not None:
                    self._catch.append(e._next_when)
                e.reset()
        self._context = {}
        self.reset_values(extra_context)
        self.controller = controller

    def reset_values(self, extra_context=None):
        '''
        Reset all expressions so that they get reevaluated on the next call

        Parameters
        ----------
        context : {None, dict}
            If provided, evaluated values will be stored in this dictionary.
            This dictionary can also contain extra variables that will be
            provided to the evaluation namespace.
        '''
        self._extra_context = extra_context
        self._old_context = self._context
        self._context = {}
        self._expressions = self._cached_expressions.copy()
        self._changed_values = {}
        self._seq_end = [None]

    def reset_generator(self, value):
        self._cached_expressions[value].reset()

    def value_changed(self, parameter):
        old_value = self._old_context.get(parameter, None)
        new_value = self._context.get(parameter, None)
        return old_value != new_value

    def set_value(self, parameter, value):
        log.debug('Setting %s to %r', parameter, value)
        self._context[parameter] = value
        if self.value_changed(parameter):
            log.debug('Marking %s as changed', parameter)
            self._changed_values[parameter] = value

    def evaluate_values(self, extra_context=None, notify=True):
        while self._expressions:
            self.evaluate_value(self._expressions.keys()[0], extra_context)
            if notify:
                self._process_context_notifications()
                self.controller._update_current_context_list()
        return self._context

    def evaluate_value(self, parameter, extra_context=None, dry_run=False,
                       notify=True):
        value = self._evaluate_value(parameter, extra_context, dry_run)
        if notify:
            self._process_context_notifications()
            self.controller._update_current_context_list()
        return value

    def _process_context_notifications(self):
        '''
        Once an expression (and all dependencies) has been evaluated, go through
        and process the appropriate notifications.

        Note
        ----
        Historically, the context notifications were processed as each each
        expression was evaluated; however, this led to some edge-cases where
        evaluating a dependency expression and calling the notification
        triggered a recursive loop.
        '''
        while self._changed_values:
            k, v = self._changed_values.popitem()
            log.debug('Processing context notification for %s', k)
            setter = 'set_{}'.format(k)
            if hasattr(self.controller, setter):
                getattr(self.controller, setter)(v)

    def _evaluate_value(self, parameter, extra_context=None, dry_run=False):
        '''
        Given a stack of expressions and the desired parameter to evaluate,
        evaluates all the expressions necessary to evaluate the desired
        parameter.  If an expression is evaluated, it is removed from the stack
        of expressions and added to the context.
        '''
        log.debug('Evaluating value %s', parameter)

        # If the value of the requested parameter has already been computed and
        # stored in the context dictionary, return the context instead.
        if parameter in self._context:
            log.debug('Value found in context')
            return self._context[parameter]

        # Otherwise, find the expression that is used to compute the value of
        # the parameter.  Check to see if the parameter has any dependencies
        # (i.e., other unevaluated parameters that need to be comptued first).
        # If so, iterate through those.
        log.debug('Popping expression from stack')
        expression = self._expressions.pop(parameter)

        # Check whether this is a raw value rather than an Expression
        if not isinstance(expression, ParameterExpression):
            log.debug('Raw value provided, using value')
            self.set_value(parameter, expression)
            return expression

        # Evaluate the dependencies first.  Check to see if the dependency is in
        # self._expressions first since it may actually be part of the global
        # namespace (e.g. a function name).
        for d in expression._dependencies:
            if d in self._expressions:
                log.debug('Evaluating dependency %s for %s', d, parameter)
                self._evaluate_value(d, extra_context, dry_run)

        # TODO: how to deal with variables in extra_context that override
        # cached context variables?  Just use once and discard the value?
        log.debug('Preparing context for evaluating %s', parameter)
        context = self._context.copy()
        if self._extra_context is not None:
            context.update(self._extra_context)
        if extra_context is not None:
            context.update(extra_context)

        next_value = expression._next_when in self._seq_end
        try:
            value = expression.evaluate(context, dry_run, next_value)
            log.debug('Successfully computed value for %s', parameter)
        except StopIteration:
            log.debug('%s has reached end of sequence', parameter)
            if parameter in self._catch:
                log.debug('Resetting sequence for %s', parameter)
                expression.reset()
                self._seq_end.append(parameter)
                value = expression.evaluate(context, dry_run, next_value)
            else:
                raise
        self.set_value(parameter, value)
        return value


class Expression(TraitType):
    '''
    Enthought Traits type defining a value that can be evaluated
    '''
    info_text = 'a Python value or expression'
    default_value = ParameterExpression('None')

    def init(self):
        if not isinstance(self.default_value, ParameterExpression):
            self.default_value = ParameterExpression(self.default_value)

    def validate(self, obj, name, value):
        if isinstance(value, ParameterExpression):
            return value
        try:
            return ParameterExpression(value)
        except:
            self.error(obj, name, value)
