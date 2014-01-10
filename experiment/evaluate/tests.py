import unittest

import numpy as np
from traits.api import HasTraits, on_trait_change

from . import Expression, ParameterExpression, evaluate_value


class TestExpressions(unittest.TestCase):

    parameters = {
            'a':    ParameterExpression('5'),
            'b':    ParameterExpression('6'),
            'c':    ParameterExpression('a*5'),
            'd':    ParameterExpression('a*b+c'),
            'e':    ParameterExpression('d+c'),
            'f':    ParameterExpression('1.23'),
            'g':    ParameterExpression('range(a, b)'),
            'h':    ParameterExpression('np.random.randint(5, 6)'),
            'i':    ParameterExpression('np.random.uniform(1, 5)'),
            'j':    57,
            'k':    65,
            'l':    ParameterExpression('j+k'),
            'm':    ParameterExpression('counterbalanced([0, 1, 2], n)'),
            'n':    36,
            'o':    ParameterExpression('ascending([0, 1, 2])'),
            }

    evaluate_value_tests = [
            ('a', {}, {'a': 5}),
            ('b', {}, {'b': 6}),
            ('c', {}, {'a': 5, 'c': 25}),
            ('d', {}, {'a': 5, 'b': 6, 'c': 25, 'd': 55}),
            ('d', {'a': 4}, {'a': 4, 'b': 6, 'c': 20, 'd': 44}),
            ('h', {}, {'h': 5}),
            ]

    # Ensure that generator objects remain 'stateful'
    def test_generator(self):
        sequence = []
        for i in range(36):
            parameters = self.parameters.copy()
            sequence.append(evaluate_value('m', parameters)['m'])
        self.assertEqual(len(np.unique(np.bincount(sequence))), 1)

        sequence =[]
        for i in range(9):
            parameters = self.parameters.copy()
            sequence.append(evaluate_value('o', parameters)['o'])
        self.assertEqual(sequence, [0, 1, 2]*3)

    def test_generator_reset(self):
        breaks = 2, 6
        expected = [0, 1, 0, 1, 2, 0, 0, 1, 2]
        actual = []
        for i in range(9):
            if i in breaks:
                self.parameters['o'].reset()
            parameters = self.parameters.copy()
            actual.append(evaluate_value('o', parameters)['o'])
        self.assertEqual(actual, expected)

    # Test the expression evaluation system
    def test_evaluate_value(self):
        for parameter, extra_context, expected in self.evaluate_value_tests:
            parameters = self.parameters.copy()
            actual = evaluate_value(parameter, parameters, extra_context)
            self.assertEqual(expected, actual)
            for parameter in expected:
                self.assertTrue(parameter not in parameters)

    def test_equal(self):
        a = ParameterExpression('a+b')
        b = ParameterExpression('a+b')
        self.assertEqual(a, b)

    def test_assignment(self):
        obj = TestTraits()
        obj.a = 'a+5'


class TestTraits(HasTraits):

    a = Expression('a+4', context=True)

    @on_trait_change('a')
    def print_change(self):
        print 'changed'


if __name__ == '__main__':
    import unittest
    unittest.main()
