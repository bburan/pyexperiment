from __future__ import division

import numpy as np
from traits.api import Bool, Float

import logging
log = logging.getLogger(__name__)

from .base_channel_plot import BaseChannelPlot


class FFTChannelPlot(BaseChannelPlot):
    '''
    Designed for efficiently handling time series data stored in a channel.
    Each time a Channel.updated event is fired, the new data is obtained and
    plotted.
    '''
    _freq_cache_valid = Bool(False)
    _psd_cache_valid = Bool(False)
    _freq_screen_cache_valid = Bool(False)
    _psd_screen_cache_valid = Bool(False)

    db = Bool(True)
    reference = Float(1)

    def _index_mapper_updated(self):
        self._freq_screen_cache_valid = False
        self.invalidate_and_redraw()

    def _value_mapper_updated(self):
        self._psd_screen_cache_valid = False
        self.invalidate_and_redraw()

    def _data_changed(self):
        self._freq_cache_valid = False
        self._psd_cache_valid = False
        self.invalidate_and_redraw()

    def _data_added(self):
        self._psd_cache_valid = False
        self.invalidate_and_redraw()

    def _get_screen_points(self):
        if not self._freq_cache_valid:
            self._freq_cache = self.source.get_fftfreq()
            self._freq_cache_valid = True
            self._freq_screen_cache_valid = False
        if not self._psd_cache_valid:
            psd = self.source.get_average_psd()
            if self.db:
                psd = 20*np.log10(psd/self.reference)
            self._psd_cache = psd
            self._psd_cache_valid = True
            self._psd_screen_cache_valid = False

        if not self._freq_screen_cache_valid:
            self._freq_screen_cache = \
                self.index_mapper.map_screen(self._freq_cache)
            self._freq_screen_cache_valid = True
        if not self._psd_screen_cache_valid:
            self._psd_screen_cache = \
                self.value_mapper.map_screen(self._psd_cache)
            self._psd_screen_cache_valid = True
        self._screen_cache_valid = True

        return self._freq_screen_cache, self._psd_screen_cache

    def _draw_plot(self, gc, view_bounds=None, mode="normal"):
        if self.source is not None:
            points = self._get_screen_points()
            self._render(gc, points)

    def _render(self, gc, points):
        if len(points[0]) == 0:
            return
        with gc:
            gc.set_antialias(True)
            gc.clip_to_rect(self.x, self.y, self.width, self.height)
            gc.set_stroke_color(self.line_color_)
            gc.set_line_width(self.line_width)
            gc.begin_path()
            gc.lines(zip(*points))
            gc.stroke_path()
            self._draw_default_axes(gc)

    def __screen_cache_valid_changed(self):
        self._freq_screen_cache_valid = False
        self._psd_screen_cache_valid = False
