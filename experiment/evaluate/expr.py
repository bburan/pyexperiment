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


def imul(x, y):
    '''
    Coerce x to be an integer multiple of y
    '''
    x = np.asarray(x)
    return np.round(x/y)*y


def octave_space(start, end, spacing):
    '''

    Examples
    --------
    >>> print(octave_space(2e3, 16e3, 1))
    [2000.0, 4000.0, 8000.0, 16000.0]
    '''
    start_octave = np.log2(start/1e3)
    end_octave = np.log2(end/1e3)
    # Ensure that requested frequencies fall on the closest requested octave.
    start_octave = np.round(start_octave/spacing)*spacing
    end_octave = np.round(end_octave/spacing)*spacing
    i = np.arange(start_octave, end_octave+spacing, spacing)
    return (2**i)*1e3


options = {
    'toss':         toss,
    'h_uniform':    h_uniform,
    'choice':       choice,
    'imul':         imul,
    'octave_space': octave_space,
}
