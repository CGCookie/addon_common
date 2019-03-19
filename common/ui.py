'''
Copyright (C) 2019 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os
import re
import math
import time
import struct
import random
import traceback
import functools
import urllib.request
from itertools import chain
from concurrent.futures import ThreadPoolExecutor

import bpy
import bgl

from .ui_styling import UI_Styling

from .globals import Globals
from .decorators import blender_version_wrapper
from .maths import Point2D, Vec2D, clamp, mid, Color
from .drawing import Drawing, ScissorStack
from .shaders import Shader
from .fontmanager import FontManager

from ..ext import png


gpu = None
batch_for_shader = None
@blender_version_wrapper('<=', '2.79')
def import_extras():
    pass
@blender_version_wrapper('>=', '2.80')
def import_extras():
    global gpu, batch_for_shader
    import gpu as gpu2
    from gpu_extras.batch import batch_for_shader as batch_for_shader2
    gpu = gpu2
    batch_for_shader = batch_for_shader2
import_extras()


class UI_Draw:
    _initialized = False

    @blender_version_wrapper('<=', '2.79')
    def init_draw(self):
        # TODO: test this implementation!
        assert False, 'function implementation not tested yet!!!'
        # UI_Draw._shader = Shader.load_from_file('ui', 'uielement.glsl', checkErrors=True)
        # sizeOfFloat, sizeOfInt = 4, 4
        # pos = [(0,0),(1,0),(1,1),  (0,0),(1,1),(0,1)]
        # count = len(pos)
        # buf_pos = bgl.Buffer(bgl.GL_FLOAT, [count, 2], pos)
        # vbos = bgl.Buffer(bgl.GL_INT, 1)
        # bgl.glGenBuffers(1, vbos)
        # vbo_pos = vbos[0]
        # bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vbo_pos)
        # bgl.glBufferData(bgl.GL_ARRAY_BUFFER, count * 2 * sizeOfFloat, buf_pos, bgl.GL_STATIC_DRAW)
        # bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)
        # en = UI_Draw._shader.enable
        # di = UI_Draw._shader.disable
        # eva = UI_Draw._shader.vertexAttribPointer
        # dva = UI_Draw._shader.disableVertexAttribArray
        # a = UI_Draw._shader.assign
        # def draw(left, top, width, height, style):
        #     nonlocal vbo_pos, count, en, di, eva, dva, a
        #     en()
        #     a('left',   left)
        #     a('top',    top)
        #     a('right',  left+width-1)
        #     a('bottom', top-height+1)
        #     a('margin_left',   style.get('margin-left', 0))
        #     a('margin_right',  style.get('margin-right', 0))
        #     a('margin_top',    style.get('margin-top', 0))
        #     a('margin_bottom', style.get('margin-bottom', 0))
        #     a('border_width',        style.get('border-width', 0))
        #     a('border_radius',       style.get('border-radius', 0))
        #     a('border_left_color',   style.get('border-left-color', (0,0,0,1)))
        #     a('border_right_color',  style.get('border-right-color', (0,0,0,1)))
        #     a('border_top_color',    style.get('border-top-color', (0,0,0,1)))
        #     a('border_bottom_color', style.get('border-bottom-color', (0,0,0,1)))
        #     a('background_color', style.get('background-color', (0,0,0,1)))
        #     eva(vbo_pos, 'pos', 2, bgl.GL_FLOAT)
        #     bgl.glDrawArrays(bgl.GL_TRIANGLES, 0, count)
        #     dva('pos')
        #     di()
        # UI_Draw._draw = draw

    @blender_version_wrapper('>=', '2.80')
    def init_draw(self):
        vertex_positions = [(0,0),(1,0),(1,1),  (1,1),(0,1),(0,0)]
        vertex_shader, fragment_shader = Shader.parse_file('uielement.glsl', includeVersion=False)
        shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertex_positions})
        get_pixel_matrix = Globals.drawing.get_pixel_matrix
        def_color = (0,0,0,1)

        def update():
            nonlocal shader, get_pixel_matrix
            shader.bind()
            shader.uniform_float("uMVPMatrix", get_pixel_matrix())

        def draw(left, top, width, height, style):
            nonlocal shader, batch, def_color
            shader.bind()
            shader.uniform_float('left',   left)
            shader.uniform_float('top',    top)
            shader.uniform_float('right',  left+width-1)
            shader.uniform_float('bottom', top-height+1)
            shader.uniform_float('margin_left',   style.get('margin-left',   0))
            shader.uniform_float('margin_right',  style.get('margin-right',  0))
            shader.uniform_float('margin_top',    style.get('margin-top',    0))
            shader.uniform_float('margin_bottom', style.get('margin-bottom', 0))
            shader.uniform_float('border_width',        style.get('border-width',  0))
            shader.uniform_float('border_radius',       style.get('border-radius', 0))
            shader.uniform_float('border_left_color',   style.get('border-left-color',   def_color))
            shader.uniform_float('border_right_color',  style.get('border-right-color',  def_color))
            shader.uniform_float('border_top_color',    style.get('border-top-color',    def_color))
            shader.uniform_float('border_bottom_color', style.get('border-bottom-color', def_color))
            shader.uniform_float('background_color', style.get('background-color', def_color))
            batch.draw(shader)

        UI_Draw._update = update
        UI_Draw._draw = draw

    def __init__(self):
        if not UI_Draw._initialized:
            self.init_draw()
            UI_Draw._initialized = True

    def update(self):
        ''' only need to call once every redraw '''
        UI_Draw._update()

    def draw(self, left, top, width, height, style):
        UI_Draw._draw(left, top, width, height, style)

Globals.set(UI_Draw())


class UI_Basic:
    selector_type = 'basic'

    def __init__(self, stylesheet=None, id=None, classes=None, style=None):
        self._ui_draw = Globals.ui_draw
        self._parent = None
        self._selector = None
        self._stylesheet = None
        self._id = None
        self._classes = set()
        self._pseudoclasses = set()
        self._style = None
        self._style_str = ''
        self._is_visible = False
        self._computed_styles = None

        # preferred size (set in self._recalculate), used for positioning and sizing
        self._width, self._height = 0,0
        self._min_width, self._min_height = 0,0
        self._max_width, self._max_height = 0,0

        # actual absolute position (set in self._update), used for drawing
        self._l, self._t, self._w, self._h = 0,0,0,0
        # offset drawing (for scrolling)
        self._x, self._y = 0,0

        self._is_dirty = True       # set to True (through self.dirty) to force recalculations
        self._defer_recalc = True   # set to True to defer recalculations (useful when many changes are occurring)

        self.stylesheet = stylesheet #or (parent.get_stylesheet() if parent else None)
        self.style = style
        self.id = id
        self.classes = classes

        self._defer_recalc = False
        self.dirty()

    def dirty(self, parent=True, inside=False):
        self._is_dirty = True
        if parent and self._parent: self._parent.dirty()
        if inside: self.dirty_inside()

    @property
    def stylesheet(self):
        return self._stylesheet
    @stylesheet.setter
    def stylesheet(self, stylesheet):
        self._stylesheet = stylesheet
        self.dirty()

    @property
    def style(self):
        return str(self._style_str)
    @stylesheet.setter
    def style(self, style):
        self._style_str = str(style)
        if not style:
            self._style = None
        else:
            self._style = UI_Styling('*{%s;}' % style)
        self.dirty()

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, id):
        self._id = '' if id is None else id.strip()
        self.dirty(parent=True, inside=True) # changing id can affect children styles!

    @property
    def classes(self):
        return ' '.join(self._classes)
    @classes.setter
    def classes(self, classes):
        if not classes: self._classes = set()
        else: self._classes = set(c for c in classes.split(' ') if c)
        self.dirty(parent=True, inside=True) # changing classes can affect children styles!
    def add_class(self, cls):
        if cls in self._classes: return
        self._classes.add(cls)
        self.dirty(parent=True, inside=True) # changing classes can affect children styles!
    def del_class(self, cls):
        #assert cls in self._classes, 'attempting to delete class that does not exist?'
        self._classes.discard(cls)
        self.dirty(parent=True, inside=True) # changing classes can affect children styles!

    def clear_pseudoclass(self):
        self._pseudoclasses = set()
        self.dirty(parent=True, inside=True)
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)
        self.dirty(parent=True, inside=True)
    def del_pseudoclass(self, pseudo):
        #assert pseudo in self._pseudoclasses, 'attempting to delete a pseudoclass that does not exist?'
        self._pseudoclasses.discard(pseudo)
        self.dirty(parent=True, inside=True)

    def _get_style_num(self, k, def_v, min_v=0, max_v=None):
        v = self._computed_styles.get(k, def_v)
        if v == 'auto': v = def_v
        if min_v is not None: v = max(min_v, v)
        if max_v is not None: v = min(max_v, v)
        return v
    def _get_style_trbl(self, kb):
        t = self._get_style_num('%s-top' % kb, 0)
        r = self._get_style_num('%s-right' % kb, 0)
        b = self._get_style_num('%s-bottom' % kb, 0)
        l = self._get_style_num('%s-left' % kb, 0)
        return (t,r,b,l)

    def recalculate(self):
        # recalculates width and height
        if not self._is_dirty: return
        if self._defer_recalc: return

        self._is_dirty = True

        sel_parent = [] if not self._parent else self._parent._selector
        sel_type = self.selector_type
        sel_id = '#%s' % self._id if self._id else ''
        sel_cls = ''.join('.%s' % c for c in self._classes)
        sel_pseudo = ''.join(':%s' % p for p in self._pseudoclasses)
        self._selector = sel_parent + [sel_type + sel_id + sel_cls + sel_pseudo]

        if self._stylesheet:
            self._computed_styles = self._stylesheet.compute_style(self._selector, self._style)
        else:
            self._computed_styles = {}
        self._is_visible = self._computed_styles.get('display', 'auto') != 'none'
        #self._is_visible = self._computed_styles.get('visibility', 'visible') != 'hidden'
        if not self._is_visible:
            #self._min_width, self._min_height, self._max_width, self._max_height = 0,0,0,0
            self._is_dirty = False
            return

        min_width, min_height = self._get_style_num('min-width', 0), self._get_style_num('min-height', 0)
        max_width, max_height = self._get_style_num('max-width', float('inf')), self._get_style_num('max-height', float('inf'))
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width', 0)

        self._min_width  = min_width
        self._min_height = min_height
        self._max_width  = max_width
        self._max_height = max_height

        self.recalculate_inside()

        # make sure there is room for margin + border + padding
        self._min_width  = (margin_left + border_width + padding_left) + self._min_width  + (padding_right  + border_width + margin_right )
        self._min_height = (margin_top  + border_width + padding_top ) + self._min_height + (padding_bottom + border_width + margin_bottom)
        self._max_width  = (margin_left + border_width + padding_left) + self._max_width  + (padding_right  + border_width + margin_right )
        self._max_height = (margin_top  + border_width + padding_top ) + self._max_height + (padding_bottom + border_width + margin_bottom)

    def position(self, left, top, width, height):
        # pos and size define where this element exists
        self._l, self._t = left, top
        self._w, self._h = width, height

        # might need to wrap text

        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width', 0)
        self.position_inside(
            left + margin_left + border_width + padding_left,
            top - margin_top - border_width - padding_top,
            width - margin_left - margin_right - border_width - border_width - padding_left - padding_right,
            height - margin_top - margin_bottom - border_width - border_width - padding_top - padding_bottom,
        )

    def draw(self):
        #ScissorStack.push((self._l, self._t), (self._w, self._h))
        #self.predraw()
        if True: # ScissorStack.is_visible() and ScissorStack.is_box_visible(self._l, self._t, self._w, self._h):
            self._ui_draw.draw(self._l, self._t, self._w, self._h, self._computed_styles)
            self.draw_inside()
        #ScissorStack.pop()

    def dirty_inside(self): pass
    def recalculate_inside(self): pass
    def position_inside(self, left, top, width, height): pass
    def draw_inside(self): pass



class UI_Container(UI_Basic):
    selector_type = 'container'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._children = []

    def dirty_inside(self):
        for child in self._children:
            child.dirty(parent=False, inside=True)

    def add_child(self, child):
        assert child
        assert child not in self._children, 'attempting to add existing child?'
        if child._parent:
            child._parent.del_child(child)
        self._children.append(child)
        child.dirty()
    def del_child(self, child):
        assert child
        assert child in self._children, 'attempting to delete child that does not exist?'
        self._children.remove(child)
        child._parent = None
        child.dirty()
        self.dirty()

    def visible_children(self):
        return [child for child in self._children if child._is_visible]

    def recalculate_inside(self):
        for child in self._children: child.recalculate()

        # assuming all children are drawn on top on one another
        w,h = self._min_width,self._min_height
        W,H = self._max_width,self._max_height
        for child in self.visible_children():
            w = max(w, child._min_width)
            h = max(h, child._min_height)
            W = min(W, child._max_width)
            H = min(H, child._max_height)
        self._min_width,self.min_height = w,h
        self._max_width,self.max_height = W,H

        # do not clean self if any children are still dirty (ex: they are deferring recalculation)
        self._is_dirty = any(child._is_dirty for child in self._children)

    def position_inside(self, left, top, width, height):
        for child in self.visible_children():
            child.position(left, top, width, height)

    def draw_inside(self):
        for child in self.visible_children():
            child.draw()



class UI_Label(UI_Basic):
    selector_type = 'label'

    def __init__(self, *args, **kwargs):
        super().__init__()


class UI_Button(UI_Basic):
    selector_type = 'button'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



class UI_Window(UI_Basic):
    selector_type = 'window'
    def __init__(self, *args, **kwargs):
        super().__init__()




class UI_WindowManager:
    def __init__(self, **kwargs):
        self.drawing = Globals.drawing
        self.windows = []
        self.windows_unfocus = None
        self.active = None
        self.active_last = None
        self.focus = None
        self.focus_darken = True
        self.focus_close_on_leave = True
        self.focus_close_distance = self.drawing.scale(30)

        self.tooltip_delay = 0.75
        self.tooltip_value = None
        self.tooltip_time = time.time()
        self.tooltip_show = kwargs.get('show tooltips', True)
        self.tooltip_window = UI_Window(None, {'bgcolor':(0,0,0,0.75), 'visible':False})
        self.tooltip_label = self.tooltip_window.add(UI_Label('foo bar'))
        self.tooltip_offset = Vec2D((15, -15))

        self.interval_id = 0
        self.intervals = {}

    def set_show_tooltips(self, v):
        self.tooltip_show = v
        if not v: self.tooltip_window.visible = v
    def set_tooltip_label(self, v):
        if not v:
            self.tooltip_window.visible = False
            self.tooltip_value = None
            return
        if self.tooltip_value != v:
            self.tooltip_window.visible = False
            self.tooltip_value = v
            self.tooltip_time = time.time()
            self.tooltip_label.set_label(v)
            return
        if time.time() >= self.tooltip_time + self.tooltip_delay:
            self.tooltip_window.visible = self.tooltip_show
        # self.tooltip_window.fn_sticky.set(self.active.pos + self.active.size)
        # self.tooltip_window.update_pos()

    def create_window(self, title, options):
        win = UI_Window(title, options)
        self.windows.append(win)
        return win

    def delete_window(self, win):
        if win.fn_event_handler: win.fn_event_handler(None, UI_Event('WINDOW', 'CLOSE'))
        if win == self.focus: self.clear_focus()
        if win == self.active: self.clear_active()
        if win in self.windows: self.windows.remove(win)
        win.delete()

    def clear_active(self): self.active = None

    def has_focus(self): return self.focus is not None
    def set_focus(self, win, darken=True, close_on_leave=False):
        self.clear_focus()
        if win is None: return
        win.visible = True
        self.focus = win
        self.focus_darken = darken
        self.focus_close_on_leave = close_on_leave
        self.active = win
        self.windows_unfocus = [win for win in self.windows if win != self.focus]
        self.windows = [self.focus]

    def clear_focus(self):
        if self.focus is None: return
        self.windows += self.windows_unfocus
        self.windows_unfocus = None
        self.active = None
        self.focus = None

    def draw_darken(self):
        bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glColor4f(0,0,0,0.25)    # TODO: use window background color??
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glBegin(bgl.GL_QUADS)   # TODO: not use immediate mode
        bgl.glVertex2f(-1, -1)
        bgl.glVertex2f( 1, -1)
        bgl.glVertex2f( 1,  1)
        bgl.glVertex2f(-1,  1)
        bgl.glEnd()
        bgl.glPopMatrix()
        bgl.glPopAttrib()

    def draw_postpixel(self, context):
        ScissorStack.start(context)
        bgl.glEnable(bgl.GL_BLEND)
        if self.focus:
            for win in self.windows_unfocus:
                win.draw_postpixel()
            if self.focus_darken:
                self.draw_darken()
            self.focus.draw_postpixel()
        else:
            for win in self.windows:
                win.draw_postpixel()
        self.tooltip_window.draw_postpixel()
        ScissorStack.end()

    def register_interval_callback(self, fn_callback, interval):
        self.interval_id += 1
        self.intervals[self.interval_id] = {
            'callback': fn_callback,
            'interval': interval,
            'next': 0,
        }
        return self.interval_id

    def unregister_interval_callback(self, interval_id):
        del self.intervals[self.interval_id]

    def update(self):
        cur_time = time.time()
        for interval_id in self.intervals:
            interval = self.intervals[interval_id]
            if interval['next'] > cur_time: continue
            interval['callback']()
            interval['next'] = cur_time + interval['interval']

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            mouse = Point2D((float(event.mouse_region_x), float(event.mouse_region_y)))
            self.tooltip_window.fn_sticky.set(mouse + self.tooltip_offset)
            self.tooltip_window.update_pos()
            if self.focus and self.focus_close_on_leave:
                d = self.focus.distance(mouse)
                if d > self.focus_close_distance:
                    self.delete_window(self.focus)

        ret = {}

        if self.active and self.active.state != 'main':
            ret = self.active.modal(context, event)
            if not ret: self.active = None
        elif self.focus:
            ret = self.focus.modal(context, event)
        else:
            self.active = None
            for win in reversed(self.windows):
                ret = win.modal(context, event)
                if ret:
                    self.active = win
                    break

        if self.active != self.active_last:
            if self.active_last and self.active_last.fn_event_handler:
                self.active_last.fn_event_handler(context, UI_Event('HOVER', 'LEAVE'))
            if self.active and self.active.fn_event_handler:
                self.active.fn_event_handler(context, UI_Event('HOVER', 'ENTER'))
        self.active_last = self.active

        if self.active:
            if self.active.fn_event_handler:
                self.active.fn_event_handler(context, event)
            if self.active:
                tooltip = self.active.get_tooltip()
                self.set_tooltip_label(tooltip)
        else:
            self.set_tooltip_label(None)

        return ret




