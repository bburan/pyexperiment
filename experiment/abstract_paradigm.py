from traits.api import HasTraits

import json


class AbstractParadigm(HasTraits):

    PARAMETER_FILTER = {
            'editable': lambda x: x is not False,
            'type':     lambda x: x not in ('event', 'python'),
            'ignore':   lambda x: x is not True,
    }

    @classmethod
    def get_parameters(cls):
        return sorted(cls.class_trait_names(**cls.PARAMETER_FILTER))

    @classmethod
    def get_parameter_info(cls):
        '''
        Dictionary of available parameters and their corresponding
        human-readable label
        '''
        traits = cls.class_traits(**cls.PARAMETER_FILTER)
        return dict((name, trait.label) for name, trait in traits.items())

    @classmethod
    def get_parameter_label(cls, parameter):
        return cls.get_parameter_info()[parameter]

    @classmethod
    def get_invalid_parameters(cls, parameters):
        return [p for p in parameters if p not in cls.get_parameters()]

    @classmethod
    def pp_parameters(cls):
        '''
        Utility classmethod for pretty-printing the list of parameters to the
        command line.
        '''
        par_info = cls.get_parameter_info()
        parameters = sorted(list(par_info.items()))

        # Add the column headings
        parameters.insert(0, ('Variable Name', 'Label'))
        parameters.insert(1, ('-------------', '-----'))

        # Determine the padding we need for the columns
        col_paddings = []
        for i in range(len(parameters[0])):
            sizes = [len(row[i]) if row[i] != None else 0 for row in parameters]
            col_paddings.append(max(sizes))

        # Pretty print the list
        print '\n'
        for i, row in enumerate(parameters):
            print row[0].rjust(col_paddings[0]+2) + ' ',
            if row[1] is not None:
                print row[1].ljust(col_paddings[1]+2)
            else:
                print ''

    @classmethod
    def get_dtypes(cls):
        traits = cls.class_traits(log=True)
        return [(k, v.dtype) for k, v in traits.items()]

    def items(self, **kw):
        for k in self.get_parameters(**kw):
            v = getattr(self, k)
            yield k, v

    def write_json(self, filename):
        with open(filename, 'w') as fh:
            ignore_types = ('property', 'event', 'python')
            values = self.trait_get(type=lambda x: x not in ignore_types)
            json.dump(values, fh, sort_keys=True, indent=4)

    def read_json(self, filename):
        with open(filename, 'r') as fh:
            for k, v in json.load(fh).items():
                try:
                    setattr(self, k, v)
                except AttributeError:
                    print k
