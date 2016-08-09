from collections import OrderedDict

from traits.api import Button, List, Instance, Trait
from traitsui.api import (TabularEditor, View, Item, HGroup, VGroup, spring,
                          Include)
from traitsui.tabular_adapter import TabularAdapter

from ..evaluate import choice
from .abstract_selector import AbstractSelector


###############################################################################
# Supporting classes
###############################################################################
class DictTabularAdapter(TabularAdapter):

    def _get_content(self):
        return self.item[self.column_id]

    def _set_text(self, value):
        self.item[self.column_id] = value

    def _get_bg_color(self):
        if 'setting_type' in self.item:
            trial_type = self.item['setting_type']
            if trial_type == 'NOGO':
                return '#FFC8CB'
            elif trial_type == 'GO_REMIND':
                return '#D3D3D3'
            elif trial_type == 'GO':
                return '#98FB98'


###############################################################################
# Selectors
###############################################################################
class BaseListSelector(AbstractSelector):

    sequence = List(context=True)
    _hidden_keys = []
    _sort = Button('Sort')
    _remove = Button('-')

    def __init__(self):
        self._parameters = OrderedDict()
        self._selected_settings = None

    def add_parameter(self, parameter, label=None, default_value=None):
        if parameter in self._parameters:
            raise ValueError('Parameter already exists')
        if label is None:
            label = parameter
        self._parameters[parameter] = label
        for setting in self.sequence:
            setting[parameter] = default_value

    def remove_parameter(self, parameter):
        if parameter not in self._parameters:
            raise ValueError('Parameter not in list')
        self._parameters.remove(parameter)
        for setting in self.sequence:
            del(setting[parameter])

    def _new_setting(self):
        if self._selected_settings:
            return self._selected_settings[-1].copy()
        elif self.sequence:
            return self.sequence[-1].copy()
        else:
            return dict((p, 0) for p in self._parameters)

    def add_setting(self, setting=None):
        if setting is None:
            setting = self._new_setting()
        valid_keys = set(self._parameters.keys() + self._hidden_keys)
        if set(setting.keys()) != valid_keys:
            raise ValueError('Setting contains extra parameters')
        self.sequence.append(setting)

    def remove_setting(self, setting):
        self.sequence.remove(setting)

    def remove_selected_settings(self):
        for setting in self._selected_settings:
            self.remove_setting(setting)

    def __remove_fired(self):
        self.remove_selected_settings()

    def __sort_fired(self):
        self.sequence = sorted(self.sequence)

    def _buttons_view(self):
        raise NotImplementedError

    def _settings_view(self):
        raise NotImplementedError

    def traits_view(self):
        _column_map = list((v, k) for k, v in self._parameters.items())
        _editor = TabularEditor(
            adapter=DictTabularAdapter(columns=_column_map),
            auto_update=True,
            selected='_selected_settings',
            operations=['edit'],
            editable=True,
            editable_labels=True,
            multi_select=True,
        )
        return View(
            VGroup(
                self._settings_view(),
                self._buttons_view(),
                Item('sequence', editor=_editor, show_label=False),
            ),
            resizable=True,
        )


class ListSelector(BaseListSelector):

    _add = Button('+')
    sequence_order = Trait('shuffled_set', choice.options,
                           label='Sequence order')

    def __add_fired(self):
        self.add_setting()

    def _buttons_view(self):
        return HGroup('_add', '_remove', '_sort', show_labels=False)

    def _settings_view(self):
        return Item('sequence_order')

    def create_selector(self):
        return self.sequence_order_(self.sequence)


class MultiTypeListSelector(BaseListSelector):

    _hidden_keys = ['setting_type']

    def __init__(self, *setting_types):
        super(MultiTypeListSelector, self).__init__()
        self._buttons = []
        self._sequences = []
        self.setting_types = setting_types
        for t in setting_types:
            sequence_name = '{}_order'.format(t)
            button_name = '_add_{}'.format(t)
            callback_name = '__add_{}_fired'.format(t)
            self.add_trait(button_name, Button('+{}'.format(t)))
            sequence_trait = Trait('shuffled_set', choice.options,
                                   label='{} order'.format(t), context=True)
            self.add_trait(sequence_name, sequence_trait)
            self._buttons.append(button_name)
            self._sequences.append(sequence_name)
            # This double-lambda is required to maintain the value of t in
            # memory.  Typically lambdas maintain a reference to the variable
            # name not the value stored in the variable.  That means the value
            # is looked up at runtime.
            cb = (lambda t: lambda: self.add_setting(t))(t)
            self.on_trait_change(cb, button_name)
        self._buttons.extend(['_remove', '_sort'])

    def add_setting(self, trial_type, setting=None):
        if setting is None:
            setting = self._new_setting()
        setting['setting_type'] = trial_type
        super(MultiTypeListSelector, self).add_setting(setting)

    def _buttons_view(self):
        return HGroup(*self._buttons, show_labels=False)

    def _settings_view(self):
        return VGroup(*self._sequences)

    def get_sequence(self, setting_type):
        return [s for s in self.sequence if s['setting_type'] == setting_type]

    def create_selector(self, setting_type):
        order = getattr(self, '{}_order_'.format(setting_type))
        sequence = self.get_sequence(setting_type)
        return order(sequence)


def main():
    selector = MultiTypeListSelector('GO', 'GO_REMIND', 'NOGO')
    selector.add_parameter('x')
    selector.add_parameter('y', 'Shock level')
    selector.add_parameter('z', 'Zee (dB)')
    selector.configure_traits()

    go_selector = selector.create_selector('GO')
    nogo_selector = selector.create_selector('NOGO')
    print 'go', go_selector.next()
    print 'nogo', nogo_selector.next()
    print 'go', go_selector.next()
    print 'nogo', nogo_selector.next()

    selector = ListSelector()
    selector.add_parameter('x')
    selector.add_parameter('y', 'Shock level')
    selector.add_parameter('z', 'Zee (dB)')
    selector.configure_traits()

    selector = selector.create_selector()
    print selector.next()
    print selector.next()

if __name__ == '__main__':
    main()
