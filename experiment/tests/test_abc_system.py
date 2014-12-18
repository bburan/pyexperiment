import unittest

import tables

from experiment import (AbstractData, AbstractParadigm, AbstractController,
                        AbstractExperiment)
from experiment.evaluate import Expression, ParameterExpression


class TestParadigm(AbstractParadigm):

    kw = dict(context=True, log=True)
    f1_frequency = Expression('f2_frequency/1.2', **kw)
    f2_frequency = Expression(8e3, **kw)
    level = Expression('exact_order(np.arange(0, 10, 5), cycles=1)', **kw)


class TestController(AbstractController):

    def next_trial(self):
        self.refresh_context()


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
        expected = {'f2_frequency': 8e3, 'f1_frequency': 8e3/1.2, 'level': 5}
        self.assertEqual(self.controller.current_context, expected)

        # Test generator exhaustion
        self.controller.next_trial()
        self.assertRaises(StopIteration,
                          self.controller.evaluate_pending_expressions)

    def test_chained_next_value(self):
        exp = ParameterExpression('u(exact_order([2e3, 9e3], cycles=1), level)')
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

    def test_pending_changes(self):
        self.assertEqual(self.controller.pending_changes, False)
        self.paradigm.f2_frequency = ParameterExpression('6e3')
        self.assertEqual(self.controller.pending_changes, False)
        self.controller.start()
        self.paradigm.f2_frequency = ParameterExpression('9e3')
        self.assertEqual(self.controller.pending_changes, True)


if __name__ == '__main__':
    unittest.main()
