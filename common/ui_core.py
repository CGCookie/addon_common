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
import bpy
from inspect import signature

from .ui_styling import UI_Styling, ui_defaultstylings
from .ui_utilities import helper_wraptext
from .drawing import ScissorStack

from .useractions import Actions

from .globals import Globals
from .decorators import debug_test_call, blender_version_wrapper
from .maths import Vec2D, Color, mid, Box2D, Size2D, Point2D
from .shaders import Shader
from .fontmanager import FontManager

def get_font_path(fn, ext=None):
    if ext: fn = '%s.%s' % (fn,ext)
    paths = [
        os.path.abspath(os.path.curdir),
        os.path.join(os.path.abspath(os.path.curdir), 'fonts'),
        os.path.join(os.path.dirname(__file__), 'fonts'),
    ]
    for path in paths:
        p = os.path.join(path, fn)
        if os.path.exists(p): return p
    return None

fontmap = {
    'serif': {
        'normal normal': 'DroidSerif-Regular.ttf',
        'italic normal': 'DroidSerif-Italic.ttf',
        'normal bold':   'DroidSerif-Bold.ttf',
        'italic bold':   'DroidSerif-BoldItalic.ttf',
    },
    'sans-serif': {
        'normal normal': 'DroidSans-Blender.ttf',
        'italic normal': 'OpenSans-Italic.ttf',
        'normal bold':   'OpenSans-Bold.ttf',
        'italic bold':   'OpenSans-BoldItalic.ttf',
    },
    'monospace': {
        'normal normal': 'DejaVuSansMono.ttf',
        'italic normal': 'DejaVuSansMono.ttf',
        'normal bold':   'DejaVuSansMono.ttf',
        'italic bold':   'DejaVuSansMono.ttf',
    },
}
def setup_font(fontid):
    FontManager.aspect(1, fontid)
    FontManager.enable_kerning_default(fontid)
def get_font(fontfamily, fontstyle=None, fontweight=None):
    if fontfamily in fontmap:
        styleweight = '%s %s' % (fontstyle or 'normal', fontweight or 'normal')
        fontfamily = fontmap[fontfamily][styleweight]
    path = get_font_path(fontfamily)
    assert path, 'could not find font "%s"' % fontfamily
    fontid = FontManager.load(path, setup_font)
    return fontid


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

        def draw(left, top, width, height, dpi_mult, style):
            nonlocal shader, batch, def_color
            def set_uniform_float(shader_var, style_key, default_val):
                shader.uniform_float(shader_var, style.get(style_key, default_val))
            def set_uniform_float_mult(shader_var, style_key, default_val):
                shader.uniform_float(shader_var, style.get(style_key, default_val) * dpi_mult)
            shader.bind()
            shader.uniform_float('left',   left)
            shader.uniform_float('top',    top)
            shader.uniform_float('right',  left+width-1)
            shader.uniform_float('bottom', top-height+1)
            set_uniform_float_mult('margin_left',   'margin-left',   0)
            set_uniform_float_mult('margin_right',  'margin-right',  0)
            set_uniform_float_mult('margin_top',    'margin-top',    0)
            set_uniform_float_mult('margin_bottom', 'margin-bottom', 0)
            set_uniform_float_mult('border_width',  'border-width',  0)
            set_uniform_float_mult('border_radius', 'border-radius', 0)
            set_uniform_float('border_left_color',   'border-left-color',   def_color)
            set_uniform_float('border_right_color',  'border-right-color',  def_color)
            set_uniform_float('border_top_color',    'border-top-color',    def_color)
            set_uniform_float('border_bottom_color', 'border-bottom-color', def_color)
            set_uniform_float('background_color',    'background-color',    def_color)
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

    def draw(self, left, top, width, height, dpi_mult, style):
        UI_Draw._draw(left, top, width, height, dpi_mult, style)

ui_draw = Globals.set(UI_Draw())



'''
UI_Document manages UI_Body

example hierarchy of UI

- UI_Body: (singleton!)
    - UI_Dialog: tooltips
    - UI_Dialog: menu
        - help
        - about
        - exit
    - UI_Dialog: tools
        - UI_Button: toolA
        - UI_Button: toolB
        - UI_Button: toolC
    - UI_Dialog: options
        - option1
        - option2
        - option3


clean call order

- compute_style (only if style is dirty)
    - call compute_style on all children
    - dirtied by change in style, ID, class, pseudoclass, parent, or ID/class/pseudoclass of an ancestor
    - cleaning style dirties size
- compute_preferred_size (only if size or content are dirty)
    - determines min, max, preferred size for element (override in subclass)
    - for containers that resize based on children, whether wrapped (inline), list (block), or table, ...
        - 

'''


class UI_Element_Utils:
    @staticmethod
    def defer_dirty(properties=None, parent=True, children=False):
        ''' prevents dirty propagation until the wrapped fn has finished '''
        def wrapper(fn):
            def wrapped(self, *args, **kwargs):
                self._defer_dirty = True
                ret = fn(self, *args, **kwargs)
                self._defer_dirty = False
                self.dirty(properties, parent=parent, children=children)
                return ret
            return wrapped
        return wrapper

    _option_callbacks = {}
    @staticmethod
    def add_option_callback(option):
        def wrapper(fn):
            def wrapped(self, *args, **kwargs):
                ret = fn(self, *args, **kwargs)
                return ret
            UI_Element_Utils._option_callbacks[option] = wrapped
            return wrapped
        return wrapper

    def call_option_callback(self, option, default, *args, **kwargs):
        option = option if option not in UI_Element_Utils._option_callbacks else default
        UI_Element_Utils._option_callbacks[option](self, *args, **kwargs)

# https://www.w3schools.com/jsref/obj_event.asp
# https://javascript.info/bubbling-and-capturing
class UI_Event:
    phases = [
        'none',
        'capturing',
        'at target',
        'bubbling',
    ]

    def __init__(self):
        self._eventPhase = 'none'
        self._cancelBubble = False
        self._cancelCapture = False
        self._target = None
        self._defaultPrevented = False

    def stop_propagation():
        self.stop_bubbling()
        self.stop_capturing()
    def stop_bubbling():
        self._cancelBubble = True
    def stop_capturing():
        self._cancelCapture = True

    def prevent_default():
        self._defaultPrevented = True

    @property
    def event_phase(self): return self._eventPhase
    @event_phase.setter
    def event_phase(self, v):
        assert v in self.phases, "attempting to set event_phase to unknown value (%s)" % str(v)
        self._eventPhase = v

    @property
    def bubbling(self):
        return self._eventPhase == 'bubbling' and not self._cancelBubble
    @property
    def capturing(self):
        return self._eventPhase == 'capturing' and not self._cancelCapture
    @property
    def atTarget(self):
        return self._eventPhase == 'at target'

    @property
    def target(self): return self._target

    @property
    def default_prevented(self): return self._defaultPrevented

    @property
    def eventPhase(self): return self._eventPhase



class UI_Element(UI_Element_Utils):
    def __init__(self, tagName, **kwargs):
        # set to blank defaults, will be set again later in __init__()
        self._tagName     = ''      # determines type of UI element
        self._id          = ''      # unique identifier
        self._classes_str = ''      # list of classes (space delimited string)
        self._style_str   = ''      # custom style string
        self._parent      = None    # set in parent.append_child(self) below
        self._children    = []      # list of all children
        self._scrollTop   = 0       # distance element is scrolled vertically
        self._scrollLeft  = 0       # distance element is scrolled horizontally
        self._innerText   = ''      # label, text to display, etc.

        # all events with their respective callbacks
        self._events = {
            'on_focus':         [],     # focus is gained (:active is added)
            'on_blur':          [],     # focus is lost (:active is removed)
            'on_keydown':       [],     # key is pressed down
            'on_keyup':         [],     # key is released
            'on_keypress':      [],     # key is entered (down+up)
            'on_mouseenter':    [],     # mouse enters self (:hover is added)
            'on_mousemove':     [],     # mouse moves over self
            'on_mousedown':     [],     # mouse left button is pressed down
            'on_mouseup':       [],     # mouse left button is released
            'on_mouseclick':    [],     # mouse left button is clicked (down+up while remaining on self)
            'on_mousedblclick': [],     # mouse left button is pressed twice in quick succession
            'on_mouseleave':    [],     # mouse leaves self (:hover is removed)
            'on_scroll':        [],     # self is being scrolled
        }

        # updated by main ui system (hover, active, focus)
        self._pseudoclasses = set()     # TODO: should order matter here? (make list)

        # initialize styles in order: default, focus, active, hover
        self._styling_default = UI_Styling()
        self._styling_default.append(ui_defaultstylings.filter_styling(tagName))
        self._styling_default.append(ui_defaultstylings.filter_styling(tagName, 'focus'))
        self._styling_default.append(ui_defaultstylings.filter_styling(tagName, 'active'))
        self._styling_default.append(ui_defaultstylings.filter_styling(tagName, 'hover'))
        self._styling_default.append(ui_defaultstylings.filter_styling(tagName, ['hover','active']))

        # cache
        self._classes = []              # classes applied to element, set by self.classes, based on self._classes_str
        self._selector = None           # full selector of self, built in compute_style()
        self._styling_custom = None     # custom style UI_Style for self, set by self.style
        self._computed_styles = None    # computed style UI_Style after applying all styling
        self._is_visible = False        # indicates if self is visible, set in compute_style(), based on self._computed_styles
        self._innerTextWrapped = None

        # TODO: REPLACE WITH BETTER PROPERTIES AND DELETE!!
        self._preferred_width, self._preferred_height = 0,0
        self._content_width, self._content_height = 0,0
        self._l, self._t, self._w, self._h = 0,0,0,0

        # various sizes and boxes (set in self._position), used for layout and drawing
        self._preferred_size = Size2D()                         # computed preferred size, set in self._layout, used as suggestion to parent
        self._pref_content_size = Size2D()                      # size of content
        self._pref_full_size = Size2D()                         # _pref_content_size + margins + border + padding
        self._box_draw = Box2D(topleft=(0,0), size=(-1,-1))     # where UI will be drawn (restricted by parent)
        self._box_full = Box2D(topleft=(0,0), size=(-1,-1))     # where UI would draw if not restricted (offset for scrolling)

        self._dirty_properties = {              # set of dirty properties, add through self.dirty to force propagation of dirtiness
            'style',                            # force recalculations of style
            'size',                             # force recalculations of size
            'content',                          # content of self has changed
        }
        self._dirty_propagation = {             # contains deferred dirty propagation for parent and children; parent will be dirtied later
            'defer':    False,                  # set to True to defer dirty propagation (useful when many changes are occurring)
            'parent':   set(),                  # set of properties to dirty for parent
            'children': set(),                  # set of properties to dirty for children
        }
        self._defer_clean = False               # set to True to defer cleaning (useful when many changes are occurring)

        self.tagName = tagName
        for (k,v) in kwargs.items():
            if k in self._events or ('on_%s'%k) in self._events:
                # key is an event; set callback
                self.addEventListener(k, v)
            elif hasattr(self, k):
                # need to test that a setter exists for the property
                class_attr = getattr(type(self), k, None)
                if type(class_attr) is property:
                    # this is a property
                    if class_attr.fset is None:
                        # read-only
                        pass
                    else:
                        setattr(self, k, v)
        if 'parent' in kwargs:
            # note: parent.append_child(self) will set self._parent
            kwargs['parent'].append_child(self)
        if 'children' in kwargs:
            for child in kwargs['children']:
                self.append_child(child)

        self._defer_recalc = False
        self.dirty()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        info = [('tagname', self._tagName), ('id', self._id)]
        info = ['%s="%s"' % (l,str(v)) for (l,v) in info if v]
        return '<UI_Element %s>' % ' '.join(info)

    def dirty(self, properties=None, parent=True, children=False):
        if properties is None: properties = {'style', 'size', 'content'}
        elif type(properties) is str: properties = {properties}
        elif type(properties) is list: properties = set(properties)
        self._dirty_properties |= properties
        if parent: self._dirty_propagation['parent'] |= properties
        if children: self._dirty_propagation['children'] |= properties
        self.propagate_dirtiness()

    @property
    def is_dirty(self):
        return bool(self._dirty_properties) or bool(self._dirty_propagation['parent']) or bool(self._dirty_propagation['children'])

    def propagate_dirtiness(self):
        if self._dirty_propagation['defer']: return
        if self._dirty_propagation['parent']:
            if self._parent:
                self._parent.dirty(self._dirty_propagation['parent'], parent=True, children=False)
            self._dirty_propagation['parent'].clear()
        if self._dirty_propagation['children']:
            for child in self._children:
                child.dirty(self._dirty_propagation['children'], parent=False, children=True)
            self._dirty_propagation['children'].clear()

    @property
    def defer_dirty_propagation(self):
        return self._dirty_propagation['defer']
    @defer_dirty_propagation.setter
    def defer_dirty_propagation(self, v):
        self._dirty_propagation['defer'] = bool(v)
        self.propagate_dirtiness()

    def clean(self):
        '''
        No need to clean if
        - already clean,
        - possibly more dirtiness to propagate,
        - if deferring cleaning.
        '''
        if not self.is_dirty or self._defer_clean: return

        # clean various properties
        self._compute_style()
        self._compute_content()
        self._compute_preferred_size()

    def _compute_style(self):
        '''
        rebuilds self._selector and computes the stylesheet, propagating computation to children
        '''
        if self._defer_clean: return
        if 'style' not in self._dirty_properties: return

        self.defer_dirty_propagation = True

        # rebuild up full selector
        sel_parent = [] if not self._parent else self._parent._selector
        sel_type = self._tagName
        sel_id = '#%s' % self._id if self._id else ''
        sel_cls = ''.join('.%s' % c for c in self._classes)
        sel_pseudo = ''.join(':%s' % p for p in self._pseudoclasses)
        self._selector = sel_parent + [sel_type + sel_id + sel_cls + sel_pseudo]

        # compute styles applied to self based on selector
        if not self._styling_custom:
            self._styling_custom = UI_Styling('*{%s;}' % self._style_str)
        self._computed_styles = self._styling_default.compute_style(self._selector, ui_draw.stylesheet, self._styling_custom)
        self._is_visible = self._computed_styles.get('display', 'auto') != 'none'

        fontfamily = self._computed_styles.get('font-family', 'sans-serif')
        fontstyle = self._computed_styles.get('font-style', 'normal')
        fontweight = self._computed_styles.get('font-weight', 'normal')
        self._fontid = get_font(fontfamily, fontstyle, fontweight)
        self._fontsize = float(self._computed_styles.get('font-size', 12))
        self._fontcolor = self._computed_styles.get('color', (0,0,0,1))

        self._whitespace = self._computed_styles.get('white-space', 'normal')

        # tell children to recompute selector
        for child in self._children: child._compute_style()

        # style changes might have changed size
        self.dirty('size')
        self._dirty_properties.discard('style')

        self.defer_dirty_propagation = False

    def _compute_content(self):
        if self._defer_clean: return
        if 'content' not in self._dirty_properties: return
        if not self.is_visible: return

        self.defer_dirty_propagation = True

        self.compute_content()
        for child in self._children: child._compute_content()

        # content changes might have changed size
        self.dirty('size')
        self._dirty_properties.discard('content')

        self.defer_dirty_propagation = False

    def _compute_preferred_size(self):
        if self._defer_clean: return
        if 'size' not in self._dirty_properties: return
        if not self.is_visible: return

        self.defer_dirty_propagation = True

        self._content_width, self._content_height = 0, 0
        for child in self._children: child._compute_preferred_size()
        # self.compute_children_content_size()

        self.defer_dirty_propagation = False


    @property
    def tagName(self):
        return self._tagName
    @tagName.setter
    def tagName(self, ntagName):
        errmsg = 'Tagname must contain only alpha and cannot be empty'
        assert type(ntagName) is str, errmsg
        ntagName = ntagName.lower()
        assert ntagName, errmsg
        assert len(set(ntagName) - set('abcdefghijklmnopqrstuvwxyz')) == 0, errmsg
        if self._tagName == ntagName: return
        self._tagName = ntagName
        self.dirty(parent=True, children=True) # changing tagName can affect children styles!

    @property
    def innerText(self):
        return self._innerText
    @innerText.setter
    def innerText(self, nText):
        if self._innerText == nText: return
        self._innerText = nText
        self.dirty()

    @property
    def parent(self):
        return self._parent
    def get_pathToRoot(self):
        l,cur = [],self
        while cur: l,cur = l+[cur],cur._parent
        return l

    @property
    def children(self):
        return list(self._children)
    def append_child(self, child):
        assert child
        if child in self._children:
            # attempting to add existing child?
            return
        if child._parent:
            # detach child from prev parent
            child._parent.delete_child(child)
        self._children.append(child)
        child._parent = self
        child.dirty(parent=False, children=True)
        self.dirty()
    def delete_child(self, child):
        assert child
        assert child in self._children, 'attempting to delete child that does not exist?'
        self._children.remove(child)
        child._parent = None
        child.dirty()
        self.dirty('content')
    @UI_Element_Utils.defer_dirty()
    def clear_children(self):
        for child in list(self._children):
            self.delete_child(child)

    @property
    def style(self):
        return str(self._style_str)
    @style.setter
    def style(self, style):
        self._style_str = str(style or '')
        self._styling_custom = None
        self.dirty()
    def add_style(self, style):
        self._style_str = '%s;%s' % (self._style_str, str(style or ''))
        self._styling_custom = None
        self.dirty()

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, nid):
        nid = '' if nid is None else nid.strip()
        if self._id == nid: return
        self._id = nid
        self.dirty(parent=True, children=True) # changing id can affect children styles!

    @property
    def classes(self):
        return str(self._classes_str) # ' '.join(self._classes)
    @classes.setter
    def classes(self, classes):
        classes = ' '.join(c for c in classes.split(' ') if c) if classes else ''
        l = classes.split(' ')
        pcount = { p:0 for p in l }
        classes = []
        for p in l:
            pcount[p] += 1
            if pcount[p] == 1: classes += [p]
        classes_str = ' '.join(classes)
        if self._classes_str == classes_str: return
        self._classes_str = classes_str
        self._classes = classes
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def add_class(self, cls):
        assert ' ' not in cls, 'cannot add class "%s" to "%s" because it has a space in it' % (cls, self._tagName)
        if cls in self._classes: return
        self._classes.add(cls)
        self._classes_str = '%s %s' (self._classes_str, cls)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def del_class(self, cls):
        assert ' ' not in cls, 'cannot del class "%s" from "%s" because it has a space in it' % (cls, self._tagName)
        if cls not in self._classes: return
        self._classes.remove(cls)
        self._classes_str = ' '.join(self._classes)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!

    @property
    def pseudoclasses(self):
        return set(self._pseudoclasses)
    def clear_pseudoclass(self):
        if not self._pseudoclasses: return
        self._pseudoclasses = set()
        self.dirty(parent=True, children=True) # changing pseudoclasses can affect children styles!
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)
        self.dirty(parent=True, children=True) # changing pseudoclasses can affect children styles!
    def del_pseudoclass(self, pseudo):
        if pseudo not in self._pseudoclasses: return
        self._pseudoclasses.discard(pseudo)
        self.dirty(parent=True, children=True) # changing pseudoclasses can affect children styles!
    @property
    def is_active(self): return 'active' in self._pseudoclasses
    @property
    def is_hovered(self): return 'hover' in self._pseudoclasses
    @property
    def is_focused(self): return 'focus' in self._pseudoclasses

    @property
    def scrollTop(self):
        return self._scrollTop
    @scrollTop.setter
    def scrollTop(self, v):
        self._scrollTop = v
        self.dirty()

    @property
    def scrollLeft(self):
        return self._scrollLeft
    @scrollLeft.setter
    def scrollLeft(self, v):
        self._scrollLeft = v
        self.dirty()

    @property
    def is_visible(self):
        # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!
        return self._is_visible

    def get_visible_children(self):
        # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!
        # NOTE: returns list of children without `display:none` style.
        #       does _NOT_ mean that the child is going to be drawn
        #       (might still be clipped with scissor or `visibility:hidden` style)
        return [child for child in self._children if child.is_visible]


    def layout(self, **kwargs):
        # through this function, we are calculating and committing to a certain width and height
        # although the parent element might give us something different.  if we end up with a
        # different width and height in self.position() below, we will need to improvise by
        # adjusting margin (if bigger) or using scrolling (if smaller)

        if not self.is_dirty: return
        #if self._defer_recalc: return
        if not self.is_visible: return

        dpi_mult = Globals.drawing.get_dpi_mult()
        display = self._computed_styles.get('display', 'block')
        min_width,  max_width  = self._get_style_num('min-width',  0), self._get_style_num('max-width',  float('inf'))
        min_height, max_height = self._get_style_num('min-height', 0), self._get_style_num('max-height', float('inf'))
        margin_top,  margin_right,  margin_bottom,  margin_left  = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width', 0)

        # determine how much space we will need for all the content (children)
        for child in self._children:
            child.layout()

        self.call_option_callback(('layout:%s' % display), 'layout:block')

        self._preferred_width = (
            margin_left + border_width + padding_left +
            mid(self._get_style_num('width', self._content_width), min_width, max_width) +
            padding_right + border_width + margin_right
        )

        self._preferred_height = (
            margin_top + border_width + padding_top +
            mid(self._get_style_num('height', self._content_height), min_height, max_height) +
            padding_bottom + border_width + margin_bottom
        )

    @UI_Element_Utils.add_option_callback('layout:flexbox')
    def layout_flexbox(self):
        style = self._computed_styles
        direction = style.get('flex-direction', 'row')
        wrap = style.get('flex-wrap', 'nowrap')
        justify = style.get('justify-content', 'flex-start')
        align_items = style.get('align-items', 'flex-start')
        align_content = style.get('align-content', 'flex-start')

    @UI_Element_Utils.add_option_callback('layout:block')
    def layout_block(self):
        pass

    @UI_Element_Utils.add_option_callback('layout:inline')
    def layout_inline(self):
        pass

    @UI_Element_Utils.add_option_callback('layout:none')
    def layout_none(self):
        pass


    @UI_Element_Utils.add_option_callback('position:flexbox')
    def position_flexbox(self, left, top, width, height):
        pass
    @UI_Element_Utils.add_option_callback('position:block')
    def position_flexbox(self, left, top, width, height):
        pass
    @UI_Element_Utils.add_option_callback('position:inline')
    def position_flexbox(self, left, top, width, height):
        pass
    @UI_Element_Utils.add_option_callback('position:none')
    def position_flexbox(self, left, top, width, height):
        pass


    def position(self, left, top, width, height):
        # pos and size define where this element exists
        self._l, self._t = left, top
        self._w, self._h = width, height

        dpi_mult = Globals.drawing.get_dpi_mult()
        display = self._computed_styles.get('display', 'block')
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width', 0)

        l = left   + dpi_mult*(margin_left + border_width  + padding_left)
        t = top    - dpi_mult*(margin_top  + border_width  + padding_top)
        w = width  - dpi_mult*(margin_left + margin_right  + border_width + border_width + padding_left + padding_right)
        h = height - dpi_mult*(margin_top  + margin_bottom + border_width + border_width + padding_top  + padding_bottom)

        self.call_option_callback(('position:%s' % display), 'position:block', left, top, width, height)

        # wrap text
        wrap_opts = {
            'text':     self._innerText,
            'width':    w,
            'fontid':   self._fontid,
            'fontsize': self._fontsize,
            'preserve_newlines': (self._whitespace in {'pre', 'pre-line', 'pre-wrap'}),
            'collapse_spaces':   (self._whitespace not in {'pre', 'pre-wrap'}),
            'wrap_text':         (self._whitespace != 'pre'),
        }
        self._innerTextWrapped = helper_wraptext(**wrap_opts)

    def draw(self, d=0):
        # print(' '*d, self._l, self._t, self)
        ScissorStack.push(self._l, self._t, self._w, self._h)

        dpi_mult = Globals.drawing.get_dpi_mult()
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width', 0)

        if True or ScissorStack.is_visible() and ScissorStack.is_box_visible(self._l, self._t, self._w, self._h):
            ui_draw.draw(self._l, self._t, self._w, self._h, dpi_mult, self._computed_styles)
            if self._innerTextWrapped:
                size_prev = Globals.drawing.set_font_size(self._fontsize, fontid=self._fontid, force=True)
                Globals.drawing.text_draw2D(
                    self._innerTextWrapped,
                    Point2D((
                        self._l + dpi_mult*(margin_left + border_width + padding_left),
                        self._t - dpi_mult*(margin_top  + border_width + padding_top)
                    )),
                    self._fontcolor,
                )
                Globals.drawing.set_font_size(size_prev, fontid=self._fontid, force=True)
            for child in self._children: child.draw(d+1)
        ScissorStack.pop()

    def get_under_mouse(self, mx, my):
        if mx < self._l or mx >= self._l + self._w: return None
        if my > self._t or my <= self._t - self._h: return None
        for child in self._children:
            r = child.get_under_mouse(mx, my)
            if r: return r
        return self


    ################################################################################
    # event-related functionality

    def add_eventListener(self, event, callback, useCapture=False):
        if not event.startswith('on_'): event = 'on_%s' % event
        sig = signature(callback)
        if len(sig.parameters) == 0:
            old_callback = callback
            callback = lambda e: old_callback()
        self._events[event] += [(useCapture, callback)]

    def remove_eventListener(self, event, callback):
        if not event.startswith('on_'): event = 'on_%s' % event
        self._events[event] = [(capture,cb) for (capture,cb) in self._events[event] if cb != callback]

    def _fire_event(self, event, details):
        ph = details.event_phase
        cap, bub, df = details.capturing, details.bubbling, not details.default_prevented
        if (cap and ph == 'capturing') or (df and ph == 'at target'):
            for (cap,cb) in self._events[event]:
                if cap: cb(details)
        if (bub and ph == 'bubbling') or (df and ph == 'at target'):
            for (cap,cb) in self._events[event]:
                if not cap: cb(details)

    def dispatch_event(self, event, details=None):
        if not event.startswith('on_'): event = 'on_%s' % event
        details = details or UI_Event()
        path = self.get_pathToRoot()[1:] # skipping first item, which is self
        details.event_phase = 'capturing'
        for cur in path[::-1]: cur._fire_event(event, details)
        details.event_phase = 'at target'
        self._fire_event(event, details)
        details.event_phase = 'bubbling'
        for cur in path: cur._fireEvent(event, details)

    ################################################################################
    # the following methods can be overridden to create different types of UI

    ## Layout, Positioning, and Drawing
    # `self.layout_children()` should set `self._content_width` and `self._content_height` based on children.
    def compute_content(self): pass
    def compute_preferred_size(self): pass

    # def compute_children_content_size(self): pass
    # def layout_children(self): pass
    # def position_children(self, left, top, width, height): pass
    # def draw_children(self): pass


    #####################################################################
    # helper functions
    # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!

    def _get_style_num(self, k, def_v, min_v=None, max_v=None):
        v = self._computed_styles.get(k, 'auto')
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


class UI_Document:
    default_keymap = {
        'commit': {'RET',},
        'cancel': {'ESC',},
    }

    def __init__(self, context, **kwargs):
        self.actions = Actions(bpy.context, UI_Document.default_keymap)
        self._body = UI_Element(tagName='body')
        self._timer = context.window_manager.event_timer_add(1.0 / 120, window=context.window)
        self._under_mouse = None

    @property
    def body(self):
        return self._body

    def update(self, context, event):
        self.actions.update(context, event, self._timer, print_actions=True)

        mx,my = self.actions.mouse if self.actions.mouse else (0,0)
        under_mouse = self._body.get_under_mouse(mx, my)
        if self._under_mouse != under_mouse:
            if self._under_mouse:
                for e in self._under_mouse.get_pathToRoot():
                    e.del_pseudoclass('hover')
            self._under_mouse = under_mouse
            if self._under_mouse:
                for e in self._under_mouse.get_pathToRoot():
                    e.add_pseudoclass('hover')
        # if self.ui_elem.get_under_mouse(mx, my):
        #     self.ui_elem.add_pseudoclass('hover')
        #     if not self.ui_elem.is_active and self.actions.using('LEFTMOUSE'):
        #         self.ui_elem.add_pseudoclass('active')
        #         self.ui_elem.dispatch_event('mousedown')
        # elif self.ui_elem.is_hovered:
        #     self.ui_elem.del_pseudoclass('hover')
        # if not self.actions.using('LEFTMOUSE') and self.ui_elem.is_active:
        #     self.ui_elem.dispatch_event('mouseup')
        #     self.ui_elem.del_pseudoclass('active')
        #     if self.ui_elem.is_hovered: self.ui_elem.dispatch_event('mouseclick')

    def draw(self, context):
        w,h = context.region.width,context.region.height

        ScissorStack.start(context)
        Globals.ui_draw.update()

        self._body.clean()
        self._body.layout()
        self._body.position(0, h, w, h)

        # self._body.children[0].position(500, 300, 200, 200)
        self._body.draw()

        ScissorStack.end()

class UI_Document_old:
    '''
    This is the main manager of the UI system.
    '''

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
        self.tooltip_window = UI_Dialog(None, {'bgcolor':(0,0,0,0.75), 'visible':False})
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
        win = UI_Dialog(title, options)
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





