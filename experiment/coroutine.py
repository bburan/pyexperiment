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

    def __init__(self, callback, target):
        self._target = target
        self._callback = callback
        self.n = 0

    def send(self, data):
        try:
            self.n += len(data)
            self._target.send(data)
            if self._callback is not None:
                self._callback(self.n)
        except:
            raise GeneratorExit


################################################################################
# SINKS
################################################################################
@coroutine
def printer():
    while True:
        print (yield),


@coroutine
def accumulate(data, n):
    acquired = 0
    while True:
        if acquired >= n:
            raise GeneratorExit
        d = (yield)
        acquired += 1
        data.append(d)
