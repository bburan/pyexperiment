import logging
log = logging.getLogger(__name__)

import time
import numpy as np

'''
Generators and Coroutines
-------------------------
The code below uses generators and coroutines.  For an overview, see the
following resources:

http://www.dabeaz.com/coroutines/
http://www.python.org/dev/peps/pep-0342/
'''

################################################################################
# UTILITY FUNCTIONS
################################################################################
def coroutine(func):
    '''Decorator to auto-start a coroutine.'''
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        cr.next()
        return cr
    return start


def create_pipeline(*args):
    current = args[-1]
    # Initialize final step in pipeline if it hasn't been already.
    if hasattr(current, '__call__'):
        current = current()
    for b in args[-2::-1]:
        current = b(current)
    return current


################################################################################
# Coroutines
################################################################################
@coroutine
def block_average(block_size, axis, target):
    data = (yield)
    while True:
        while data.shape[axis] >= block_size:
            s = [Ellipsis]*data.ndim
            s[axis] = np.s_[:block_size]
            target.send(data[s].mean(axis=axis))
            s[axis] = np.s_[block_size:]
            data = data[s]
        new_data = (yield)
        data = np.concatenate((data, new_data), axis=axis)


@coroutine
def blocked(block_size, axis, target):
    data = (yield)
    while True:
        while data.shape[axis] >= block_size:
            s = [Ellipsis]*data.ndim
            s[axis] = np.s_[:block_size]
            target.send(data[s])
            s[axis] = np.s_[block_size:]
            data = data[s]
        new_data = (yield)
        data = np.concatenate((data, new_data), axis=axis)


@coroutine
def accumulate(n, target):
    data = []
    while True:
        d = (yield)[np.newaxis]
        data.append(d)
        if len(data) == n:
            data = np.concatenate(data)
            target.send(data)
            data = []


@coroutine
def reshape(new_shape, target):
    while True:
        data = (yield)
        target.send(data.reshape(new_shape))


@coroutine
def rms(axis, target):
    while True:
        data = (yield)
        rms = np.mean(data**2, axis=axis)**0.5
        target.send(rms)


@coroutine
def db(reference, target):
    while True:
        data = (yield)
        target.send(20*np.log10(data/reference))


class counter(object):

    def __init__(self, callback):
        self._callback = callback
        self.n = 0

    def send(self, data):
        try:
            self.n += len(data)
            if self._callback is not None:
                self._callback(self.n)
        except Exception as e:
            log.exception(e)
            raise GeneratorExit


@coroutine
def broadcast(*targets):
    while True:
        input = (yield)
        for target in targets:
            target.send(input)


################################################################################
# SINKS
################################################################################
@coroutine
def printer():
    while True:
        print (yield),


@coroutine
def call(target):
    while True:
        data = (yield)
        target(data)
