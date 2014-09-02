from traits.api import HasTraits, Instance


class AbstractExperiment(HasTraits):

    paradigm = Instance('experiment.AbstractParadigm', ())
    data = Instance('experiment.AbstractData', ())
