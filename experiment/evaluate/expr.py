from __future__ import division

import numpy as np


def choice(sequence):
    '''
    Randomly return a single value, with replacement, from the sequence

    For more sophisticated selection algorithms, see the functions provided by
    `experiment.evaluate.choice`.
    '''
    i = np.random.randint(0, len(sequence))
    return sequence[i]


def h_uniform(x, lb, ub):
    '''
    Assuming a uniform distribution, return the probability of an event occuring
    at that given sample (i.e. the hazard probability).

    >>> h_uniform(0, 3, 7)
    0.0
    >>> h_uniform(3, 3, 7)
    0.25
    >>> h_uniform(4, 3, 7)
    0.3333333333333333
    >>> h_uniform(6, 3, 7)
    1.0
    >>> h_uniform(7, 3, 7)
    1.0
    '''
    if x < lb:
        return 0.0
    if x >= ub:
        return 1.0
    return 1.0/(ub-x)


def toss(x=0.5):
    '''
    Flip a coin weighted by x
    '''
    return np.random.uniform() <= x


def imult(x, y):
    '''
    Coerce x to be an integer multiple of y
    '''
    return round(x/y)*y


options = {
    'toss':         toss,
    'h_uniform':    h_uniform,
    'choice':       choice,
    'imult':        imult,
}
