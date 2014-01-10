from __future__ import division

import logging
log = logging.getLogger(__name__)

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
            'time':             time,
            'np':               np,
            }

    # Include random sequence generators defined in this module
    GLOBALS.update(choice.options)

    # Include various convenience functions defined in the expressions module
    GLOBALS.update(expr.options)

    def __init__(self, value):
        if isinstance(value, basestring):
            self._expression = value
            self._code = compile(self._expression, '<string>', 'eval')
            self._dependencies = self._code.co_names

            self._cache_valid = False
            self._cached_value = None
            self._generator = False

            try:
                # Do a quick check to see if any syntax errors pop out.
                # NameError is going to be a common one (especially when we are
                # making it dependent on other modules).  If we can successfully
                # evaluate it and it does not depend on any values, then we
                # might as well cache the resulting value.
                result = eval(self._code, self.GLOBALS)

            except NameError:
                # This is the one error we will allow since it may suggest the
                # expression requires values not present in the global
                # namespace (but we don't know that for sure ...)
                pass
        else:
            self._dependencies = []
            self._expression = str(value)
            self._cache_valid = True
            self._cached_value = value
            self._code = None
            self._generator = False

    def evaluate(self, local_context=None, dry_run=False):
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
        if self._generator:
            return self._cached_value.next()
        elif self._cache_valid:
            return self._cached_value
        else:
            value = eval(self._code, self.GLOBALS, local_context)
            if not dry_run and isinstance(value, types.GeneratorType):
                self._generator = True
                self._cached_value = value
                return value.next()
            else:
                return value

    def reset(self):
        self._cached_value = None
        self._cache_valid = False
        self._generator = False

    def __str__(self):
        return self._expression

    def __repr__(self):
        return "{} ({})".format(self._expression, self._cache_valid)

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


def evaluate_value(parameter, expressions, context=None, dry_run=False):
    '''
    Given a stack of expressions and the desired parameter to evaluate,
    evaluates all the expressions necessary to evaluate the desired parameter.
    If an expression is evaluated, it is removed from the stack of expressions
    and added to the context.
    '''
    if context is None:
        context = {}

    # If the value of the requested parameter has already been computed and
    # stored in the context dictionary, remove it from the expression stack and
    # return the cached value.
    if parameter in context:
        expressions.pop(parameter)
        return context

    # Otherwise, find the expression that is used to compute the value of the
    # parameter.  Check to see if the parameter has any dependencies (i.e.
    # other unevaluated parameters that need to be comptued first).  If so,
    # iterate through those.
    expression = expressions.pop(parameter)
    if isinstance(expression, ParameterExpression):
        for d in expression._dependencies:
            if d in expressions:
                evaluate_value(d, expressions, context)
        context[parameter] = expression.evaluate(context, dry_run=dry_run)
    else:
        context[parameter] = expression
    return context


def evaluate_expressions(expressions, current_context, dry_run=False):
    '''
    Will raise a NameError if it is no longer able to evaluate.
    '''
    while expressions:
        name = expressions.keys()[0]
        evaluate_value(name, expressions, current_context, dry_run)


class Expression(TraitType):
    '''
    Enthought Traits type defining a value that can be evaluated
    '''
    info_text = 'a Python value or expression'
    default_value = ParameterExpression('None')

    def post_setattr(self, object, name, value):
        if not isinstance(value, ParameterExpression):
            value = ParameterExpression(value)
            object.__dict__[name] = value

    def init(self):
        if not isinstance(self.default_value, ParameterExpression):
            self.default_value = ParameterExpression(self.default_value)

    def validate(self, object, name, value):
        if isinstance(value, ParameterExpression):
            return value
        try:
            return ParameterExpression(value)
        except:
            self.error(object, name, value)
