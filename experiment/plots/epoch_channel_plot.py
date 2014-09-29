from traits.api import Property, Int, cached_property, Instance, Float
import numpy as np
from base_channel_plot import BaseChannelPlot


class EpochChannelPlot(BaseChannelPlot):

    source = Instance('experiment.channel.Channel')

    index_data = Property(depends_on='source.fs, source.snippet_size')
    index_screen = Property(depends_on='index_data')
    value_data = Property(depends_on='reject_threshold, '
                          'source.added, source.updated')
    value_screen = Property(depends_on='value_data')

    reject_threshold = Float(np.inf)
    update_rate = Int(5)
    update_counter = Int(0)

    def _index_mapper_updated(self):
        pass

    @cached_property
    def _get_index_data(self):
        return np.arange(self.source.epoch_size)/self.source.fs

    @cached_property
    def _get_index_screen(self):
        return self.index_mapper.map_screen(self.index_data)

    @cached_property
    def _get_value_data(self):
        return self.source.get_average()

    @cached_property
    def _get_value_screen(self):
        return self.value_mapper.map_screen(self.value_data)

    def _draw_plot(self, gc, view_bounds=None, mode="normal"):
        self._render(gc)

    def _render(self, gc):
        if len(self.value_screen) == 0:
            return
        with gc:
            print 'updating'
            gc.clip_to_rect(self.x, self.y, self.width, self.height)
            gc.set_stroke_color(self.line_color_)
            gc.set_line_width(self.line_width)
            gc.begin_path()
            gc.lines(np.column_stack((self.index_screen, self.value_screen)))
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
