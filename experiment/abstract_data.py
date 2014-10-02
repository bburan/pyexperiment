import logging
log = logging.getLogger(__name__)

import numpy as np
from traits.api import Any, Event, HasTraits, Property, cached_property


class AbstractData(HasTraits):

    fh = Property(depends_on='store_node')
    store_node = Any
    event_log = Any
    trial_log = Any
    event_log_updated = Event
    trial_log_updated = Event
    trial_log_dtype = Any

    @cached_property
    def _get_fh(self):
        return self.store_node._v_file

    def register_dtypes(self, dtypes):
        fh = self.store_node._v_file
        description = np.dtype(dtypes)
        self.trial_log_description = description
        self.trial_log = fh.createTable(self.store_node, 'trial_log',
                                        description)

    def _event_log_default(self):
        fh = self.store_node._v_file
        dtype = [('timestamp', 'f'), ('name', 'S64')]
        description = np.dtype(dtype)
        node = fh.createTable(self.store_node, 'event_log', description)
        return node

    def log_event(self, timestamp, event):
        # The append() method of a tables.Table class requires a list of rows
        # (i.e. records) to append to the table.  Since we only append a single
        # row at a time, we need to nest it as a list that contains a single
        # record.
        self.event_log.append([(timestamp, event)])
        self.event_log_updated = (timestamp, event)

    def log_trial(self, **kwargs):
        # Create the record with appropriate names for the columns then convert
        # to the order needed for the trial log
        record = np.rec.fromrecords([kwargs.values()], names=kwargs.keys())
        record = record.astype(self.trial_log_description)
        self.trial_log.append(record)
        self.trial_log_updated = record

    def save(self, **kwargs):
        for name, value in kwargs.items():
            self.store_node._f_setAttr(name, value)
