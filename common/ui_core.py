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

import re

from .ui_styling import UI_Styling
from .drawing import ScissorStack

from .globals import Globals
from .decorators import debug_test_call, blender_version_wrapper
from .maths import Color
from .shaders import Shader


class UI_Draw:
    _initialized = False
    _stylesheet = None

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
        import gpu
        from gpu_extras.batch import batch_for_shader

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

    @staticmethod
    def load_stylesheet(path):
        UI_Draw._stylesheet = UI_Styling.from_file(path)
    @property
    def stylesheet(self):
        return self._stylesheet

    def update(self):
        ''' only need to call once every redraw '''
        UI_Draw._update()

    def draw(self, left, top, width, height, style):
        UI_Draw._draw(left, top, width, height, style)

ui_draw = Globals.set(UI_Draw())



def defer_dirty(fn):
    '''
    this UI_Core-specific decorator will prevent dirty propagation until the wrapped fn has finished
    '''
    def wrapper(self, *args, **kwargs):
        self._defer_dirty = True
        ret = fn(self, *args, **kwargs)
        self._defer_dirty = False
        self.dirty(parent=False, children=False)
        return ret
    return wrapper


class UI_Core:
    selector_type = 'DO NOT INSTANTIATE DIRECTLY!'

    def __init__(self, parent=None, id=None, classes=None, style=None):
        assert type(self) is not UI_Core, 'DO NOT INSTANTIATE DIRECTLY!'
        self._parent = None
        self._children = []
        self._selector = None
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
        self._defer_dirty = False   # set to True to defer dirty propagation (useful when many changes are occurring)
        self._defered_dirty_parent = False      # is True when dirtying parent was deferred
        self._defered_dirty_children = False    # is True when dirtying children was deferred
        self._defer_recalc = True   # set to True to defer recalculations (useful when many changes are occurring)

        self.style = style
        self.id = id
        self.classes = classes

        if parent:
            parent.append_child(self)

        self._defer_recalc = False
        self.dirty()

    def dirty(self, parent=True, children=False):
        self._is_dirty = True
        if self._defer_dirty:
            self._defered_dirty_parent |= parent
            self._defered_dirty_children |= children
            return
        if parent or self._defered_dirty_parent:
            if self._parent: self._parent.dirty(parent=True, children=False)
        if children or self._defered_dirty_children:
            for child in self._children:
                child.dirty(parent=False, children=True)
        self._defered_dirty_parent = False
        self._defered_dirty_children = False

    @property
    def children(self):
        return list(self._children)
    @defer_dirty
    def clear_children(self):
        for child in list(self._children):
            self.del_child(child)
    def append_child(self, child):
        assert child
        assert child not in self._children, 'attempting to add existing child?'
        if child._parent:
            child._parent.del_child(child)
        self._children.append(child)
        child.dirty()
        self.dirty()
    def del_child(self, child):
        assert child
        assert child in self._children, 'attempting to delete child that does not exist?'
        self._children.remove(child)
        child._parent = None
        child.dirty()
        self.dirty()

    @property
    def style(self):
        return str(self._style_str or '')
    @style.setter
    def style(self, style):
        self._style_str = str(style or '')
        self._style = UI_Styling('*{%s;}' % self._style_str)
        self.dirty()
    def add_style(self, style):
        self.style = '%s;%s' % (self.style, str(style or ''))

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, nid):
        nid = '' if nid is None else nid.strip()
        if self._id == nid: return
        self._id = id
        self.dirty(parent=True, children=True) # changing id can affect children styles!

    @property
    def classes(self):
        return ' '.join(self._classes)
    @classes.setter
    def classes(self, classes):
        classes = set(c for c in classes.split(' ') if c) if classes else set()
        if classes == self._classes: return
        self._classes = classes
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def add_class(self, cls):
        if cls in self._classes: return
        self._classes.add(cls)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def del_class(self, cls):
        if cls not in self._classes: return
        self._classes.discard(cls)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!

    @property
    def pseudoclasses(self):
        return set(self._pseudoclasses)
    def clear_pseudoclass(self):
        if not self._pseudoclasses: return
        self._pseudoclasses = set()
        self.dirty(parent=True, children=True)
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)
        self.dirty(parent=True, children=True)
    def del_pseudoclass(self, pseudo):
        if pseudo not in self._pseudoclasses: return
        self._pseudoclasses.discard(pseudo)
        self.dirty(parent=True, children=True)

    @property
    def visible(self):
        return self._is_visible

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

        stylesheet = ui_draw.stylesheet
        if stylesheet:
            self._computed_styles = stylesheet.compute_style(self._selector, self._style)
        else:
            self._computed_styles = self._style(self._selector)
        self._is_visible = self._computed_styles.get('display', 'auto') != 'none'
        if not self.visible:
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

        self.recalculate_children()

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
        self.position_children(
            left + margin_left + border_width + padding_left,
            top - margin_top - border_width - padding_top,
            width - margin_left - margin_right - border_width - border_width - padding_left - padding_right,
            height - margin_top - margin_bottom - border_width - border_width - padding_top - padding_bottom,
        )

    def draw(self):
        ScissorStack.push(self._l, self._t, self._w, self._h)
        #self.predraw()
        if True or ScissorStack.is_visible() and ScissorStack.is_box_visible(self._l, self._t, self._w, self._h):
            ui_draw.draw(self._l, self._t, self._w, self._h, self._computed_styles)
            for child in self._children: child.draw()
        ScissorStack.pop()

    def get_under_mouse(self, mx, my):
        if mx < self._l or mx >= self._l + self._w: return None
        if my > self._t or my <= self._t - self._h: return None
        for child in self._children:
            r = child.get_under_mouse(mx, my)
            if r: return r
        return self

    def recalculate_children(self): pass
    def position_children(self, left, top, width, height): pass
    def draw_children(self): pass

    # EVENTS
    def on_focus(self):         pass    # self gains focus (:active is added)
    def on_blur(self):          pass    # self loses focus (:active is removed)
    def on_keydown(self):       pass    # key is pressed down
    def on_keyup(self):         pass    # key is released
    def on_keypress(self):      pass    # key is entered (down+up)
    def on_mouseenter(self):    pass    # mouse enters self (:hover is added)
    def on_mousemove(self):     pass    # mouse moves over self
    def on_mousedown(self):     pass    # mouse left button is pressed down
    def on_mouseup(self):       pass    # mouse left button is released
    def on_mouseclick(self):    pass    # mouse left button is clicked (down+up while remaining on self)
    def on_mousedblclick(self): pass    # mouse left button is pressed twice in quick succession
    def on_mouseleave(self):    pass    # mouse leaves self (:hover is removed)
    def on_scroll(self):        pass    # self is being scrolled
