from traits.api import HasTraits, Instance
from traitsui.api import VGroup, Item, TabularEditor
from traitsui.tabular_adapter import TabularAdapter


class ContextAdapter(TabularAdapter):

    columns = ['Parameter', 'Value', 'Variable']

    def get_image(self, obj, trait, row, column):
        if column == 0 and self.item[-2]:
            return '@icons:tuple_node'

    def get_width(self, obj, trait, column):
        return 100

    def get_bg_color(self, obj, trait, row, column=0):
        return '#98FB98' if self.item[-1] else '#FFFFFF'


context_editor = TabularEditor(adapter=ContextAdapter(), editable=False)


class AbstractExperiment(HasTraits):

    paradigm = Instance('experiment.AbstractParadigm', ())
    data = Instance('experiment.AbstractData', ())

    context_group = VGroup(
        Item('handler.current_context_list', editor=context_editor),
        show_labels=False,
        label='Current Context',
    )
