from experiment import AbstractParadigm, Expression
from experiment.paradigm.constant_limits import \
    GoNogoCLSettings, GoNogoCLControllerMixin

from traits.api import HasTraits
from traitsui.api import VGroup, View, Item, HGroup

class DTParadigm(HasTraits):

    fc = Expression(2e3, label='Center frequency (Hz)', context=False)
    level = Expression(20, label='Level (dB SPL)', help='Test')
    duration = Expression(0.512, label='Duration (s)')
    rise_fall_time = Expression(0.0025, label='Rise/fall time (s)')

    traits_view = View(
        VGroup(
            'duration',
            'rise_fall_time',
            'fc',
            'level',
            label='Tone',
            show_border=True,
        ),
    )


def main():
    from experiment import (AbstractController, AbstractExperiment,
                            AbstractParadigm)
    class C(GoNogoCLControllerMixin, AbstractController):
        def stop_experiment(self, info=None):
            pass
    class E(AbstractExperiment):
        traits_view = View(
            HGroup(
                Item('paradigm', style='custom'),
                Item('data', style='custom'),
                show_labels=False,
            ),
        )

    from experiment.selector.fixed_sequence import MultiTypeListSelector
    selector = MultiTypeListSelector('GO', 'GO_REMIND', 'NOGO')
    selector.add_parameter('x', 'Modulation Frequency (Hz)')
    settings = GoNogoCLSettings(selector=selector, target=DTParadigm())

    e = E(paradigm=settings)
    c = C()
    e.configure_traits(handler=c)


if __name__ == '__main__':
    main()
