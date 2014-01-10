from traits.api import HasTraits, Instance


class AbstractExperiment(HasTraits):

    paradigm = Instance('experiment.AbstractExperimentParadigm', ())
    data = Instance('experiment.AbstractExperimentData', ())
