from .abstract_selector import AbstractSelector
from .fixed_sequence import ListSelector, MultiTypeListSelector

def get_selectors(setting_types=None):
    '''
    Return a dictionary of available selectors
    '''
    if setting_types is None:
        return {
            'list': ListSelector(),
        }
    else:
        return {
            'list': MultiTypeListSelector(*setting_types),
        }
