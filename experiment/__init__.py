from .abstract_experiment import AbstractExperiment
from .abstract_controller import (AbstractController,
                                  ApplyRevertControllerMixin, context_editor)
from .abstract_data import AbstractData
from .abstract_paradigm import AbstractParadigm
from .evaluate import ParameterExpression, Expression

from pkg_resources import resource_filename
icon_dir = [resource_filename('experiment', 'icons')]
