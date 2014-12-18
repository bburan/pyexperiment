import unittest

import numpy as np
from traits.api import HasTraits, on_trait_change

from experiment.evaluate import (Expression, ParameterExpression,
                                 ExpressionNamespace, choice)


class TestExpressions(unittest.TestCase):

    def setUp(self):
        self.parameters = {
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
            'p':    ParameterExpression('ascending([0, 1, 2], cycles=1)'),
            'q':    ParameterExpression('ascending([3, 4, 5], cycles=1)',
                                        evaluate_when='p'),
            'r':    ParameterExpression('ascending([0, 1, 2], cycles=1)'),
        }
        self.ns = ExpressionNamespace(self.parameters)

    evaluate_value_tests = [
        ('a', {}, {'a': 5}),
        ('b', {}, {'b': 6}),
        ('c', {}, {'a': 5, 'c': 25}),
        ('d', {}, {'a': 5, 'b': 6, 'c': 25, 'd': 55}),
        # Test to ensure that the extra_context value for a does not override
        # the cached context value.
        ('d', {'a': 4}, {'a': 5, 'b': 6, 'c': 20, 'd': 44}),
        ('h', {}, {'h': 5}),
    ]

    def test_evaluate_all(self):
        result = self.ns.evaluate_values()
        # Remove the random variables
        result.pop('h')
        result.pop('i')
        result.pop('m')
        expected = dict(a=5, b=6, c=25, d=55, e=80, f=1.23, g=[5], j=57, k=65,
                        l=122, n=36, o=0, p=0, q=3, r=0)
        self.assertEqual(result, expected)

    # Ensure that generator objects remain 'stateful'
    def test_generator(self):
        sequence = []
        for i in range(36):
            sequence.append(self.ns.evaluate_value('m'))
            self.ns.reset_values()
        self.assertEqual(len(np.unique(np.bincount(sequence))), 1)

        sequence = []
        for i in range(9):
            sequence.append(self.ns.evaluate_value('o'))
            self.ns.reset_values()
        self.assertEqual(sequence, [0, 1, 2]*3)

    def test_generator_reset(self):
        breaks = 2, 6
        expected = [0, 1, 0, 1, 2, 0, 0, 1, 2]
        actual = []
        for i in range(9):
            if i in breaks:
                self.ns.reset_generator('o')
            actual.append(self.ns.evaluate_value('o'))
            self.ns.reset_values()
        self.assertEqual(actual, expected)

    def test_generator_requires(self):
        expected = [(0, 3), (1, 3), (2, 3),
                    (0, 4), (1, 4), (2, 4),
                    (0, 5), (1, 5), (2, 5),
                    ]
        # Be sure to test both p then q and q then p!  These tests are not
        # redundant as there have been exceptions in the past where order of
        # evaluation raised a subtle bug.
        sequence = []
        ns = ExpressionNamespace(self.parameters)
        for i in range(9):
            p = ns.evaluate_value('p')
            q = ns.evaluate_value('q')
            sequence.append((p, q))
            ns.reset_values()
        self.assertEqual(sequence, expected)

    def test_generator_requires_reverse(self):
        expected = [(0, 3), (1, 3), (2, 3),
                    (0, 4), (1, 4), (2, 4),
                    (0, 5), (1, 5), (2, 5),
                    ]
        sequence = []
        ns = ExpressionNamespace(self.parameters)
        for i in range(9):
            q = ns.evaluate_value('q')
            p = ns.evaluate_value('p')
            sequence.append((p, q))
            ns.reset_values()
        self.assertEqual(sequence, expected)

    def test_simple_generator_stopiteration(self):
        for i in range(3):
            self.ns.evaluate_value('r')
            self.ns.reset_values()
        self.assertRaises(StopIteration, self.ns.evaluate_value, 'r')

    def test_paired_generator_stopiteration(self):
        # Ensure that we get the StopIteration once the sequence has been
        # exhausted.
        for i in range(9):
            self.ns.evaluate_value('q')
            self.ns.reset_values()
        self.assertRaises(StopIteration, self.ns.evaluate_value, 'q')

    # Test the expression evaluation system
    def test_evaluate_value(self):
        for parameter, extra_context, expected in self.evaluate_value_tests:
            self.ns.evaluate_value(parameter, extra_context)
            self.assertEqual(expected, self.ns._context)
            for parameter in expected:
                self.assertTrue(parameter not in self.ns._expressions)
            self.ns.reset_values()

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


class TestChoice(unittest.TestCase):

    def get_seq(self, sequence, selector, n=1):
        choice = selector(sequence)
        return [choice.next() for i in range(len(sequence)*n)]

    def setUp(self):
        self.seq = [1, 3, 8, 9, 12, 0, 4]

    def test_shuffled_set(self):
        seq = self.get_seq(self.seq, choice.shuffled_set)
        self.assertEqual(set(seq), set(self.seq))
        seq = self.get_seq(self.seq, choice.shuffled_set, 2)

    def test_cycles(self):
        basic_selectors = (choice.ascending, choice.descending,
                           choice.exact_order, choice.shuffled_set)
        for selector in basic_selectors:
            # Ensure that we get a StopIteration error
            c = selector(self.seq, cycles=1)
            for i in range(len(self.seq)):
                c.next()
            self.assertRaises(StopIteration, c.next)

            # Ensure we don't get an error at all
            c = selector(self.seq, cycles=np.inf)
            for i in range(len(self.seq)):
                c.next()
            c.next()

            # Ensure we don't get an error at all
            c = selector(self.seq, cycles=2)
            for j in range(2):
                for i in range(len(self.seq)):
                    c.next()
            self.assertRaises(StopIteration, c.next)


if __name__ == '__main__':
    unittest.main()
