import unittest

import tables

from experiment import (AbstractData, AbstractParadigm, AbstractController,
                        AbstractExperiment, depends_on)
from experiment.evaluate import Expression, ParameterExpression, choice, expr

import numpy as np


class TestParadigm(AbstractParadigm):

    kw = dict(context=True, log=True)
    f1_frequency = Expression('f2_frequency/1.2', **kw)
    f2_frequency = Expression(8e3, **kw)
    level = Expression('exact_order(np.arange(0, 10, 5), c=1)', **kw)
    trials = Expression('exact_order(np.arange(0, 10, 1), c=1)', **kw)
    gain = Expression(32, **kw)
    atten = Expression(0, **kw)

    f3_frequency = Expression(
        'u(exact_order(np.arange(0, 10, 5), c=1), f3_level)', **kw)
    f3_level = Expression('exact_order([0, 1, 2])', **kw)


class TestController(AbstractController):

    def __init__(self, *args, **kw):
        self.order = []
        super(TestController, self).__init__(*args, **kw)

    def next_trial(self):
        self.refresh_context()

    @depends_on('level', 'atten')
    def set_f1_frequency(self, f1_frequency):
        self.order.append('f1_frequency')

    @depends_on('level')
    def set_f2_frequency(self, f1_frequency):
        self.order.append('f2_frequency')

    @depends_on('gain')
    def set_level(self, level):
        self.order.append('level')

    def set_gain(self, gain):
        self.order.append('gain')

    @depends_on('trials')
    def set_atten(self, atten):
        self.order.append('atten')

    def set_trials(self, trials):
        self.order.append('trials')

    def set_f3_level(self, f3_level):
        f3_frequency = self.get_current_value('f3_frequency')
        self.order.append('f3_level')


class TestABCSystem(unittest.TestCase):

    def setUp(self):
        self.fh = tables.open_file('dummy_name', 'w', driver='H5FD_CORE',
                                   driver_core_backing_store=0)
        self.data = AbstractData(store_node=self.fh.root)
        self.controller = TestController()
        self.paradigm = TestParadigm()
        self.experiment = AbstractExperiment(paradigm=self.paradigm,
                                             data=self.data)
        self.experiment.edit_traits(handler=self.controller)

    def tearDown(self):
        self.fh.close()

    def test_next_value(self):
        self.controller.start()
        # Test initial round of values
        actual = self.controller.get_current_value('f1_frequency')
        self.assertEqual(8e3/1.2, actual)
        actual = self.controller.get_current_value('f2_frequency')
        self.assertEqual(8e3, actual)
        self.assertEqual(0, self.controller.get_current_value('level'))

        # Test next round
        self.controller.next_trial()
        self.controller.evaluate_pending_expressions()
        expected = {'f2_frequency': 8e3, 'f1_frequency': 8e3/1.2, 'level': 5,
                    'gain': 32, 'atten': 0, 'trials': 1, 'f3_level': 0,
                    'f3_frequency': 0}
        self.assertEqual(self.controller.namespace._context, expected)

        # Test generator exhaustion
        self.controller.next_trial()
        self.assertRaises(StopIteration,
                          self.controller.evaluate_pending_expressions)

    def test_chained_next_value(self):
        exp = ParameterExpression('u(exact_order([2e3, 9e3], c=1), level)')
        self.paradigm.f2_frequency = exp
        self.controller.start()
        frequencies = []
        levels = []
        for i in range(4):
            levels.append(self.controller.get_current_value('level'))
            frequencies.append(
                self.controller.get_current_value('f2_frequency'))
            self.controller.next_trial()
        self.assertEqual([2e3, 2e3, 9e3, 9e3], frequencies)
        self.assertEqual([0, 5, 0, 5], levels)
        self.assertRaises(StopIteration,
                          self.controller.evaluate_pending_expressions)

    def test_generator_expression(self):
        expr = 'u(asc(imul([1.1e3, 2.2e3], 1e3), c=1), level)'
        self.paradigm.f2_frequency = ParameterExpression(expr)
        self.controller.start()
        frequencies = []
        levels = []
        for i in range(4):
            levels.append(self.controller.get_current_value('level'))
            frequencies.append(
                self.controller.get_current_value('f2_frequency'))
            self.controller.next_trial()
        self.assertEqual([1e3, 1e3, 2e3, 2e3], frequencies)
        self.assertEqual([0, 5, 0, 5], levels)
        self.assertRaises(StopIteration,
                          self.controller.evaluate_pending_expressions)

    def test_custom_context(self):
        def dp_freq(start, end, octave_spacing, probe_duration, c=1):
            start_octave = np.log2(start/1e3)
            end_octave = np.log2(end/1e3)
            i = np.arange(start_octave, end_octave+octave_spacing,
                          octave_spacing)
            frequencies = (2**i)*1e3
            frequencies = expr.imul(frequencies, 1/probe_duration)
            return choice.ascending(frequencies, c=c)
        self.controller.extra_context['dp_freq'] = dp_freq
        self.controller.extra_context['probe_duration'] = 50e-3

        expression = 'u(dp_freq(4e3, 16e3, 1, probe_duration), level)'
        self.paradigm.f2_frequency = ParameterExpression(expression)
        self.controller.start()
        frequencies = []
        levels = []
        for i in range(6):
            levels.append(self.controller.get_current_value('level'))
            frequencies.append(
                self.controller.get_current_value('f2_frequency'))
            self.controller.next_trial()
        self.assertEqual([4e3, 4e3, 8e3, 8e3, 16e3, 16e3], frequencies)
        self.assertEqual([0, 5, 0, 5, 0, 5], levels)
        self.assertRaises(StopIteration,
                          self.controller.evaluate_pending_expressions)

    def test_nested_eval(self):
        # Ensure that a value (f3_frequency) which depends on f3_level does not
        # enter infinite recursion when set_f3_level attempts to query
        # f3_frequency.
        self.controller.start()
        self.controller.get_current_value('f3_frequency')

    def test_pending_changes(self):
        self.assertEqual(self.controller.pending_changes, False)
        self.paradigm.f2_frequency = ParameterExpression('6e3')
        self.assertEqual(self.controller.pending_changes, False)
        self.controller.start()
        self.paradigm.f2_frequency = ParameterExpression('9e3')
        self.assertEqual(self.controller.pending_changes, True)


if __name__ == '__main__':
    unittest.main()
