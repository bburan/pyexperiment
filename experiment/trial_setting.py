from traits.api import HasTraits, Enum, TraitError, Float, Int
from traitsui.api import View, VGroup


class TrialSetting(HasTraits):

    _parameters = ['ttype']
    _labels = ['Type']

    ttype = Enum('GO', 'NOGO', 'GO_REMIND', 'NOGO_REPEAT', label='Trial type',
                 store='attribute', context=True, log=True)

    def __init__(self, ttype, **kwargs):
        kwargs['ttype'] = ttype
        super(TrialSetting, self).__init__(**kwargs)

    #def traits_view(self):
    #    # How should the object appear under various contexts (GUI, command
    #    # line, etc)
    #    return View(VGroup(*self._parameters))

    # Implement special classmethods to facilitate GUI representation, sorting
    # and comparison as needed.
    def __str__(self):
        lv = zip(self._labels, self.values())
        return ', '.join('{}: {}'.format(l, v) for l, v in lv)

    def __repr__(self):
        string = ', '.join('{}={}'.format(k, v) for k, v in self.items())
        return '<TrialSetting::{}>'.format(string)

    def __lt__(self, other):
        if not isinstance(other, TrialSetting):
            return NotImplemented
        return self.values() < other.values()

    def __ge__(self, other):
        if not isinstance(other, TrialSetting):
            return NotImplemented
        return self.values() > other.values()

    def __eq__(self, other):
        if not isinstance(other, TrialSetting):
            return NotImplemented
        return self.values() == other.values()

    def __ne__(self, other):
        if not isinstance(other, TrialSetting):
            return NotImplemented
        return self.values() != other.values()

    def values(self):
        return [getattr(self, p) for p in self._parameters]

    def keys(self):
        return self._parameters

    def items(self):
        return zip(self.keys(), self.values())

    def iteritems(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key not in self._parameters:
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key, value):
        if key not in self._parameters:
            raise KeyError(key)
        super(TrialSetting, self).__setitem__(key, value)

    def __len__(self):
        return len(self._parameters)

    def __iter__(self):
        return iter(self._parameters)

from traitsui.api import TabularEditor
from traitsui.tabular_adapter import TabularAdapter

#from cns import get_config
#color_names = get_config('COLOR_NAMES')
#
#class TrialSettingAdapter(TabularAdapter):
#
#    default_value = TrialSetting(ttype='GO')
#
#    def _get_bg_color(self):
#        ttype = self.item.ttype
#        if ttype == 'NOGO':
#            return color_names['light red']
#        elif ttype == 'GO_REMIND':
#            return color_names['dark green']
#        elif ttype == 'GO':
#            return color_names['light green']
#
#trial_setting_editor = TabularEditor(
#    auto_update=True,
#    selected='_selected_setting',
#    operations=['edit'],
#    editable=True,
#    multi_select=True,
#    adapter=TrialSettingAdapter(width=150)
#)

def add_parameters(parameters, paradigm_class=None, repeats=True):
    '''
    Modifies the TrialSetting class on-the fly to control the parameters we want
    '''

    # Since add_parameters may be called several times during the lifetime of
    # the program, we need to make sure we're not duplicating an existing
    # parameter.
    parameters = [p for p in parameters if p not in TrialSetting.class_traits()]

    columns = []
    labels = []
    for parameter in parameters:
        # Get the human-readable label from the class definition if it is
        # available, otherwise set the label to the computer-representation of
        # the parameter name.
        if paradigm_class is not None:
            label = paradigm_class.class_traits()[parameter].label
        else:
            label = parameter

        trait = Float(label=label, context=True, store='attribute', log=False)
        try:
            TrialSetting.add_class_trait(parameter, trait)
            column = ((label, parameter))
            columns.append(column)
            labels.append(label)
        except TraitError:
            # The trait has already been defined, so we should just skip it
            pass

    if repeats:
        # Repeats is a special variable that tells us how many times a single
        # TrialSetting object should be presented during a sequence
        trait = Int(1, label='Repeats', store='attribute', context=True, log=False)
        try:
            TrialSetting.add_class_trait('repeats', trait)
            column = (('Repeats', 'repeats'))
            columns.append(column)
        except TraitError:
            # The trait has already been defined, so we should just skip it
            pass

    #columns.append(('Type', 'ttype'))
    #trial_setting_editor.adapter.columns.extend(columns)
    TrialSetting._parameters.extend(parameters)
    TrialSetting._labels.extend(labels)

import unittest

class TestTrialSetting(unittest.TestCase):

    def setUp(self):
        add_parameters(['x', 'y'])

    def testEquality(self):
        self.assertEqual(TrialSetting('NOGO'), TrialSetting('NOGO'))
        self.assertEqual(TrialSetting('NOGO', x=1), TrialSetting('NOGO', x=1))
        self.assertNotEqual(TrialSetting('NOGO'), TrialSetting('GO'))
        self.assertNotEqual(TrialSetting('NOGO', x=1), TrialSetting('GO', x=1))

    def testIdentity(self):
        self.assertFalse(TrialSetting('NOGO') is TrialSetting('NOGO'))

    def testList(self):
        settings = [TrialSetting('NOGO'), TrialSetting('GO', x=1),
                    TrialSetting('GO', x=1), TrialSetting('GO', x=2)]
        settings.remove(TrialSetting('GO', x=1))
        self.assertEqual(len(settings), 3)

if __name__ == '__main__':
    #add_parameters(['x', 'y'])
    #s = TrialSetting()
    unittest.main()
