'''
Containers for timeseries data
==============================

The majority of these containers are backed by a HDF5 datastore (e.g. an EArray)
for acquiring and caching data.  If you just want a temporary dataset, create a
temporary array.  However, if you wish to have an in-memory datastore, you can
define a MemoryMixin class (see :class:`FileMixin`) that implements a
__getitem__ method.
'''
from __future__ import division

from traits.api import HasTraits, Property, Array, Int, Event, \
    Instance, on_trait_change, Bool, Any, String, Float, cached_property, \
    Enum, Set
import numpy as np
import tables
from scipy import signal
from .arraytools import slice_overlap

import logging
log = logging.getLogger(__name__)


################################################################################
# Backend storage classes implemented as mixins (e.g., file, RAM, etc.)
################################################################################
class FileMixin(HasTraits):
    '''
    Mixin class that uses a HDF5_ EArray as the backend for the buffer.  If the
    array does not exist, it will be created automatically.  Note that this does
    have some performance implications since data may have to be transferred
    between the hard disk and RAM.

    By default, this will create the node.  If the node already exists, use the
    `from_node` classmethod to return an instance of the class.

    IMPORTANT! When using this mixin with most subclasses of Channel, the
    FileMixin typically must appear first in the list otherwise you may have
    some method resolution order issues.

    .. _HDF5: http://www.hdfgroup.org/HDF5/

    Properties
    ----------
    dtype
        Default is float64.  It is a good idea to set dtype appropriately for
        the waveform (e.g. use a boolean dtype for TTL data) to minimize file
        size.  Note that Matlab does not currently support the HDF5 BITFIELD
        (e.g. boolean) type and will be unable to read waveforms stored in this
        format.
    node
        A HDF5 node that will host the array
    name
        Name of the array
    expected_duration
        Rough estimate of how long the waveform will be.  This is used (in
        conjunction with fs) to optimize the "chunksize" when creating the
        array.

    Compression properties
    ----------------------
    compression_level
        Between 0 and 9, with 0=uncompressed and 9=maximum
    compression_type
        zlib, lzo or bzip
    use_checksum
        Ensures data integrity, but at cost of degraded read/write performance

    Default settings for the compression filter are no compression which
    provides the best read/write performance.

    Note that if compression_level is > 0 and compression_type is None,
    tables.Filter will raise an exception.
    '''

    # According to http://www.pytables.org/docs/manual-1.4/ch05.html the best
    # compression method is LZO with a compression level of 1 and shuffling, but
    # it really depends on the type of data we are collecting.
    compression_level = Int(0, transient=True)
    compression_type = Enum(None, 'lzo', 'zlib', 'bzip', 'blosc',
                            transient=True)
    use_checksum = Bool(False, transient=True)
    use_shuffle = Bool(False, transient=True)

    # It is important to implement dtype appropriately, otherwise it defaults to
    # float64 (double-precision float).
    dtype = Any(transient=True)

    # Duration is in seconds.  The default corresponds to a 30 minute
    # experiment, which we seem to have settled on as the "standard" for running
    # appetitive experiments.
    expected_duration = Float(1800, transient=True)

    # The actual source where the data is stored.  Node is the HDF5 Group that
    # the EArray is stored under while name is the name of the EArray.
    node = Instance(tables.group.Group, transient=True)
    name = String(transient=True)
    overwrite = Bool(False, transient=True)
    _buffer = Instance(tables.array.Array, transient=True)

    shape = Property(depends_on='added, changed', cached=True)

    def _get_shape(self):
        return self._buffer.shape

    def _create_buffer(self, name, dtype, shape, expectedrows):
        log.debug('%s: creating buffer with shape %r', self, self._get_initial_shape())
        atom = tables.Atom.from_dtype(np.dtype(dtype))
        log.debug('%s: creating buffer with type %r', self, dtype)
        filters = tables.Filters(complevel=self.compression_level,
                                 complib=self.compression_type,
                                 fletcher32=self.use_checksum,
                                 shuffle=self.use_shuffle)
        if name in self.node and self.overwrite:
            self.node._f_get_child(name)._f_remove()
        return self.node._v_file.createEArray(self.node._v_pathname, name, atom,
                                              shape, filters=filters,
                                              expectedrows=expectedrows)

    @classmethod
    def from_node(cls, node, **kwargs):
        '''
        Create an instance of the class from an existing node
        '''
        # If the attribute (e.g. fs or t0) are not provided, load the value of
        # the attribute from the node attributes
        for name in cls.class_trait_names(attr=True):
            if name not in kwargs:
                try:
                    kwargs[name] = node._v_attrs[name]
                except KeyError:
                    # This checks for an older verison of the physiology channel
                    # data format that did not save t0 as an attribute to the
                    # node.
                    if name == 't0':
                        kwargs['t0'] = 0
                    else:
                        raise

        kwargs['node'] = node._v_parent
        kwargs['name'] = node._v_name
        kwargs['_buffer'] = node
        kwargs['dtype'] = node.dtype
        return cls(**kwargs)

    def _get_initial_shape(self):
        return (0,)

    def __buffer_default(self):
        earray = self._create_buffer(self.name, self.dtype, self._get_initial_shape(),
                                     int(self.fs*self.expected_duration))
        for k, v in self.trait_get(attr=True).items():
            earray._v_attrs[k] = v
        return earray

    # Ensure that all 'Traits' are synced with the file so we have that
    # information stored away.
    @on_trait_change('+attr', post_init=True)
    def update_attrs(self, name, new):
        log.debug('%s: updating %s to %r', self, name, new)
        self._buffer.setAttr(name, new)

    def _write(self, data):
        self._buffer.append(data)

    def __repr__(self):
        return '<HDF5Store {}>'.format(self.name)

    def append(self, data):
        self._buffer.append(data)

    def clear(self):
        self._buffer.truncate(0)


class NDArrayMixin(HasTraits):
    '''
    Mixin class that uses numpy arrays as the backend for the buffer.
    '''

    def __buffer_default(self):
        initial_shape = list(self._get_initial_shape())
        edim = shape.index(-1)
        initial_shape[edim] = expected_rows
        _buffer = np.empty(initial_shape, dtype=dtype)


################################################################################
# Backend storage classes (e.g., file, RAM, etc.)
################################################################################
class Timeseries(HasTraits):

    updated = Event
    added = Event
    fs = Float(attr=True)
    t0 = Float(0, attr=True)

    def send(self, timestamps):
        if len(timestamps):
            self.append(timestamps)
            self.added = np.array(timestamps)/self.fs

    def get_range(self, lb, ub):
        ts = self._buffer.read()
        ilb = int(lb*self.fs)
        iub = int(ub*self.fs)
        mask = (ts >= ilb) & (ts < iub)
        return ts[mask]/self.fs

    def latest(self):
        if len(self._buffer) > 0:
            return self._buffer[-1]/self.fs
        else:
            np.nan

    def __getitem__(self, slice):
        return self._buffer[slice]/self.fs

    def __len__(self):
        return len(self._buffer)


class FileTimeseries(FileMixin, Timeseries):
    '''
    Timeseries class using a HDF5 node as the datastore
    '''

    name = 'FileTimeseries'
    dtype = Any(np.int32)


class Epoch(HasTraits):

    added = Event
    fs = Float(attr=True)
    t0 = Float(0, attr=True)

    def get_range(self, lb, ub):
        timestamps = self._buffer[:]
        starts = timestamps[:, 0]
        ends = timestamps[:, 1]
        ilb = int(lb*self.fs)
        iub = int(ub*self.fs)
        start_mask = (starts >= ilb) & (starts < iub)
        end_mask = (ends >= ilb) & (ends < iub)
        mask = start_mask | end_mask
        if mask.any():
            return timestamps[mask, :]/self.fs
        else:
            return np.array([]).reshape((0, 2))

    def send(self, timestamps):
        if len(timestamps):
            self.append(timestamps)
            self.added = np.array(timestamps)/self.fs

    def __getitem__(self, key):
        return self._buffer[key]/self.fs


class FileEpoch(FileMixin, Epoch):
    '''
    Epoch class using a HDF5 node as the datastore
    '''

    name = 'FileEpoch'
    dtype = Any(np.int32)

    def _get_initial_shape(self):
        return (0, 2)


class Channel(HasTraits):
    '''
    Base class for dealing with a continuous stream of data sampled at a fixed
    rate, fs (cycles per time unit), starting at time t0 (time unit).  This
    class is not meant to be used directly since it does not implement a backend
    for storing the data.  Subclasses are responsible for implementing the data
    buffer (e.g. either a file-based or memory-based buffer).

    fs
        Sampling frequency
    t0
        Time offset (i.e. time of first sample) relative to the start of
        acquisition.  This typically defaults to zero; however, some subclasses
        may discard old data (e.g.  :class:`RAMChannel`), so we need to factor
        in the time offset when attempting to extract a given segment of the
        waveform for analysis.

    Two events are supported.

    added
        New data has been added. If listeners have been caching the results of
        prior computations, they can assume that older data in the cache is
        valid.
    changed
        The underlying dataset has changed, but the time-range has not.

    The changed event roughly corresponds to changes in the Y-axis (i.e. the
    signal) while added roughly corresponds to changes in the X-axis (i.e.
    addition of additional samples).
    '''

    # Sampling frequency of the data stored in the buffer
    fs = Float(attr=True, transient=True)

    # Time of first sample in the buffer.  Typically this is 0, but if we delay
    # acquisition or discard "old" data (e.g. via a RAMBuffer), then we need to
    # update t0.
    t0 = Float(0, attr=True, transient=True)

    added = Event
    changed = Event

    samples = Property(depends_on='shape', cached=True)
    duration = Property(depends_on='samples, fs', cached=True)
    latest = Property(depends_on='duration, t0', cached=True)
    time = Property(depends_on='samples, fs, t0', cached=True)
    signal = Property(depends_on='_buffer', cached=True)

    def __getitem__(self, slice):
        '''
        Delegates to the __getitem__ method on the underlying buffer

        Subclasses can add additional data preprocessing by overriding this
        method.  See `ProcessedFileMultiChannel` for an example.
        '''
        return self._buffer[slice]

    def _get_initial_shape(self):
        if not self.traits_inited():
            return
        return self._buffer.shape

    def _get_samples(self):
        if not self.traits_inited():
            return
        return self.shape[-1]

    def _get_duration(self):
        if not self.traits_inited():
            return
        return self.samples/self.fs

    def _get_latest(self):
        if not self.traits_inited():
            return
        return self.duration+self.t0

    def _get_time(self):
        if not self.traits_inited():
            return
        return np.arange(self.samples)/self.fs + self.t0

    def _get_signal(self):
        if not self.traits_inited():
            return
        return self._buffer[:]

    def _to_bounds(self, start, end, reference=None):
        if start > end:
            raise ValueError("Start time must be < end time")
        if reference is not None:
            ref_idx = self.to_index(reference)
        else:
            ref_idx = 0
        lb = max(0, self.to_index(start)+ref_idx)
        ub = max(0, self.to_index(end)+ref_idx)
        return lb, ub

    def to_index(self, time):
        '''
        Convert time to the corresponding index in the waveform.  Note that the
        index may be negative if the time is less than t0.  Since Numpy allows
        negative indices, be sure to check the value.
        '''
        return int((time-self.t0)*self.fs)

    def to_samples(self, time):
        '''
        Convert time to number of samples.
        '''
        time = np.asanyarray(time)
        samples = time*self.fs
        return samples.astype('i')

    def get_index(self, index, reference=0):
        t0_index = int(self.t0*self.fs)
        index = max(0, index-t0_index+reference)
        return self[..., index]

    def get_range(self, start, end, reference=None):
        '''
        Returns a subset of the range.

        Parameters
        ----------
        start : float, sec
            Start time.
        end : float, sec
            End time.
        reference : float, optional
            Set to -1 to get the most recent range
        '''
        if start is None:
            start = self.t0
        if end is None:
            end = self.t0+self.duration

        lb, ub = self._to_bounds(start, end, reference)
        log.debug('%s: %d:%d requested', self, lb, ub)
        return self[..., lb:ub]

    def get_range_index(self, start, end, reference=0, check_bounds=False):
        '''
        Returns a subset of the range specified in samples

        The samples must be speficied relative to start of data acquisition.

        Parameters
        ----------
        start : num samples (int)
            Start index in samples
        end : num samples (int)
            End index in samples
        reference : num samples (int), optional
            Time of trigger to reference start and end to
        check_bounds : bool
            Check that start and end fall within the valid data range
        '''
        t0_index = int(self.t0*self.fs)
        lb = start-t0_index+reference
        ub = end-t0_index+reference

        if check_bounds:
            if lb < 0:
                raise ValueError("start must be >= 0")
            if ub >= len(self._buffer):
                raise ValueError("end must be <= signal length")

        if np.iterable(lb):
            return [self[..., l:u] for l, u in zip(lb, ub)]
        else:
            return self[..., lb:ub]

    def get_bounds(self):
        '''
        Returns valid range of times as a tuple (lb, ub)
        '''
        return self.t0, self.latest

    def send(self, data):
        '''
        Convenience method that allows us to use a Channel as a "sink" for a
        processing pipeline.
        '''
        if len(data):
            self.write(data.ravel())

    def write(self, data):
        '''
        Write data to buffer.
        '''
        lb = self.latest
        self._write(data)
        ub = self.latest

        # Some plots monitoring this event will use this to determine whether
        # the updated region of the data is within the visible region.  If not,
        # no update is made.
        self.added = lb, ub

    def summarize(self, timestamps, offset, duration, fun):
        if len(timestamps) == 0:
            return np.array([])

        # Channel.to_samples(time) converts time (in seconds) to the
        # corresponding number of samples given the sampling frequency of the
        # channel.  If the trial begins at sample n, then we want to analyze
        # contact during the interval [n+lb_index, n+ub_index).
        lb_index = self.to_samples(offset)
        ub_index = self.to_samples(offset+duration)
        timestamps = self.to_samples(timestamps)

        # Variable ts is the sample number at which the trial began and is a
        # multiple of the contact sampling frequency.
        # Channel.get_range_index(lb_sample, ub_sample, reference_sample) will
        # return the specified range relative to the reference sample.  Since we
        # are interested in extracting the range [contact_offset,
        # contact_offset+contact_dur) relative to the timestamp, we need to
        # first convert the range to the number of samples (which we did above
        # where we have it as [lb_index, ub_index)).  Since our reference index
        # (the timestamp) is already in the correct units, we don't need to
        # convert it.
        if np.iterable(timestamps):
            range = self.get_range_index(lb_index, ub_index, timestamps)
            return np.array([fun(r) for r in range])
        else:
            range = self.get_range_index(lb_index, ub_index, timestamps)
            return fun(range)

    def get_fftfreq(self):
        return np.fft.rfftfreq(self.samples, 1/self.fs)

    def _get_psd(self, s, rms=False):
        csd = np.fft.rfft(s)
        psd = 2*np.abs(csd)/self.samples
        return psd/np.sqrt(2) if rms else psd

    def get_psd(self, rms=False, window=None):
        s = signal.detrend(self[:], type='linear', axis=-1)
        if window is not None:
            w = signal.get_window(window, self.samples)
            s = w/w.mean()*s
        return self._get_psd(s, rms)

    def get_rms(self, detrend=True):
        if detrend:
            s = signal.detrend(self[:], type='linear', axis=-1)
        else:
            s = self[:]
        return np.mean(s**2, axis=-1)**0.5

    def get_magnitude(self, frequency, rms=False, window=None):
        if window is not None:
            w = signal.get_window(window, self.samples)
            s = w/w.mean()*self.signal
        else:
            s = self.signal
        r = 2.0*s*np.exp(-1.0j*(2.0*np.pi*self.time*frequency))
        magnitude = np.abs(np.mean(r))
        return magnitude/np.sqrt(2.0) if rms else magnitude


class FileChannel(FileMixin, Channel):
    '''
    Uses a HDF5 datastore for the buffer
    '''

    dtype = Any(np.float32)


class MultiChannel(Channel):

    # Default to 0 to make it clear that the class has not been properly
    # initialized
    channels = Int(0, attr=True)

    def get_channel_range(self, channel, lb, ub):
        return self.get_range(lb, ub)[channel]

    def send(self, data):
        if len(data):
            self.write(data)

    def get_range(self, start, end, reference=None, channels=None):
        lb, ub = self._to_bounds(start, end, reference)
        if channels is None:
            channels = Ellipsis
        return self[..., lb:ub][channels]

    def get_range_index(self, start, end, reference=0, check_bounds=False,
                        channels=None):
        '''
        Returns a subset of the range specified in samples

        The samples must be speficied relative to start of data acquisition.

        Parameters
        ----------
        start : num samples (int)
            Start index in samples
        end : num samples (int)
            End index in samples
        reference : num samples (int), optional
            Time of trigger to reference start and end to
        check_bounds : bool
            Check that start and end fall within the valid data range
        '''
        t0_index = int(self.t0*self.fs)
        lb = start-t0_index+reference
        ub = end-t0_index+reference

        if check_bounds:
            if lb < 0:
                raise ValueError("start must be >= 0")
            if ub >= len(self._buffer):
                raise ValueError("end must be <= signal length")

        if channels is None:
            channels = Ellipsis

        if np.iterable(lb):
            return [self[channels, l:u] for l, u in zip(lb, ub)]
        else:
            return self[channels, lb:ub]

    def summarize(self, timestamps, offset, duration, fun, channels=None):
        if len(timestamps) == 0:
            return np.array([])

        # Channel.to_samples(time) converts time (in seconds) to the
        # corresponding number of samples given the sampling frequency of the
        # channel.  If the trial begins at sample n, then we want to analyze
        # contact during the interval [n+lb_index, n+ub_index).
        lb_index = self.to_samples(offset)
        ub_index = self.to_samples(offset+duration)
        timestamps = self.to_samples(timestamps)

        # Variable ts is the sample number at which the trial began and is a
        # multiple of the contact sampling frequency.
        # Channel.get_range_index(lb_sample, ub_sample, reference_sample) will
        # return the specified range relative to the reference sample.  Since we
        # are interested in extracting the range [contact_offset,
        # contact_offset+contact_dur) relative to the timestamp, we need to
        # first convert the range to the number of samples (which we did above
        # where we have it as [lb_index, ub_index)).  Since our reference index
        # (the timestamp) is already in the correct units, we don't need to
        # convert it.
        if np.iterable(timestamps):
            range = self.get_range_index(lb_index, ub_index, timestamps,
                                         channels=channels)
            return np.array([fun(r) for r in range])
        else:
            range = self.get_range_index(lb_index, ub_index, timestamps,
                                         channels=channels)
            return fun(range)


class ProcessedMultiChannel(MultiChannel):
    '''
    References and filters the data when requested
    '''

    # Channels in the list should use zero-based indexing (e.g. the first
    # channel is 0).
    bad_channels = Array(dtype='int')
    diff_mode = Enum('all good', None)
    diff_matrix = Property(depends_on='bad_channels, diff_mode, channels')

    filter_freq_lp = Float(6e3, filter=True)
    filter_freq_hp = Float(300, filter=True)
    filter_btype = Enum('highpass', 'bandpass', 'lowpass', None, filter=True)
    filter_order = Float(8.0, filter=True)
    filter_type = Enum('butter', 'ellip', 'cheby1', 'cheby2', 'bessel',
                       filter=True)

    filter_instable = Property(depends_on='filter_coefficients')
    filter_coefficients = Property(depends_on='+filter, fs')

    _padding = Property(depends_on='filter_order')

    @cached_property
    def _get_filter_instable(self):
        b, a = self.filter_coefficients
        return not np.all(np.abs(np.roots(a)) < 1)

    @on_trait_change('filter_coefficients, diff_matrix', post_init=True)
    def _fire_change(self):
        # Objects that use this channel as a datasource need to know when the
        # data changes.  Since changes to the filter coefficients, differential
        # matrix or filter function affect the entire dataset, we fire the
        # changed event.  This will tell, for example, the
        # ExtremesMultiChannelPlot to clear it's cache and redraw the entire
        # waveform.
        self.changed = True

    @cached_property
    def _get_diff_matrix(self):
        if self.diff_mode is None:
            return np.identity(self.channels)
        else:
            matrix = np.identity(self.channels)

            # If all but one channel is bad, this will raise a
            # ZeroDivisionError.  I'm going to let this error "bubble up" since
            # the user should realize that they are no longer referencing their
            # data in that situation.
            weight = 1.0/(self.channels-1-len(self.bad_channels))

            for r in range(self.channels):
                if r in self.bad_channels:
                    matrix[r, r] = 0
                else:
                    for i in range(self.channels):
                        if (i not in self.bad_channels) and (i != r):
                            matrix[r, i] = -weight
            return matrix

    @cached_property
    def _get_filter_coefficients(self):
        if self.filter_btype is None:
            return [], []
        if self.filter_btype == 'bandpass':
            Wp = np.array([self.filter_freq_hp, self.filter_freq_lp])
        elif self.filter_btype == 'highpass':
            Wp = self.filter_freq_hp
        else:
            Wp = self.filter_freq_lp
        Wp = Wp/(0.5*self.fs)

        return signal.iirfilter(self.filter_order, Wp, 60, 2,
                                ftype=self.filter_type,
                                btype=self.filter_btype,
                                output='ba')

    @cached_property
    def _get__padding(self):
        return 3*self.filter_order

    def __getitem__(self, slice):
        # We need to stabilize the edges of the chunk with extra data from
        # adjacent chunks.  Expand the time slice to obtain this extra data.
        padding = self._padding
        data = slice_overlap(self._buffer, slice[-1], padding, padding)

        # It does not matter whether we compute the differential first or apply
        # the filter.  Since the differential requires data from all channels
        # while filtering does not, we compute the differential first then throw
        # away the channels we do not need.
        data = self.diff_matrix.dot(data)

        # For the filtering, we do not need all the channels, so we can throw
        # out the extra channels by slicing along the second axis
        data = data[slice[:-1]]
        if self.filter_btype is not None:
            b, a = self.filter_coefficients
            # Since we have already padded the data at both ends padlen can be
            # set to 0.  The "unstable" edges of the filtered waveform will be
            # chopped off before returning the result.
            data = signal.filtfilt(b, a, data, padlen=0)
        return data[..., padding:-padding]


class ProcessedFileMultiChannel(FileMixin, ProcessedMultiChannel):
    pass


class FileMultiChannel(FileMixin, MultiChannel):

    name = 'FileMultiChannel'

    def _get_initial_shape(self):
        return (self.channels, 0)


class FilterMixin(HasTraits):

    filter_freq_lp = Float(6e3, filter=True, attr=True)
    filter_freq_hp = Float(300, filter=True, attr=True)
    filter_btype = Enum('highpass', 'bandpass', 'lowpass', None, filter=True,
                        attr=True)
    filter_order = Float(8.0, filter=True, attr=True)
    filter_type = Enum('butter', 'ellip', 'cheby1', 'cheby2', 'bessel',
                       filter=True, attr=True)

    filter_instable = Property(depends_on='filter_coefficients', transient=True)
    filter_coefficients = Property(depends_on='+filter, fs', transient=True)
    _padding = Property(depends_on='filter_order', transient=True)

    @cached_property
    def _get__padding(self):
        return 3*self.filter_order

    @cached_property
    def _get_filter_instable(self):
        b, a = self.filter_coefficients
        return not np.all(np.abs(np.roots(a)) < 1)

    @cached_property
    def _get_filter_coefficients(self):
        if self.fs == 0:
            return
        if self.filter_btype is None:
            return [], []
        if self.filter_btype == 'bandpass':
            Wp = np.array([self.filter_freq_hp, self.filter_freq_lp])
        elif self.filter_btype == 'highpass':
            Wp = self.filter_freq_hp
        else:
            Wp = self.filter_freq_lp
        Wp = Wp/(0.5*self.fs)
        return signal.iirfilter(self.filter_order, Wp, 60, 2,
                                ftype=self.filter_type,
                                btype=self.filter_btype,
                                output='ba')


class EpochChannel(Channel):

    epoch_duration = Float(attr=True)
    epoch_size = Property(Int, depends_on='fs, epoch_duration', transient=True)

    @cached_property
    def _get_epoch_size(self):
        return int(self.epoch_duration*self.fs)

    def _get_initial_shape(self):
        return (0, self.epoch_size)

    def send(self, data):
        data.shape = (-1, self.epoch_size)
        self.send_all(data)

    def send_all(self, data):
        epochs = len(data)
        self._buffer.append(data)
        self._buffer.flush()

    def get_epochs(self, reject_threshold=None):
        if len(self._buffer) == 0:
            return np.array([]).reshape((-1, self.epoch_size))
        result = self._buffer[:]
        if reject_threshold is not None:
            result = result[result.max(axis=-1) < reject_threshold]
        return result

    def get_average(self, reject_threshold=None):
        return self.get_epochs(reject_threshold).mean(axis=0)

    def get_n(self, reject_threshold=None):
        return len(self.get_epochs(reject_threshold))

    def get_psd(self, reject_threshold=None, waveform_averages=None, rms=False,
                window=None):
        s = self.get_epochs(reject_threshold)
        if waveform_averages is not None:
            new_shape = [waveform_averages, -1, self.samples]
            s = s.reshape(new_shape).mean(axis=0)
        if window is not None:
            w = signal.get_window(window, s.shape[-1])
            s = w/w.mean()*s
        return self._get_psd(s, rms)

    def get_average_psd(self, reject_threshold=None, waveform_averages=None,
                        rms=False, window=None):
        psd = self.get_psd(reject_threshold, waveform_averages, rms, window)
        return psd.mean(axis=0)


class TimestampEpochChannel(EpochChannel):

    timestamps = Instance('tables.EArray')

    def _timestamps_default(self):
        atom = tables.Atom.from_dtype(np.dtype('int32'))
        rows = int(self.fs*self.expected_duration)
        if self.name + '_ts' in self.node and self.overwrite:
            self.node._f_get_child(self.name + '_ts')._f_remove()
        earray = self.node._v_file.createEArray(self.node._v_pathname, self.name
                                                + '_ts', atom, (0,),
                                                expectedrows=rows)
        return earray

    def send(self, data, timestamps):
        data.shape = (-1, self.epoch_size)
        self.send_all(data, [timestamps])

    def send_all(self, data, timestamps):
        epochs = len(data)
        self._buffer.append(data)
        self.timestamps.append(data)
        self._buffer.flush()


class FilteredEpochChannel(FilterMixin, EpochChannel):

    def get_waveforms(self, *args, **kw):
        result = super(FilteredEpochChannel, self).get_waveforms(*args, **kw)
        result = signal.detrend(result, type='linear')
        b, a = self.filter_coefficients
        return signal.filtfilt(b, a, result)


class SpikeChannel(EpochChannel):

    classifiers = Any
    timestamps = Any
    unique_classifiers = Set

    def __getitem__(self, key):
        return self._buffer[key]

    def _classifiers_default(self):
        atom = tables.Atom.from_dtype(np.dtype('int32'))
        rows = int(self.fs*self.expected_duration)
        earray = self.node._v_file.createEArray(self.node._v_pathname, self.name
                                                + '_classifier', atom, (0,),
                                                expectedrows=rows)
        return earray

    def _timestamps_default(self):
        atom = tables.Atom.from_dtype(np.dtype('int32'))
        rows = int(self.fs*self.expected_duration)
        earray = self.node._v_file.createEArray(self.node._v_pathname, self.name
                                                + '_ts', atom, (0,),
                                                expectedrows=rows)
        return earray

    def _get_initial_shape(self):
        return (0, self.epoch_size)

    def send(self, data, timestamp=np.nan, classifier=np.nan):
        data.shape = (-1, self.epoch_size)
        self.send_all(data, [timestamp], [classifier])

    def send_all(self, data, timestamps=None, classifiers=None):
        epochs = len(data)
        self._buffer.append(data)
        if timestamps is None:
            timestamps = [np.nan]*epochs
        self.timestamps.append(timestamps)
        if classifiers is None:
            classifiers = [np.nan]*epochs
        self.classifiers.append(classifiers)
        self.unique_classifiers.update(set(classifiers))
        self.added = data, timestamps, classifiers

    def get_recent(self, history=None):
        if len(self._buffer) == 0:
            return np.array([]).reshape((-1, self.epoch_size))
        if history is not None:
            result = self._buffer[-history:]
        else:
            result = self._buffer[:]

        if classifier is not None:
            classifiers = self.classifiers[-history:]
            mask = classifiers[:] == classifier
            return spikes[mask]
        return spikes

    def get_recent_average(self, count=1, classifier=None):
        return self.get_recent(count, classifier).mean(0)

    def get_average(self, reject_threshold=None):
        if len(self._buffer) == 0:
            return np.array([]).reshape((-1, self.epoch_size))
        result = self._buffer[:]
        if reject_threshold is not None:
            result = result[result.max(axis=0) < reject_threshold]
        return result.mean(axis=0)


class FileEpochChannel(FileMixin, EpochChannel):

    def _get_shape(self):
        return self._buffer.shape

    def _get_initial_shape(self):
        return (0, self.epoch_size)


class FileFilteredEpochChannel(FileMixin, FilteredEpochChannel):

    def _get_initial_shape(self):
        return (0, self.epoch_size)


import unittest


class TestEpochChannel(unittest.TestCase):

    def setUp(self):
        self.fh = tables.open_file('dummy_name', 'w', driver='H5FD_CORE',
                                   driver_core_backing_store=0)

    def tearDown(self):
        self.fh.close()

    def testEpochPSD(self):
        t = np.arange(200e3)/200e3
        frequency = 1000
        for amplitude in (0.5, 1.0, 2.0, 4.0):
            channel = FileEpochChannel(fs=200e3, epoch_duration=1,
                                       node=self.fh.root, name='temp',
                                       overwrite=True)
            for i in range(2):
                waveform = amplitude*np.sin(2*np.pi*frequency*t)
                channel.send(waveform[np.newaxis])
                frequencies = channel.get_fftfreq()
                freq_ix = np.argmin(np.abs(frequencies-frequency))

                # Test Vpp calculation
                psd = channel.get_average_psd()
                sin_vpp = psd[freq_ix]
                self.assertAlmostEqual(sin_vpp, amplitude)

                # Test Vrms calculation
                psd = channel.get_average_psd(rms=True)
                sin_rms = psd[freq_ix]
                self.assertAlmostEqual(sin_rms*np.sqrt(2), amplitude)

                # Test Vpp calculation using window.  A flattop window should be
                # the most accurate in estimating frequency level.
                psd = channel.get_average_psd(window='flattop')
                sin_vpp = psd[freq_ix]
                self.assertAlmostEqual(sin_vpp, amplitude, places=7)


class TestChannel(unittest.TestCase):

    def setUp(self):
        self.fh = tables.open_file('dummy_name', 'w', driver='H5FD_CORE',
                                   driver_core_backing_store=0)

    def tearDown(self):
        self.fh.close()

    def testChannelPSD(self):
        klass = get_channel_class('Channel', 'file')
        frequency = 1000
        fs = 100e3
        for duration in (1, 1.5, 5):
            t = np.arange(fs*duration)/fs
            for amplitude in (0.5, 1.0, 2.0, 4.0):
                channel = FileChannel(fs=fs, node=self.fh.root, name='temp',
                                      overwrite=True)

                waveform = amplitude*np.sin(2*np.pi*frequency*t)
                channel.send(waveform[np.newaxis])
                frequencies = channel.get_fftfreq()
                freq_ix = np.argmin(np.abs(frequencies-frequency))

                # Test Vpp calculation
                psd = channel.get_psd()
                sin_vpp = psd[freq_ix]
                self.assertAlmostEqual(sin_vpp, amplitude, places=5)

                # Test Vrms calculation
                psd = channel.get_psd(rms=True)
                sin_rms = psd[freq_ix]
                self.assertAlmostEqual(sin_rms*np.sqrt(2), amplitude, places=5)

                # Test single PSD calculation using DFT
                single_psd = channel.get_magnitude(frequency)
                self.assertAlmostEqual(single_psd, amplitude)
                single_psd_rms = channel.get_magnitude(frequency, rms=True)
                self.assertAlmostEqual(single_psd_rms*np.sqrt(2), amplitude)

                # Ensure that we are getting the equivalent of 0 for frequencies
                # not in the signal.
                single_psd = channel.get_magnitude(1)
                self.assertAlmostEqual(single_psd, 0, places=2)
                single_psd = channel.get_magnitude(frequency*0.5)
                self.assertAlmostEqual(single_psd, 0, places=2)

                # Test Vpp calculation using window.  A flattop window should be
                # the most accurate in estimating frequency level.
                psd = channel.get_psd(window='flattop')
                sin_vpp = psd[freq_ix]
                self.assertAlmostEqual(sin_vpp, amplitude, places=7)

                # Repeat the get_magnitude tests, and ensure they are more
                # accurate than without a window.
                sin_vpp = channel.get_magnitude(frequency, window='flattop')
                self.assertAlmostEqual(sin_vpp, amplitude, places=7)
                sin_vpp = channel.get_magnitude(1, window='flattop')
                self.assertAlmostEqual(sin_vpp, 0, places=4)
                sin_vpp = channel.get_magnitude(100, window='flattop')
                self.assertAlmostEqual(sin_vpp, 0, places=7)
                sin_vpp = channel.get_magnitude(10e3, window='flattop')
                self.assertAlmostEqual(sin_vpp, 0, places=7)


def get_channel(class_name, backend, mixins=None):
    classes = globals()
    channel_class = classes[class_name]
    backend_class = classes['{}Mixin'.format(backend.capitalize())]
    if mixins is None:
        mixins = []
    elif isinstance(mixins, basestring):
        mixins = [mixins]
    mixin_classes = [classes['{}Mixin'.format(m.capitalize())] for m in mixins]
    bases = [backend_class] + mixin_classes + [channel_class]
    name = backend.capitalize() + \
        ''.join(m.capitalize() for m in mixins) + \
        class_name
    return type(name, tuple(bases), {})


if __name__ == '__main__':
    unittest.main()
