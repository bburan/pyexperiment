import numpy as np

from traits.api import (Property, Int, cached_property, Instance, Float,
                        on_trait_change)

from .base_channel_plot import BaseChannelPlot


class EpochChannelPlot(BaseChannelPlot):

    source = Instance('experiment.channel.Channel')

    index_data = Property(depends_on='source.fs, source.snippet_size')
    index_screen = Property(depends_on='index_data')
    value_data = Property(depends_on='reject_threshold, '
                          'source.added, source.updated')

    reject_threshold = Float(np.inf)
    update_rate = Int(5)
    update_counter = Int(0)

    def _index_mapper_updated(self):
        pass

    @cached_property
    def _get_index_data(self):
        return np.arange(self.source.epoch_size)/self.source.fs

    @cached_property
    def _get_value_data(self):
        return self.source.get_average()

    def _draw_plot(self, gc, view_bounds=None, mode="normal"):
        if not self._screen_cache_valid:
            s_index = self.index_mapper.map_screen(self.index_data)
            s_value = self.value_mapper.map_screen(self.value_data)
            self._screen_cache = s_index, s_value
            self._screen_cache_valid = True
        self._render(gc, self._screen_cache)

    def _render(self, gc, points):
        if len(points[0]) == 0:
            return
        with gc:
            gc.clip_to_rect(self.x, self.y, self.width, self.height)
            gc.set_stroke_color(self.line_color_)
            gc.set_line_width(self.line_width)
            gc.begin_path()
            gc.lines(np.column_stack(points))
            gc.stroke_path()
            gc.set_stroke_color(self.line_color_)
            gc.set_line_width(self.line_width)
            self._draw_default_axes(gc)

    def _data_changed(self, event_data):
        self.invalidate_and_redraw()

    def _data_added(self, event_data):
        self.update_counter += 1
        if (self.update_counter % self.update_rate) == 0:
            self.invalidate_and_redraw()
            self.update_counter = 0
