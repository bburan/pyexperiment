from traits.api import HasTraits, Bool, Instance, List, Trait, Any
from traitsui.api import VGroup, Item, View, Include

from experiment import Expression, AbstractParadigm

SETTING_TYPES = ('GO', 'GO_REMIND', 'NOGO')

class GoNogoCLSettings(AbstractParadigm):

    go_probability = Expression('0.5 if c_nogo < 5 else 1',
                                label='Go probability')
    repeat_fa = Bool(True, label='Repeat nogo if FA?', context=True)
    selector = Instance('experiment.selector.AbstractSelector', container=True)
    target = Instance(HasTraits, container=True)

    paradigm_view_mixin = VGroup(
        Item('target', style='custom', show_label=False),
        VGroup(
            VGroup(
                Item('go_probability'),
                Item('repeat_fa'),
            ),
            Item('selector', style='custom', show_label=False),
            label='Sequence settings',
            show_border=True,
        ),
    )

    traits_view = View(Include('paradigm_view_mixin'))


class GoNogoCLControllerMixin(object):

    remind_requested = Bool(False)
    selectors = List()

    def _create_selectors(self):
        # The selectors are generator functions which yield values from a list
        # of elements. In this case, we initialize the selector (the generator)
        # with a list of the setting dictionaries. If we wish for a certain
        # parameter to be presented multiple times in a single set, we need to
        # repeat this parameter in the list (e.g. if repeats is >= 1).
        for setting_type in SETTING_TYPES:
            selector = self.paradigm.selector.create_selector(setting_type)
            setattr(self, 'current_sequence_{}'.format(setting_type), selector)

    def next_setting(self):
        # Must be able to handle both the initial (first trial) and repeat nogo
        # cases as needed.  Check for special cases first.
        if self.remind_requested:
            self.remind_requested = False
            return self.current_sequence_GO_REMIND.next()
        if len(self.model.data.trial_log) == 0:
            return self.current_sequence_GO_REMIND.next()

        # Now, check to see if we need to update the selector
        if self.current_sequence is None or \
                self.value_changed('go_setting_order') or \
                self.value_changed('go_settings'):
            self._create_selectors()

        # This is a regular case.  Select the appropriate setting.
        spout = self.model.data.yes_seq[-1]
        nogo = self.model.data.nogo_seq[-1]
        if nogo and spout and self.get_current_value('repeat_fa'):
            return self.nogo_repeat_setting()
        if np.random.uniform() <= self.get_current_value('go_probability'):
            return self.current_sequence_GO.next()
        else:
            return self.current_sequence_NOGO.next()
