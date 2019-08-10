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
import time
import random
from inspect import signature
import traceback

import bpy
import bgl

from .blender import tag_redraw_all
from .ui_styling import UI_Styling, ui_defaultstylings
from .ui_utilities import helper_wraptext, convert_token_to_cursor
from .drawing import ScissorStack
from .fsm import FSM

from .useractions import Actions, kmi_to_keycode

from .globals import Globals
from .decorators import debug_test_call, blender_version_wrapper
from .maths import Vec2D, Color, mid, Box2D, Size1D, Size2D, Point2D, RelPoint2D, clamp
from .shaders import Shader
from .fontmanager import FontManager
from .utils import iter_head

from ..ext import png


'''
TODO:



'''


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


def get_image_path(fn, ext=None, subfolders=None):
    # if no subfolders are given, assuming image path is <root>/icons
    # or <root>/images where <root> is the 2 levels above this file
    if subfolders is None:
        subfolders = ['icons', 'images']
    if ext:
        fn = '%s.%s' % (fn,ext)
    path_here = os.path.dirname(__file__)
    path_root = os.path.join(path_here, '..', '..')
    paths = [os.path.join(path_root, p, fn) for p in subfolders]
    paths += [os.path.join(path_here, 'images', fn)]
    paths = [p for p in paths if os.path.exists(p)]
    return iter_head(paths, None)


def load_image_png(fn):
    if not hasattr(load_image_png, 'cache'): load_image_png.cache = {}
    if not fn in load_image_png.cache:
        # have not seen this image before
        # note: assuming 4 channels (rgba) per pixel!
        path = get_image_path(fn)
        print('Loading image "%s" (%s)' % (str(fn), str(path)))
        w,h,d,m = png.Reader(path).read()
        load_image_png.cache[fn] = [[r[i:i+4] for i in range(0,w*4,4)] for r in d]
    return load_image_png.cache[fn]



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
        vertex_shader, fragment_shader = Shader.parse_file('ui_element.glsl', includeVersion=False)
        shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertex_positions})
        get_pixel_matrix = Globals.drawing.get_pixel_matrix
        def_color = (0,0,0,1)

        def update():
            nonlocal shader, get_pixel_matrix
            shader.bind()
            shader.uniform_float("uMVPMatrix", get_pixel_matrix())

        def draw(left, top, width, height, dpi_mult, style, texture_id):
            nonlocal shader, batch, def_color
            def set_uniform_float(shader_var, style_key, default_val):
                v = style.get(style_key, (default_val, ''))
                if type(v) is tuple: v,u = v
                shader.uniform_float(shader_var, v)
            def set_uniform_float_mult(shader_var, style_key, default_val):
                v = style.get(style_key, (default_val, ''))
                if type(v) is tuple: v,u = v
                shader.uniform_float(shader_var, v * dpi_mult)
            shader.bind()
            shader.uniform_float('left',   left)
            shader.uniform_float('top',    top)
            shader.uniform_float('right',  left+width-1)
            shader.uniform_float('bottom', top-height+1)
            set_uniform_float_mult('margin_left',    'margin-left',    0)
            set_uniform_float_mult('margin_right',   'margin-right',   0)
            set_uniform_float_mult('margin_top',     'margin-top',     0)
            set_uniform_float_mult('margin_bottom',  'margin-bottom',  0)
            set_uniform_float_mult('padding_left',   'padding-left',   0)
            set_uniform_float_mult('padding_right',  'padding-right',  0)
            set_uniform_float_mult('padding_top',    'padding-top',    0)
            set_uniform_float_mult('padding_bottom', 'padding-bottom', 0)
            set_uniform_float_mult('border_width',   'border-width',   0)
            set_uniform_float_mult('border_radius',  'border-radius',  0)
            set_uniform_float('border_left_color',   'border-left-color',   def_color)
            set_uniform_float('border_right_color',  'border-right-color',  def_color)
            set_uniform_float('border_top_color',    'border-top-color',    def_color)
            set_uniform_float('border_bottom_color', 'border-bottom-color', def_color)
            set_uniform_float('background_color',    'background-color',    def_color)
            if texture_id == -1:
                shader.uniform_float('using_image', 0)
            else:
                # bgl.glBlendEquation(bgl.GL_FUNC_ADD)
                # bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
                bgl.glActiveTexture(bgl.GL_TEXTURE0)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, texture_id)
                shader.uniform_float('using_image', 1)
                shader.uniform_int('image', 0)
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

    def draw(self, left, top, width, height, dpi_mult, style, texture_id=-1):
        UI_Draw._draw(left, top, width, height, dpi_mult, style, texture_id)


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
    def defer_dirty(cause, properties=None, parent=True, children=False):
        ''' prevents dirty propagation until the wrapped fn has finished '''
        def wrapper(fn):
            def wrapped(self, *args, **kwargs):
                self._defer_dirty = True
                ret = fn(self, *args, **kwargs)
                self._defer_dirty = False
                self.dirty('dirtying deferred dirtied properties now: '+cause, properties, parent=parent, children=children)
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

    _cleaning_graph = {}
    _cleaning_graph_roots = set()
    _cleaning_graph_nodes = set()
    @staticmethod
    def add_cleaning_callback(label, labels_dirtied=None):
        # NOTE: this function decorator does NOT call self.dirty!
        UI_Element_Utils._cleaning_graph_nodes.add(label)
        g = UI_Element_Utils._cleaning_graph
        labels_dirtied = list(labels_dirtied) if labels_dirtied else []
        for l in [label]+labels_dirtied: g.setdefault(l, {'fn':None, 'children':[], 'parents':[]})
        def wrapper(fn):
            def wrapped_cleaning_callback(self, *args, **kwargs):
                ret = fn(self, *args, **kwargs)
                return ret
            g[label]['fn'] = fn
            g[label]['children'] = labels_dirtied
            for l in labels_dirtied: g[l]['parents'].append(label)

            # find roots of graph (any label that is not dirtied by another cleaning callback)
            UI_Element_Utils._cleaning_graph_roots = set(k for (k,v) in g.items() if not v['parents'])
            assert UI_Element_Utils._cleaning_graph_roots, 'cycle detected in cleaning callbacks'
            # TODO: also detect cycles such as: a->b->c->d->b->...
            #       done in call_cleaning_callbacks, but could be done here instead?

            return wrapped_cleaning_callback
        return wrapper

    def call_cleaning_callbacks(self, *args, **kwargs):
        g = UI_Element_Utils._cleaning_graph
        working = set(UI_Element_Utils._cleaning_graph_roots)
        done = set()
        while working:
            current = working.pop()
            assert current not in done, 'cycle detected in cleaning callbacks (%s)' % current
            if not all(p in done for p in g[current]['parents']): continue
            do_cleaning = False
            do_cleaning |= current in self._dirty_properties
            do_cleaning |= bool(self._dirty_callbacks.get(current, []))
            if do_cleaning:
                g[current]['fn'](self, *args, **kwargs)
            redirtied = [d for d in self._dirty_properties if d in done]
            if redirtied:
                # restarting
                working = set(UI_Element_Utils._cleaning_graph_roots)
                done = set()
                # assert False, "Redirtied %s after cleaning %s" % (
                #     str(redirtied),
                #     current
                # )
            else:
                working.update(g[current]['children'])
                done.add(current)


    #####################################################################
    # helper functions
    # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!

    re_percent = re.compile(r'(?P<v>\d+)%')
    def _get_style_num(self, k, def_v, percent_of=None, min_v=None, max_v=None, scale=None, override_v=None):
        v = self._computed_styles.get(k, 'auto')
        if v == 'auto':
            if def_v == 'auto': return def_v
            v = def_v
        if type(v) is tuple:
            # tuple: (scalar, unit)
            v,u = v
            if u == '%':
                v = (percent_of if percent_of is not None else float(def_v)) * float(v) / 100
            elif u == 'px' or u == '':
                pass
            else:
                print('Saw unhandled unit "%s" for key %s' % (str(u), str(k)))
                pass
        if override_v is not None: v = override_v
        v = float(v)
        if min_v is not None: v = max(float(min_v), v)
        if max_v is not None: v = min(float(max_v), v)
        if scale is not None: v *= scale
        return v

    def _get_style_trbl(self, kb, scale=None):
        t = self._get_style_num('%s-top' % kb, 0)
        r = self._get_style_num('%s-right' % kb, 0)
        b = self._get_style_num('%s-bottom' % kb, 0)
        l = self._get_style_num('%s-left' % kb, 0)
        if scale is None: return (t,r,b,l)
        return (t*scale, r*scale, b*scale, l*scale)


# https://www.w3schools.com/jsref/obj_event.asp
# https://javascript.info/bubbling-and-capturing
class UI_Event:
    phases = [
        'none',
        'capturing',
        'at target',
        'bubbling',
    ]

    def __init__(self, target=None, mouse=None, key=None):
        self._eventPhase = 'none'
        self._cancelBubble = False
        self._cancelCapture = False
        self._target = target
        self._mouse = mouse
        self._key = key
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
    def mouse(self): return self._mouse

    @property
    def key(self): return self._key

    @property
    def default_prevented(self): return self._defaultPrevented

    @property
    def eventPhase(self): return self._eventPhase


class UI_Element_Properties:
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
        self._styling_default = None
        self.dirty('changing tagName can affect children styles', parent=True, children=True)

    @property
    def innerText(self):
        return self._innerText
    @innerText.setter
    def innerText(self, nText):
        if self._innerText == nText: return
        self._innerText = nText
        self.dirty('changing innerText changes content', 'content')
        self.dirty_flow()

    @property
    def innerTextAsIs(self):
        return self._innerTextAsIs
    @innerTextAsIs.setter
    def innerTextAsIs(self, v):
        v = str(v) if v is not None else None
        if self._innerTextAsIs == v: return
        self._innerTextAsIs = v
        self.dirty('changing innerTextAsIs changes content', 'content')

    @property
    def parent(self):
        return self._parent
    def get_pathToRoot(self):
        l=[self]
        while l[-1]._parent: l.append(l[-1]._parent)
        return l
        l,cur = [],self
        while cur: l,cur = l+[cur],cur._parent
        return l
    def get_root(self):
        c = self
        while c._parent: c = c._parent
        return c

    def getElementById(self, element_id):
        if element_id is None: return None
        if self._id == element_id: return self
        for child in self._children_all:
            e = child.getElementById(element_id)
            if e is not None: return e
        return None

    def getElementsByName(self, element_name):
        if element_name is None: return None
        ret = [e for child in self._children_all for e in child.getElementsByName(element_name)]
        if self._name == element_name: ret.append(self)
        return ret

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
        child.dirty('appending child to parent', parent=False, children=True)
        self.dirty('appending new child changes content', 'content')
        return child
    def delete_child(self, child):
        assert child
        assert child in self._children, 'attempting to delete child that does not exist?'
        self._children.remove(child)
        child._parent = None
        child.dirty('deleting child from parent')
        self.dirty('deleting child changes content', 'content')
    @UI_Element_Utils.defer_dirty('clearing children')
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
        self.dirty('changing style for %s affects style' % str(self), 'style', parent=False, children=False)
        if self._parent:
            self.dirty('changing style for %s affects parent content' % str(self), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def add_style(self, style):
        self._style_str = '%s;%s' % (self._style_str, str(style or ''))
        self._styling_custom = None
        self.dirty('adding style for %s affects style' % str(self), 'style', parent=False, children=False)
        if self._parent:
            self.dirty('adding style for %s affects parent content' % str(self), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, nid):
        nid = '' if nid is None else nid.strip()
        if self._id == nid: return
        self._id = nid
        self.dirty('changing id for %s affects styles' % str(self), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('changing id for %s affects parent content' % str(self), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')

    @property
    def forId(self):
        return self._forId
    @forId.setter
    def forId(self, v):
        self._forId = v

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, v):
        self._name = v

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
        self.dirty('changing classes to %s for %s affects style' % (classes_str, str(self)), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('changing classes to %s for %s affects parent content' % (classes_str, str(self)), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def add_class(self, cls):
        assert ' ' not in cls, 'cannot add class "%s" to "%s" because it has a space in it' % (cls, self._tagName)
        if cls in self._classes: return
        self._classes.append(cls)
        self._classes_str = ' '.join(self._classes)
        self.dirty('adding class "%s" for %s affects style' % (str(cls), str(self)), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('adding class "%s" for %s affects parent content' % (cls, str(self)), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def del_class(self, cls):
        assert ' ' not in cls, 'cannot del class "%s" from "%s" because it has a space in it' % (cls, self._tagName)
        if cls not in self._classes: return
        self._classes.remove(cls)
        self._classes_str = ' '.join(self._classes)
        self.dirty('deleting class "%s" for %s affects style' % (cls, str(self)), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('deleting class "%s" for %s affects parent content' % (cls, str(self)), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')

    @property
    def pseudoclasses(self):
        return set(self._pseudoclasses)
    def clear_pseudoclass(self):
        if not self._pseudoclasses: return
        self._pseudoclasses = set()
        self.dirty('clearing psuedoclasses for %s affects style' % str(self), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('clearing psuedoclasses for %s affects parent content' % str(self), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)

        if pseudo == 'disabled':
            self.del_pseudoclass('active')
            self.del_pseudoclass('focus')
            # TODO: on_blur?
        self.dirty('adding psuedoclass %s for %s affects style' % (pseudo, str(self)), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('adding pseudoclass %s for %s affects parent content' % (pseudo, str(self)), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def del_pseudoclass(self, pseudo):
        if pseudo not in self._pseudoclasses: return
        self._pseudoclasses.discard(pseudo)

        self.dirty('deleting psuedoclass %s for %s affects style' % (pseudo, str(self)), 'style', parent=False, children=True)
        if self._parent:
            self.dirty('deleting psuedoclass %s for %s affects parent content' % (pseudo, str(self)), 'content', parent=True, children=False)
            self._parent.add_dirty_callback(self, 'style')
    def has_pseudoclass(self, pseudo):
        return pseudo in self._pseudoclasses
    @property
    def is_active(self): return 'active' in self._pseudoclasses
    @property
    def is_hovered(self): return 'hover' in self._pseudoclasses
    @property
    def is_focused(self): return 'focus' in self._pseudoclasses
    @property
    def is_disabled(self): return 'disabled' in self._pseudoclasses

    def blur(self):
        if 'focus' not in self._pseudoclasses: return
        ui_document.blur()

    @property
    def pseudoelement(self):
        return self._pseudoelement
    @pseudoelement.setter
    def pseudoelement(self, v):
        v = v or ''
        if self._pseudoelement == v: return
        self._pseudoelement = v
        self.dirty('changing psuedoelement affects style', parent=True, children=False)

    @property
    def src(self):
        if self._src_str: return self._src_str
        src = self._computed_styles.get('background-image', 'none')
        if src == 'none': src = None
        return src
    @src.setter
    def src(self, v):
        # TODO: load the resource and do something with it!!
        if self._src_str == v: return
        self._src_str = v
        self._src = None    # force reload of image
        self.dirty('changing src affects content', 'content', parent=True, children=False)

    @property
    def title(self):
        return self._title
    @title.setter
    def title(self, v):
        self._title = v
        self.dirty('title changed', parent=True, children=False)

    def reposition(self, left=None, top=None, bottom=None, right=None):
        if left is not None: self._style_left = left
        if top  is not None: self._style_top  = top
        self._absolute_pos = None
        self.update_position()
        tag_redraw_all()

    @property
    def left(self):
        l = self.style_left
        return self._relative_pos.x if self._relative_pos and l == 'auto' else l
        # return self._style_left if self._style_left is not None else self._computed_styles.get('left', 'auto')
    @left.setter
    def left(self, v):
        self.style_left = v
    @property
    def style_left(self):
        if self._style_left is not None: return self._style_left
        return self._computed_styles.get('left', 'auto')
    @style_left.setter
    def style_left(self, v):
        if self._style_left == v: return
        self._style_left = v
        self.dirty_flow()

    @property
    def top(self):
        t = self.style_top
        return self._relative_pos.y if self._relative_pos and t == 'auto' else t
        # return self._style_top if self._style_top is not None else self._computed_styles.get('top', 'auto')
    @top.setter
    def top(self, v):
        self.style_top = v
    @property
    def style_top(self):
        if self._style_top is not None: return self._style_top
        return self._computed_styles.get('top', 'auto')
    @style_top.setter
    def style_top(self, v):
        if self._style_top == v: return
        self._style_top = v
        self.dirty_flow()

    # @property
    # def top(self):
    #     return self._style_top if self._style_top is not None else self._computed_styles.get('top', 'auto')
    # @top.setter
    # def top(self, v):
    #     self._style_top = v
    #     self.dirty_flow()

    @property
    def right(self):
        return self._style_right if self._style_right is not None else self._computed_styles.get('right', 'auto')
    @right.setter
    def right(self, v):
        self._style_right = v
        self.dirty_flow()
    @property
    def style_right(self):
        if self._style_right is not None: return self._style_right
        return self._computed_styles.get('right', 'auto')
    @style_right.setter
    def style_right(self, v):
        if self._style_right == v: return
        self._style_right = v
        self.dirty_flow()

    @property
    def bottom(self):
        return self._style_bottom if self._style_bottom is not None else self._computed_styles.get('bottom', 'auto')
    @bottom.setter
    def bottom(self, v):
        self._style_bottom = v
        self.dirty_flow()
    @property
    def style_bottom(self):
        if self._style_bottom is not None: return self._style_bottom
        return self._computed_styles.get('bottom', 'auto')
    @style_bottom.setter
    def style_bottom(self, v):
        if self_style_bottom == v: return
        self._style_bottom = v
        self.dirty_flow()

    @property
    def width(self):
        w = self.style_width
        return self._absolute_size.width if self._absolute_size and w == 'auto' else w
    @width.setter
    def width(self, v):
        self.style_width = v
    @property
    def style_width(self):
        if self._style_width is not None: return self._style_width
        return self._computed_styles.get('width', 'auto')
    @style_width.setter
    def style_width(self, v):
        if self._style_width == v: return
        self._style_width = v
        self.dirty_flow()

    @property
    def height(self):
        h = self.style_height
        return self._absolute_size.height if self._absolute_size and h == 'auto' else h
    @height.setter
    def height(self, v):
        self.style_height = v
    @property
    def style_height(self):
        if self._style_height is not None: return self._style_height
        return self._computed_styles.get('height', 'auto')
    @style_height.setter
    def style_height(self, v):
        if self._style_height == v: return
        self._style_height = v
        self.dirty_flow()

    @property
    def left_pixels(self):
        if self._relative_element is None:   rew = self._parent_size.width if self._parent_size else 0
        elif self._relative_element == self: rew = self._parent_size.width
        else:                                rew = self._relative_element.width_pixels
        l = self.style_left
        if self._relative_pos and l == 'auto': l = self._relative_pos.x
        if l != 'auto':
            if type(l) is tuple:
                if   l[1] == 'px': l = l[0]
                elif l[1] == '%':  l = rew * l[0] / 100.0
        else:
            r = self.style_right
            w = self.width_pixels if self.width_pixels != 'auto' else 0
            if type(r) is tuple:
                if   r[1] == 'px': l = rew - (r[0]               + w)
                elif r[1] == '%':  l = rew - (rew * r[0] / 100.0 + w)
            elif r != 'auto':      l = rew - (r                  + w)
        return l
    @property
    def top_pixels(self):
        if self._relative_element is None:   reh = self._parent_size.height if self._parent_size else 0
        elif self._relative_element == self: reh = self._parent_size.height
        else:                                reh = self._relative_element.height_pixels
        t = self.style_top
        if self._relative_pos and t == 'auto': t = self._relative_pos.y
        if t != 'auto':
            if type(t) is tuple:
                if t[1]   == 'px': t = t[0]
                elif t[1] == '%':  t = reh * t[0] / 100.0
        else:
            b = self.style_bottom
            h = self.height_pixels if self.height_pixels != 'auto' else 0
            if type(b) is tuple:
                if   b[1] == 'px': t = (b[0]               + h) # - reh
                elif b[1] == '%':  t = (reh * b[0] / 100.0 + h) # - reh
            elif b != 'auto':      t = (b                  + h) # - reh
        return t
    @property
    def width_pixels(self):
        w = self.style_width
        if self._absolute_size and w == 'auto': w = self._absolute_size.width
        if type(w) is tuple:
            if w[1] == 'px': w = w[0]
            elif w[1] == '%':
                if self._relative_element == self:
                    rew = self._parent_size.width
                elif self._relative_element is None:
                    rew = 0
                else:
                    rew = self._relative_element.width_pixels
                w = rew * w[0] / 100.0
        return w
    @property
    def height_pixels(self):
        h = self.style_height
        if self._absolute_size and h == 'auto': h = self._absolute_size.height
        if type(h) is tuple:
            if h[1] == 'px': h = h[0]
            elif h[1] == '%':
                if self._relative_element == self:
                    reh = self._parent_size.height
                elif self._relative_element is None:
                    reh = 0
                else:
                    reh = self._relative_element.height_pixels
                h = reh * h[0] / 100.0
        return h




    @property
    def scrollTop(self):
        # TODO: clamp value?
        return self._scroll_offset.y
    @scrollTop.setter
    def scrollTop(self, v):
        if not self._is_scrollable_y: v = 0
        v = min(v, self._dynamic_content_size.height - self._absolute_size.height + self._mbp_height)
        v = max(v, 0)
        self._scroll_offset.y = v
        tag_redraw_all()

    @property
    def scrollLeft(self):
        # TODO: clamp value?
        return -self._scroll_offset.x    # negated so that positive values of scrollLeft scroll content left
    @scrollLeft.setter
    def scrollLeft(self, v):
        # TODO: clamp value?
        if not self._is_scrollable_x: v = 0
        v = min(v, self._dynamic_content_size.width - self._absolute_size.width + self._mbp_width)
        v = max(v, 0)
        v = -v
        self._scroll_offset.x = v
        tag_redraw_all()

    @property
    def is_visible(self):
        # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!
        if self._is_visible is None: return self._computed_styles.get('display', 'auto') != 'none'
        return self._is_visible
    @is_visible.setter
    def is_visible(self, v):
        self._is_visible = v
        self.dirty('changing visibility can affect style', 'style', children=True)

    @property
    def is_scrollable(self):
        return self._is_scrollable_x or self._is_scrollable_y
    @property
    def is_scrollable_x(self):
        return self._is_scrollable_x
    @property
    def is_scrollable_y(self):
        return self._is_scrollable_y

    def get_visible_children(self):
        # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!
        # NOTE: returns list of children without `display:none` style.
        #       does _NOT_ mean that the child is going to be drawn
        #       (might still be clipped with scissor or `visibility:hidden` style)
        return [child for child in self._children if child.is_visible]

    @property
    def content_width(self):
        return self._static_content_size.width
    @property
    def content_height(self):
        return self._static_content_size.height

    @property
    def type(self):
        return self._type
    @type.setter
    def type(self, v):
        self._type = v
        self.dirty('Changing type can affect style', 'style', children=True)
        self.dirty_styling()

    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, v):
        if self._value == v: return
        self._value = v
        self.dispatch_event('on_input')
        self.dirty('Changing value can affect style and content')
        #self.dirty_styling()

    @property
    def checked(self):
        return self._checked
    @checked.setter
    def checked(self, v):
        v = "checked" if v else None
        if self._checked == v: return
        self._checked = v
        self.dispatch_event('on_input')
        self.dirty('Changing checked can affect style and content', 'style', children=True)
        #self.dirty_styling()

    @property
    def preclean(self):
        return self._preclean
    @preclean.setter
    def preclean(self, fn):
        self._preclean = fn

    @property
    def postclean(self):
        return self._postclean
    @postclean.setter
    def postclean(self, fn):
        self._postclean = fn

    @property
    def postflow(self):
        return self._postflow
    @postflow.setter
    def postflow(self, fn):
        self._postflow = fn

    @property
    def can_focus(self): return self._can_focus
    @can_focus.setter
    def can_focus(self, v): self._can_focus = v



class UI_Element_Dirtiness:
    def dirty(self, cause=None, properties=None, parent=True, children=False):
        if cause is None: cause = 'Unknown cause'
        parent &= self._parent is not None
        if properties is None: properties = set(UI_Element_Utils._cleaning_graph_nodes)
        elif type(properties) is str: properties = {properties}
        elif type(properties) is list: properties = set(properties)
        self._dirty_properties |= properties
        self._dirty_causes.append(cause)
        if parent: self._dirty_propagation['parent'] |= properties
        if children: self._dirty_propagation['children'] |= properties
        self.propagate_dirtiness()
        # print('%s had %s dirtied, because %s' % (str(self), str(properties), str(cause)))
        tag_redraw_all()

    def dirty_styling(self):
        self._computed_styles = {}
        self._styling_default = None
        self._styling_parent = None
        self._styling_custom = None
        for child in self._children_all: child.dirty_styling()
        if self._parent is None:
            self.dirty('Dirtying style cache', children=True)
        tag_redraw_all()

    def add_dirty_callback(self, child, properties):
        if type(properties) is str: properties = [properties]
        for p in properties:
            if p not in self._dirty_callbacks:
                self._dirty_callbacks[p] = set()
            self._dirty_callbacks[p].add(child)
        if self._parent: self._parent.add_dirty_callback(self, properties)

    def dirty_flow(self, parent=True, children=True):
        if self._dirty_flow: return
        self._dirty_flow = True
        if parent and self._parent:
            self._parent.dirty_flow()
        if children:
            for child in self._children_all:
                child.dirty_flow()
        tag_redraw_all()

    @property
    def is_dirty(self):
        return bool(self._dirty_properties) or bool(self._dirty_propagation['parent']) or bool(self._dirty_propagation['children'])

    def propagate_dirtiness(self):
        if self._dirty_propagation['defer']: return
        if self._dirty_propagation['parent']:
            if self._parent:
                cause = ' -> '.join('%s'%cause for cause in (self._dirty_causes+[
                    '"propagating dirtiness (%s) from %s to parent %s"' % (str(self._dirty_propagation['parent']), str(self), str(self._parent))
                ]))
                self._parent.dirty(
                    cause=cause,
                    properties=self._dirty_propagation['parent'],
                    parent=True,
                    children=False,
                )
            self._dirty_propagation['parent'].clear()
        if self._dirty_propagation['children']:
            # no need to dirty ::before, ::after, or text, because they will be reconstructed
            for child in self._children_all:
                cause = ' -> '.join('%s'%cause for cause in (self._dirty_causes+[
                    '"propagating dirtiness (%s) from %s to child %s"' % (str(self._dirty_propagation['children']), str(self), str(child)),
                ]))
                child.dirty(
                    cause=cause,
                    properties=self._dirty_propagation['children'],
                    parent=False,
                    children=True,
                )
            self._dirty_propagation['children'].clear()
        self._dirty_causes = []

    @property
    def defer_dirty_propagation(self):
        return self._dirty_propagation['defer']
    @defer_dirty_propagation.setter
    def defer_dirty_propagation(self, v):
        self._dirty_propagation['defer'] = bool(v)
        self.propagate_dirtiness()

    def _call_preclean(self):
        if self.is_dirty and self._preclean: self._preclean()
        for child in self._children_all: child._call_preclean()
    def _call_postclean(self):
        if self._was_dirty and self._postclean: self._postclean()
        for child in self._children_all: child._call_postclean()
    def _call_postflow(self):
        if self._postflow: self._postflow()
        for child in self._children_all: child._call_postflow()
    def clean(self, depth=0):
        '''
        No need to clean if
        - already clean,
        - possibly more dirtiness to propagate,
        - if deferring cleaning.
        '''
        self._was_dirty = self.is_dirty
        self._call_preclean()
        if not self.is_dirty or self._defer_clean: return
        self.call_cleaning_callbacks()
        for child in self._children_all: child.clean(depth=depth+1)
        self._call_postclean()
        assert not self.is_dirty, '%s is still dirty after cleaning: %s' % (str(self), str(self._dirty_properties))


class UI_Element(UI_Element_Utils, UI_Element_Properties, UI_Element_Dirtiness):
    def __init__(self, **kwargs):
        ################################################################
        # attributes of UI_Element that are settable
        # set to blank defaults, will be set again later in __init__()
        self._tagName       = ''        # determines type of UI element
        self._id            = ''        # unique identifier
        self._classes_str   = ''        # list of classes (space delimited string)
        self._style_str     = ''        # custom style string
        self._innerText     = ''        # text to display (converted to UI_Elements)
        self._src_str       = None      # path to resource, such as image
        self._can_focus     = False     # True:self can take focus
        self._title         = None      # tooltip
        self._forId         = None      # used for labels

        # attribs
        self._type          = None
        self._value         = None
        self._checked       = None
        self._name          = None

        self._was_dirty = False
        self._preclean      = None      # fn that's called back right before clean is started
        self._postclean     = None      # fn that's called back right after clean is done
        self._postflow      = None      # fn that's called back right after layout is done

        #################################################################
        # read-only attributes of UI_Element
        self._parent        = None      # read-only property; set in parent.append_child(child)
        self._children      = []        # read-only list of all children; append_child, delete_child, clear_children
        self._pseudoclasses = set()     # TODO: should order matter here? (make list)
                                        # updated by main ui system (hover, active, focus)
        self._pseudoelement = ''        # set only if element is a pseudoelement ('::before' or '::after')

        self._style_left    = None
        self._style_top     = None
        self._style_right   = None
        self._style_bottom  = None
        self._style_width   = None
        self._style_height  = None

        #################################################################################
        # boxes for viewing (wrt blender region) and content (wrt view)
        # NOTE: content box is larger than viewing => scrolling, which is
        #       managed by offsetting the content box up (y+1) or left (x-1)
        self._static_content_size  = None       # size of static content (text, image, etc.) w/o margin,border,padding
        self._static_content_space = 0          # horizontal space between text elements
        self._dynamic_content_size = None       # size of dynamic content (static or wrapped children) w/o mbp
        self._dynamic_full_size    = None       # size of dynamic content with mbp added
        self._mbp_width            = None
        self._mbp_height           = None
        self._relative_element     = None
        self._relative_pos         = None
        self._relative_offset      = None
        self._scroll_offset        = Vec2D((0,0))
        self._absolute_pos         = None       # abs pos of element from relative info; cached in draw
        self._absolute_size        = None       # viewing size of element; set by parent

        self._viewing_box = Box2D(topleft=(0,0), size=(-1,-1))  # topleft+size: set by parent element
        self._inside_box  = Box2D(topleft=(0,0), size=(-1,-1))  # inside area of viewing box (less margins, paddings, borders)
        self._content_box = Box2D(topleft=(0,0), size=(-1,-1))  # topleft: set by scrollLeft, scrollTop properties
                                                                # size: determined from children and style

        ##################################################################################
        # all events with their respective callbacks
        # NOTE: values of self._events are list of tuples, where:
        #       - first item is bool indicating type of callback, where True=capturing and False=bubbling
        #       - second item is the callback function, possibly wrapped with lambda
        #       - third item is the original callback function
        self._events = {
            'on_focus':         [],     # focus is gained (:foces is added)
            'on_blur':          [],     # focus is lost (:focus is removed)
            'on_keydown':       [],     # key is pressed down
            'on_keyup':         [],     # key is released
            'on_keypress':      [],     # key is entered (down+up)
            'on_mouseenter':    [],     # mouse enters self (:hover is added)
            'on_mousemove':     [],     # mouse moves over self
            'on_mousedown':     [],     # mouse button is pressed down
            'on_mouseup':       [],     # mouse button is released
            'on_mouseclick':    [],     # mouse button is clicked (down+up while remaining on self)
            'on_mousedblclick': [],     # mouse button is pressed twice in quick succession
            'on_mouseleave':    [],     # mouse leaves self (:hover is removed)
            'on_scroll':        [],     # self is being scrolled
            'on_input':         [],     # occurs immediately after value has changed
        }

        ####################################################################
        # cached properties
        # TODO: go back through these to make sure we've caught everything
        self._classes          = []     # classes applied to element, set by self.classes property, based on self._classes_str
        self._computed_styles  = {}     # computed style UI_Style after applying all styling
        self._is_visible       = None   # indicates if self is visible, set in compute_style(), based on self._computed_styles
        self._is_scrollable_x  = False  # indicates is self is scrollable along x, set in compute_style(), based on self._computed_styles
        self._is_scrollable_y  = False  # indicates is self is scrollable along y, set in compute_style(), based on self._computed_styles
        self._static_content_size     = None   # min and max size of content, determined from children and style
        self._children_text    = []     # innerText as children
        self._child_before     = None   # ::before child
        self._child_after      = None   # ::after child
        self._children_all     = []     # all children in order
        self._innerTextWrapped = None   # <--- no longer needed?
        self._selector         = None   # full selector of self, built in compute_style()
        self._selector_before  = None   # full selector of ::before pseudoelement for self
        self._selector_after   = None   # full selector of ::after pseudoelement for self
        self._styling_default  = None   # default styling for element (depends on tagName)
        self._styling_custom   = None   #
        self._styling_parent   = None
        self._innerTextAsIs    = None   # text to display as-is (no wrapping)
        self._src              = None
        self._textwrap_opts    = {}
        self._l, self._t, self._w, self._h = 0,0,0,0    # scissor position

        ####################################################
        # dirty properties
        # used to inform parent and children to recompute
        self._dirty_properties = {              # set of dirty properties, add through self.dirty to force propagation of dirtiness
            'style',                            # force recalculations of style
            'content',                          # content of self has changed
            'blocks',                           # children are grouped into blocks
            'size',                             # force recalculations of size
        }
        self._dirty_flow = True
        self._dirty_causes = []
        self._dirty_callbacks = {}
        self._dirty_propagation = {             # contains deferred dirty propagation for parent and children; parent will be dirtied later
            'defer':    False,                  # set to True to defer dirty propagation (useful when many changes are occurring)
            'parent':   set(),                  # set of properties to dirty for parent
            'children': set(),                  # set of properties to dirty for children
        }
        self._defer_clean = False               # set to True to defer cleaning (useful when many changes are occurring)


        ########################################################
        # TODO: REPLACE WITH BETTER PROPERTIES AND DELETE!!
        self._preferred_width, self._preferred_height = 0,0
        self._content_width, self._content_height = 0,0
        # various sizes and boxes (set in self._position), used for layout and drawing
        self._preferred_size = Size2D()                         # computed preferred size, set in self._layout, used as suggestion to parent
        self._pref_content_size = Size2D()                      # size of content
        self._pref_full_size = Size2D()                         # _pref_content_size + margins + border + padding
        self._box_draw = Box2D(topleft=(0,0), size=(-1,-1))     # where UI will be drawn (restricted by parent)
        self._box_full = Box2D(topleft=(0,0), size=(-1,-1))     # where UI would draw if not restricted (offset for scrolling)


        ###################################################
        # start setting properties
        # NOTE: some properties require special handling
        self._defer_clean = True
        for (k,v) in kwargs.items():
            if k in self._events:
                # key is an event; set callback
                self.add_eventListener(k, v)
            elif k == 'parent':
                # note: parent.append_child(self) will set self._parent
                v.append_child(self)
            elif k == '_parent':
                self._parent = v
            elif k == 'children':
                # append each child
                for child in kwargs['children']:
                    self.append_child(child)
            elif hasattr(self, k):
                # need to test that a setter exists for the property
                class_attr = getattr(type(self), k, None)
                if type(class_attr) is property:
                    # k is a property
                    assert class_attr.fset is not None, 'Attempting to set a read-only property %s to "%s"' % (k, str(v))
                    setattr(self, k, v)
                else:
                    # k is an attribute
                    print('Setting non-property attribute %s to "%s"' % (k, str(v)))
                    setattr(self, k, v)
            else:
                print('Unhandled pair (%s,%s)' % (k,str(v)))
        self._defer_clean = False
        self.dirty('initially dirty')

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        info = ['tagName', 'id', 'classes', 'type', 'innerText', 'innerTextAsIs']
        info = [(k, getattr(self, k)) for k in info if hasattr(self, k)]
        info = ['%s="%s"' % (k, str(v)) for k,v in info if v]
        if self.is_dirty: info += ['dirty']
        return '<UI_Element %s>' % ' '.join(info)

    @UI_Element_Utils.add_cleaning_callback('style', {'size', 'content'})
    def _compute_style(self):
        '''
        rebuilds self._selector and computes the stylesheet, propagating computation to children
        '''
        if self._defer_clean: return
        if 'style' not in self._dirty_properties:
            for e in self._dirty_callbacks.get('style', []): e._compute_style()
            self._dirty_callbacks['style'] = set()
            return

        self.defer_dirty_propagation = True

        # rebuild up full selector
        sel_parent = [] if not self._parent else self._parent._selector
        if self._pseudoelement:
            # this is either a ::before or ::after pseudoelement
            self._selector = sel_parent[:-1] + [sel_parent[-1] + '::' + self._pseudoelement]
            self._selector_before = None
            self._selector_after  = None
        elif self._innerTextAsIs:
            # this is a text element
            self._selector = sel_parent + ['*text*']
            self._selector_before = None
            self._selector_after = None
        else:
            attribs = ['type', 'value', 'checked']
            sel_tagName = self._tagName
            sel_id = '#%s' % self._id if self._id else ''
            sel_cls = ''.join('.%s' % c for c in self._classes)
            sel_pseudo = ''.join(':%s' % p for p in self._pseudoclasses)
            sel_attribs = ''.join('[%s]' % p for p in attribs if getattr(self,p) is not None)
            sel_attribvals = ''.join('[%s="%s"]' % (p,str(getattr(self,p))) for p in attribs if getattr(self,p) is not None)
            self._selector = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo + sel_attribs + sel_attribvals]
            self._selector_before = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo + '::before']
            self._selector_after  = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo + '::after']

        # initialize styles in order: default, focus, active, hover, hover+active
        # TODO: inherit parent styles with other elements (not just *text*)
        if self._styling_parent is None:
            if self._parent:
                # keep = {
                #     'font-family', 'font-style', 'font-weight', 'font-size',
                #     'color',
                # }
                # decllist = {k:v for (k,v) in self._parent._computed_styles.items() if k in keep}
                # self._styling_parent = UI_Styling.from_decllist(decllist)
                self._styling_parent = UI_Styling()
            else:
                self._styling_parent = UI_Styling()

        # computed default styling
        if self._styling_default is None:
            if self._innerTextAsIs is not None:
                self._styling_default = UI_Styling()
            else:
                self._styling_default = ui_defaultstylings

        # # compute custom styles
        if self._styling_custom is None:
            self._styling_custom = UI_Styling('*{%s;}' % self._style_str)

        styling_list = [self._styling_parent, self._styling_default, ui_draw.stylesheet, self._styling_custom]
        self._computed_styles = UI_Styling.compute_style(self._selector, *styling_list)

        if self._is_visible and not self._pseudoelement:
            # need to compute ::before and ::after styles to know whether there is content to compute and render
            self._computed_styles_before = UI_Styling.compute_style(self._selector_before, *styling_list)
            self._computed_styles_after  = UI_Styling.compute_style(self._selector_after,  *styling_list)
        else:
            self._computed_styles_before = None
            self._computed_styles_after = None
        self._is_scrollable_x = (self._computed_styles.get('overflow-x', 'visible') == 'scroll')
        self._is_scrollable_y = (self._computed_styles.get('overflow-y', 'visible') == 'scroll')

        fontfamily = self._computed_styles.get('font-family', 'sans-serif')
        fontstyle = self._computed_styles.get('font-style', 'normal')
        fontweight = self._computed_styles.get('font-weight', 'normal')
        self._fontid = get_font(fontfamily, fontstyle, fontweight)
        self._fontsize = float(self._computed_styles.get('font-size', (12,''))[0])
        self._fontcolor = self._computed_styles.get('color', (0,0,0,1))

        self._whitespace = self._computed_styles.get('white-space', 'normal')

        self._src = None

        # tell children to recompute selector
        # NOTE: self._children_all has not been constructed, yet!
        for child in self._children: child._compute_style()
        for child in self._children_text: child._compute_style()
        if self._child_before: self._child_before._compute_styles()
        if self._child_after: self._child_after._compute_styles()

        self.dirty('style change might have changed content (::before / ::after)', 'content')
        self.dirty('style change might have changed size', 'size')
        self.dirty_flow()
        self._dirty_properties.discard('style')
        self._dirty_callbacks['style'] = set()

        self.defer_dirty_propagation = False

    @UI_Element_Utils.add_cleaning_callback('content', {'blocks'})
    def _compute_content(self):
        if self._defer_clean: return
        if not self.is_visible:
            self._dirty_properties.discard('content')
            return
        if 'content' not in self._dirty_properties:
            for e in self._dirty_callbacks.get('content', []): e._compute_content()
            self._dirty_callbacks['content'] = set()
            return

        self.defer_dirty_propagation = True

        if self._computed_styles_before and self._computed_styles_before.get('content', ''):
            # TODO: cache this!!
            self._child_before = UI_Element(tagName=self._tagName, pseudoelement='before', _parent=self)
            self._child_before.clean()
        else:
            self._child_before = None

        if self._computed_styles_after and self._computed_styles_after.get('content', ''):
            # TODO: cache this!!
            self._child_after = UI_Element(tagName=self._tagName, pseudoelement='after', _parent=self)
            self._child_after.clean()
        else:
            self._child_after = None

        if self._src and not self.src:
            self._src = None

        if self._innerText:
            # TODO: cache this!!
            textwrap_opts = {
                'text':              self._innerText,
                'fontid':            self._fontid,
                'fontsize':          self._fontsize,
                'preserve_newlines': self._whitespace in {'pre', 'pre-line', 'pre-wrap'},
                'collapse_spaces':   self._whitespace in {'normal', 'nowrap', 'pre-line'},
                'wrap_text':         self._whitespace in {'normal', 'pre-wrap', 'pre-line'},
            }
            # TODO: if whitespace:pre, then make self NOT wrap
            innerTextWrapped = helper_wraptext(**textwrap_opts)
            rewrap = False
            rewrap |= self._innerTextWrapped != innerTextWrapped
            rewrap |= any(textwrap_opts[k] != self._textwrap_opts.get(k,None) for k in textwrap_opts.keys())
            if rewrap:
                self._textwrap_opts = textwrap_opts
                self._innerTextWrapped = innerTextWrapped
                self._children_text = []
                self._text_map = []
                idx = 0
                for l in self._innerTextWrapped.splitlines():
                    if self._children_text:
                        ui_br = UI_Element(tagName='br', _parent=self)
                        self._children_text.append(ui_br)
                        self._text_map.append({
                            'ui_element': ui_br,
                            'idx': idx,
                            'offset': 0,
                            'char': '\n',
                            'pre': '',
                        })
                        idx += 1
                    words = re.split(r'( +)', l)
                    for word in words:
                        ui_word = UI_Element(innerTextAsIs=word, _parent=self)
                        self._children_text.append(ui_word)
                        for i in range(len(word)):
                            self._text_map.append({
                                'ui_element': ui_word,
                                'idx': idx,
                                'offset': i,
                                'char': word[i],
                                'pre': word[:i],
                            })
                        idx += len(word)
                ui_end = UI_Element(innerTextAsIs='', _parent=self)
                self._children_text.append(ui_end)
                self._text_map.append({
                    'ui_element': ui_end,
                    'idx': idx,
                    'offset': 0,
                    'char': '',
                    'pre': '',
                })
                self._children_text_min_size = Size2D(width=0, height=0)
                for child in self._children_text:
                    child.clean()
                    self._children_text_min_size.width  = max(self._children_text_min_size.width,  child._static_content_size.width)
                    self._children_text_min_size.height = max(self._children_text_min_size.height, child._static_content_size.height)

        elif self.src and not self._src:
            image = load_image_png(self.src)
            self._image_height,self._image_width,self._image_depth = len(image),len(image[0]),len(image[0][0])
            assert self._image_depth == 4
            self._image_flat = [d for r in image for c in r for d in c]
            self._src = 'image'

            self._image_texbuffer = bgl.Buffer(bgl.GL_INT, [1])
            bgl.glGenTextures(1, self._image_texbuffer)
            self._image_textureid = self._image_texbuffer[0]
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._image_textureid)
            # bgl.glTexEnv(bgl.GL_TEXTURE_ENV, bgl.GL_TEXTURE_ENV_MODE, bgl.GL_MODULATE)
            bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_NEAREST)
            bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
            # texbuffer = bgl.Buffer(bgl.GL_BYTE, [self.width,self.height,self.depth], image_data)
            image_size = self._image_width * self._image_height * self._image_depth
            texbuffer = bgl.Buffer(bgl.GL_BYTE, [image_size], self._image_flat)
            bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, self._image_width, self._image_height, 0, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, texbuffer)
            del texbuffer
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)

            self._children_text = []
            self._children_text_min_size = None
            self._innerTextWrapped = None

        else:
            self._children_text = []
            self._children_text_min_size = None
            self._innerTextWrapped = None

        # collect all children indo self._children_all
        # TODO: cache this!!
        # TODO: some children are "detached" from self (act as if child.parent==root or as if floating)
        self._children_all = []
        if self._child_before:  self._children_all.append(self._child_before)
        if self._children_text: self._children_all += self._children_text
        if self._children:      self._children_all += self._children
        if self._child_after:   self._children_all.append(self._child_after)

        for child in self._children_all: child._compute_content()

        # content changes might have changed size
        self.dirty('content changes might have affected blocks', 'blocks')
        self.dirty_flow()
        self._dirty_properties.discard('content')
        self._dirty_callbacks['content'] = set()

        self.defer_dirty_propagation = False

    def get_text_pos(self, index):
        if self._innerText is None: return None
        index = clamp(index, 0, len(self._text_map))
        m = self._text_map[index]
        e = m['ui_element']
        idx = m['idx']
        offset = m['offset']
        pre = m['pre']
        size_prev = Globals.drawing.set_font_size(self._fontsize, fontid=self._fontid, force=True)
        tw = Globals.drawing.get_text_width(pre)
        # th = Globals.drawing.get_line_height(pre)
        Globals.drawing.set_font_size(size_prev, fontid=self._fontid, force=True)
        #print(index, m, e._relative_pos, e._relative_offset, e._scroll_offset, tw)
        e_pos = e._relative_pos + e._relative_offset + e._scroll_offset + RelPoint2D((tw, 0))
        return e_pos

    @UI_Element_Utils.add_cleaning_callback('blocks', {'size'})
    def _compute_blocks(self):
        # split up all children into layout blocks

        if self._defer_clean: return
        if not self.is_visible:
            self._dirty_properties.discard('blocks')
            return
        if 'blocks' not in self._dirty_properties:
            for e in self._dirty_callbacks.get('blocks', []): e._compute_blocks()
            self._dirty_callbacks['blocks'] = set()
            return

        self.defer_dirty_propagation = True

        if self._computed_styles.get('display', 'inline') == 'flexbox':
            # all children are treated as flex blocks, regardless of their display
            pass
        else:
            # collect children into blocks
            self._blocks = []
            blocked_inlines = None
            for child in self._children_all:
                d = child._computed_styles.get('display', 'inline')
                if d == 'inline':
                    if not blocked_inlines:
                        blocked_inlines = []
                        self._blocks.append(blocked_inlines)
                    blocked_inlines.append(child)
                else:
                    self._blocks.append([child])
                    blocked_inlines = None

        for child in self._children_all:
            child._compute_blocks()

        # content changes might have changed size
        self.dirty('block changes might have changed size', 'size')
        self.dirty_flow()
        self._dirty_properties.discard('blocks')
        self._dirty_callbacks['blocks'] = set()

        self.defer_dirty_propagation = False

    ################################################################################################
    # NOTE: COMPUTE STATIC CONTENT SIZE (TEXT, IMAGE, ETC.), NOT INCLUDING MARGIN, BORDER, PADDING
    #       WE MIGHT NOT NEED TO COMPUTE MIN AND MAX??
    @UI_Element_Utils.add_cleaning_callback('size')
    def _compute_static_content_size(self):
        if self._defer_clean: return
        if not self.is_visible:
            self._dirty_properties.discard('size')
            return
        if 'size' not in self._dirty_properties:
            for e in self._dirty_callbacks.get('size', []): e._compute_static_content_size()
            self._dirty_callbacks['size'] = set()
            return

        self.defer_dirty_propagation = True

        for child in self._children_all:
            child._compute_static_content_size()

        self._static_content_size = None

        # set size based on content (computed size)
        if self._innerTextAsIs is not None:
            # TODO: allow word breaking?
            # size_prev = Globals.drawing.set_font_size(self._textwrap_opts['fontsize'], fontid=self._textwrap_opts['fontid'], force=True)
            size_prev = Globals.drawing.set_font_size(self._parent._fontsize, fontid=self._parent._fontid, force=True)
            self._static_content_size = Size2D()
            self._static_content_size.set_all_widths(Globals.drawing.get_text_width(self._innerTextAsIs)+1)
            self._static_content_size.set_all_heights(Globals.drawing.get_line_height(self._innerTextAsIs))
            self._static_content_space = Globals.drawing.get_text_width(' ')
            # Globals.drawing.set_font_size(size_prev, fontid=self._textwrap_opts['fontid'], force=True)
            Globals.drawing.set_font_size(size_prev, fontid=self._parent._fontid, force=True)

        elif self._src == 'image':
            # TODO: set to image size?
            dpi_mult = Globals.drawing.get_dpi_mult()
            self._static_content_size = Size2D()
            self._static_content_size.set_all_widths(self._image_width * dpi_mult)
            self._static_content_size.set_all_heights(self._image_height * dpi_mult)
            self._static_content_space = 0
            pass

        else:
            pass

        self._dirty_properties.discard('size')
        self.dirty_flow()
        self._dirty_callbacks['size'] = set()
        self.defer_dirty_propagation = False

    def layout(self, **kwargs):
        # layout each block into lines.  if a content box of child element is too wide to fit in line and
        # child is not only element on the current line, then end current line, start a new line, relayout the child.
        # this function does not set the final position and size for element.

        # through this function, we are calculating and committing to a certain width and height
        # although the parent element might give us something different.  if we end up with a
        # different width and height in self.position() below, we will need to improvise by
        # adjusting margin (if bigger) or using scrolling (if smaller)

        # TODO: allow for horizontal growth rather than biasing for vertical
        # TODO: handle other types of layouts (ex: table, flex)
        # TODO: allow for different line alignments (top for now; bottom, baseline)
        # TODO: percent_of (style width, height, etc.) could be of last non-static element or document
        # TODO: position based on bottom-right,etc.

        # NOTE: parent ultimately controls layout and viewing area of child, but uses this layout function to "ask"
        #       child how much space it would like

        # given size might by inf. given can be ignored due to style. constraints applied at end.
        # positioning (with definitive size) should happen

        if not self.is_visible: return

        first_on_line  = kwargs['first_on_line']    # is self the first UI_Element on the current line?
        fitting_size   = kwargs['fitting_size']     # size from parent that we should try to fit in (only max)
        fitting_pos    = kwargs['fitting_pos']      # top-left position wrt parent where we go if not absolute or fixed
        parent_size    = kwargs['parent_size']      # size of inside of parent
        nonstatic_elem = kwargs['nonstatic_elem']   # last non-static element
        document_elem  = kwargs['document_elem']    # whole document element (root)

        styles       = self._computed_styles
        style_pos    = styles.get('position', 'static')

        self._fitting_pos = fitting_pos
        self._fitting_size = fitting_size
        self._parent_size = parent_size
        self._absolute_pos = None
        self._content_offset = 0 #if not self._static_content_size or first_on_line else self._static_content_space
        self._document_elem = document_elem
        self._nonstatic_elem = nonstatic_elem

        self.update_position()

        if not self._dirty_flow: return

        dpi_mult      = Globals.drawing.get_dpi_mult()
        display       = styles.get('display', 'block')
        is_nonstatic  = style_pos in {'absolute','relative','fixed','sticky'}
        is_contribute = style_pos not in {'absolute', 'fixed'}
        next_nonstatic_elem = self if is_nonstatic else nonstatic_elem
        parent_width  = parent_size.get_width_midmaxmin()  or 0
        parent_height = parent_size.get_height_midmaxmin() or 0
        width         = self._get_style_num('width',      'auto', percent_of=parent_width,  scale=dpi_mult, override_v=self._style_width)   # could be 'auto'
        height        = self._get_style_num('height',     'auto', percent_of=parent_height, scale=dpi_mult, override_v=self._style_height)  # could be 'auto'
        min_width     = self._get_style_num('min-width',  'auto', percent_of=parent_width,  scale=dpi_mult)     # could be 'auto'
        min_height    = self._get_style_num('min-height', 'auto', percent_of=parent_height, scale=dpi_mult)     # could be 'auto'
        max_width     = self._get_style_num('max-width',  'auto', percent_of=parent_width,  scale=dpi_mult)     # could be 'auto'
        max_height    = self._get_style_num('max-height', 'auto', percent_of=parent_height, scale=dpi_mult)     # could be 'auto'
        overflow_x   = styles.get('overflow-x', 'visible')
        overflow_y   = styles.get('overflow-y', 'visible')

        border_width  = self._get_style_num('border-width', 0, scale=dpi_mult)
        margin_top,  margin_right,  margin_bottom,  margin_left  = self._get_style_trbl('margin',  scale=dpi_mult)
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding', scale=dpi_mult)
        mbp_left   = (margin_left    + border_width + padding_left)
        mbp_right  = (padding_right  + border_width + margin_right)
        mbp_top    = (margin_top     + border_width + padding_top)
        mbp_bottom = (padding_bottom + border_width + margin_bottom)
        mbp_width  = mbp_left + mbp_right
        mbp_height = mbp_top  + mbp_bottom

        self._mbp_left = mbp_left
        self._mbp_top = mbp_top
        self._mbp_right = mbp_right
        self._mbp_bottom = mbp_bottom
        self._mbp_width = mbp_width
        self._mbp_height = mbp_height

        self._computed_min_width  = min_width  # self._get_style_num('min-width',  'auto', percent_of=parent_width,  scale=dpi_mult) # could be 'auto'
        self._computed_min_height = min_height # self._get_style_num('min-height', 'auto', percent_of=parent_height, scale=dpi_mult) # could be 'auto'
        self._computed_max_width  = max_width  # self._get_style_num('max-width',  'auto', percent_of=parent_width,  scale=dpi_mult) # could be 'auto'
        self._computed_max_height = max_height # self._get_style_num('max-height', 'auto', percent_of=parent_height, scale=dpi_mult) # could be 'auto'

        if self._static_content_size:
            # self has static content size
            dw = self._static_content_size.width # + (0 if first_on_line else self._static_content_space)
            dh = self._static_content_size.height

        else:
            # self has no static content, so flow and size is determined from children
            # note: will keep track of accumulated size and possibly update inside size as needed
            # note: style size overrides passed fitting size
            inside_size = Size2D()
            if fitting_size.max_width  is not None: inside_size.max_width  = max(0, fitting_size.max_width  - mbp_width)
            if fitting_size.max_height is not None: inside_size.max_height = max(0, fitting_size.max_height - mbp_height)
            if width      != 'auto': inside_size.width      = max(0, width      - mbp_width)
            if height     != 'auto': inside_size.height     = max(0, height     - mbp_height)
            if max_width  != 'auto': inside_size.max_width  = max(0, max_width  - mbp_width)
            if max_height != 'auto': inside_size.max_height = max(0, max_height - mbp_height)
            if min_width  != 'auto': inside_size.min_width  = max(0, min_width  - mbp_width)
            if min_height != 'auto': inside_size.min_height = max(0, min_height - mbp_height)

            if self._innerText and self._whitespace in {'nowrap', 'pre'}:
                inside_size.min_width = inside_size.width = inside_size.max_width = float('inf')

            lines = []
            accum_width  = 0    # max width for all lines
            accum_height = 0    # sum heights for all lines
            for block in self._blocks:
                # each block might be wrapped onto multiple lines
                cur_line = []
                line_width = 0
                line_height = 0
                for element in block:
                    if not element.is_visible: continue
                    position = element._computed_styles.get('position', 'static')
                    c = position not in {'absolute', 'fixed'}
                    sx = element._computed_styles.get('overflow-x', 'visible')
                    sy = element._computed_styles.get('overflow-y', 'visible')
                    processed = False
                    while not processed:
                        first_child = not cur_line
                        rw = (inside_size.width  if inside_size.width  is not None else (inside_size.max_width  if inside_size.max_width  is not None else float('inf'))) - line_width
                        rh = (inside_size.height if inside_size.height is not None else (inside_size.max_height if inside_size.max_height is not None else float('inf'))) - accum_height
                        # rw = float('inf') if inside_size.max_width  is None else (inside_size.max_width  - line_width)
                        # rh = float('inf') if inside_size.max_height is None else (inside_size.max_height - accum_height)
                        if overflow_y in {'scroll','auto'}: rh = float('inf')
                        remaining = Size2D(max_width=rw, max_height=rh)
                        pos = Point2D((mbp_left + line_width, -(mbp_top + accum_height)))
                        element.layout(
                            first_on_line=first_child,
                            fitting_size=remaining,
                            fitting_pos=pos,
                            parent_size=inside_size,
                            nonstatic_elem=next_nonstatic_elem,
                            document_elem=document_elem
                        )
                        w = element._dynamic_full_size.width
                        h = element._dynamic_full_size.height
                        is_good = False
                        is_good |= first_child                  # always add child to an empty line
                        is_good |= c and w<=rw and h<=rh        # child fits on current line
                        is_good |= not c                        # child does not contribute to our size
                        if is_good:
                            if c: cur_line.append(element)
                            # clamp width and height only if scrolling (respectively)
                            if sx == 'scroll': w = remaining.clamp_width(w)
                            if sy == 'scroll': h = remaining.clamp_height(h)
                            sz = Size2D(width=w, height=h)
                            element.set_view_size(sz)
                            line_width += w
                            line_height = max(line_height, h)
                            processed = True
                        else:
                            # element does not fit!  finish of current line, then reprocess current element
                            lines.append(cur_line)
                            accum_height += line_height
                            accum_width = max(accum_width, line_width)
                            cur_line = []
                            line_width = 0
                            line_height = 0
                            element.dirty_flow(parent=False, children=True)
                            #element._dirty_flow = True
                if cur_line:
                    lines.append(cur_line)
                    accum_height += line_height
                    accum_width = max(accum_width, line_width)
            dw = accum_width
            dh = accum_height

        # possibly override with text size
        if self._children_text_min_size:
            dw = max(dw, self._children_text_min_size.width)
            dh = max(dh, self._children_text_min_size.height)

        self._dynamic_content_size = Size2D(width=dw, height=dh)

        dw += mbp_width
        dh += mbp_height

        # override with style settings
        if width      != 'auto': dw = width
        if height     != 'auto': dh = height
        if min_width  != 'auto': dw = max(min_width,  dw)
        if min_height != 'auto': dh = max(min_height, dh)
        if max_width  != 'auto': dw = min(max_width,  dw)
        if max_height != 'auto': dh = min(max_height, dh)

        self._dynamic_full_size = Size2D(width=dw, height=dh)
        # if self._tagName == 'body': print(self._dynamic_content_size, self._dynamic_full_size)

        self._tmp_max_width = max_width

        self._dirty_flow = False

    def update_position(self):
        styles    = self._computed_styles
        style_pos = styles.get('position', 'static')
        pl,pt     = self.left_pixels,self.top_pixels

        # position element
        if style_pos in {'fixed', 'absolute'}:
            # pt,pr,pb,pl = self.top,self.right,self.bottom,self.left
            # # TODO: ignoring units, which could be %!!
            # if type(pt) is tuple: pt = pt[0]
            # if type(pr) is tuple: pr = pr[0]
            # if type(pb) is tuple: pb = pb[0]
            # if type(pl) is tuple: pl = pl[0]
            self._relative_element = self._document_elem if style_pos == 'fixed' else self._nonstatic_elem
            if self._relative_element is None or self._relative_element == self:
                mbp_left = mbp_top = 0
            else:
                mbp_left = self._relative_element._mbp_left
                mbp_top = self._relative_element._mbp_top
            # if self._dirty_flow: print(self,pt,pr,pb,pl)
            if pl == 'auto':
                # if pr != 'auto': print(self, self._relative_element._fitting_size, pr)
                # if pr != 'auto' and self._relative_element._fitting_size:
                #     # TODO: THIS DOES NOT WORK!! NEED TO SUBTRACT WIDTH, BUT DON'T KNOW IF, YET!
                #     # move to set_view_size() or create separate function to set position?
                #     pl = self._relative_element._fitting_size.max_width - pr # - self.width
                # else: pl = 0
                pl = 0
            if pt == 'auto':
                # if pb != 'auto' and self._relative_element._fitting_size:
                #     pt = -self._relative_element._fitting_size.max_height + pb
                # else: pt = 0
                pt = 0
            self._relative_pos = RelPoint2D((pl, pt)) # ((pl + mbp_left, pt - mbp_top))
            self._relative_offset = RelPoint2D((mbp_left, -mbp_top))
        elif style_pos == 'relative':
            if pl == 'auto':
                pl = 0
            if pt == 'auto':
                pt = 0
            self._relative_element = self._parent
            self._relative_pos = RelPoint2D(self._fitting_pos)
            self._relative_offset = RelPoint2D((pl, pt))
        else:
            self._relative_element = self._parent
            self._relative_pos = RelPoint2D(self._fitting_pos)
            self._relative_offset = RelPoint2D((0, 0))

    def set_view_size(self, size:Size2D):
        # parent is telling us how big we will be.  note: this does not trigger a reflow!
        # TODO: clamp scroll
        # TODO: handle vertical and horizontal element alignment
        # TODO: handle justified and right text alignment
        self._absolute_size = size
        self.scrollLeft = self.scrollLeft
        self.scrollTop = self.scrollTop

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


    # @UI_Element_Utils.add_option_callback('position:flexbox')
    # def position_flexbox(self, left, top, width, height):
    #     pass
    # @UI_Element_Utils.add_option_callback('position:block')
    # def position_flexbox(self, left, top, width, height):
    #     pass
    # @UI_Element_Utils.add_option_callback('position:inline')
    # def position_flexbox(self, left, top, width, height):
    #     pass
    # @UI_Element_Utils.add_option_callback('position:none')
    # def position_flexbox(self, left, top, width, height):
    #     pass


    # def position(self, left, top, width, height):
    #     # pos and size define where this element exists
    #     self._l, self._t = left, top
    #     self._w, self._h = width, height

    #     dpi_mult = Globals.drawing.get_dpi_mult()
    #     display = self._computed_styles.get('display', 'block')
    #     margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
    #     padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
    #     border_width = self._get_style_num('border-width', 0)

    #     l = left   + dpi_mult * (margin_left + border_width  + padding_left)
    #     t = top    - dpi_mult * (margin_top  + border_width  + padding_top)
    #     w = width  - dpi_mult * (margin_left + margin_right  + border_width + border_width + padding_left + padding_right)
    #     h = height - dpi_mult * (margin_top  + margin_bottom + border_width + border_width + padding_top  + padding_bottom)

    #     self.call_option_callback(('position:%s' % display), 'position:block', left, top, width, height)

    #     # wrap text
    #     wrap_opts = {
    #         'text':     self._innerText,
    #         'width':    w,
    #         'fontid':   self._fontid,
    #         'fontsize': self._fontsize,
    #         'preserve_newlines': (self._whitespace in {'pre', 'pre-line', 'pre-wrap'}),
    #         'collapse_spaces':   (self._whitespace not in {'pre', 'pre-wrap'}),
    #         'wrap_text':         (self._whitespace != 'pre'),
    #     }
    #     self._innerTextWrapped = helper_wraptext(**wrap_opts)

    @property
    def absolute_pos(self):
        return self._absolute_pos

    def _setup_ltwh(self):
        # parent_pos = self._parent.absolute_pos if self._parent else Point2D((0, self._parent_size.max_height-1))
        parent_pos = self._relative_element.absolute_pos if self._relative_element and self._relative_element != self else Point2D((0, self._parent_size.max_height-1))
        if not parent_pos: parent_pos = RelPoint2D((0,0))
        rel_pos = self._relative_pos or RelPoint2D((0,0))
        rel_offset = self._relative_offset or RelPoint2D((0,0))
        abs_pos = parent_pos + rel_pos + rel_offset
        self._absolute_pos = parent_pos + rel_pos + rel_offset + self._scroll_offset
        self._l = round(abs_pos.x)
        self._t = round(abs_pos.y)
        self._w = round(self._absolute_size.width)
        self._h = round(self._absolute_size.height)
        self._r = self._l + self._w - 1
        self._b = self._t - self._h + 1

    def draw(self, depth=0):
        if not self.is_visible: return

        self._setup_ltwh()

        ScissorStack.push(self._l, self._t, self._w, self._h)
        bgl.glEnable(bgl.GL_BLEND)

        dpi_mult = Globals.drawing.get_dpi_mult()
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin', scale=dpi_mult)
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding', scale=dpi_mult)
        border_width = self._get_style_num('border-width', 0, scale=dpi_mult)

        if ScissorStack.is_visible() and ScissorStack.is_box_visible(self._l, self._t, self._w, self._h):
            if self._innerTextAsIs is not None:
                pos = Point2D((self._l + self._content_offset, self._t))
                size_prev = Globals.drawing.set_font_size(self._parent._fontsize, fontid=self._parent._fontid, force=True)
                Globals.drawing.text_draw2D(self._innerTextAsIs, pos, self._parent._fontcolor)
                Globals.drawing.set_font_size(size_prev, fontid=self._parent._fontid, force=True)
            else:
                if self._src == 'image':
                    # ui_draw.draw(il, it, iw, ih, dpi_mult, self._image_textureid)
                    ui_draw.draw(self._l, self._t, self._w, self._h, dpi_mult, self._computed_styles, self._image_textureid)
                else:
                    ui_draw.draw(self._l, self._t, self._w, self._h, dpi_mult, self._computed_styles)

            if False:
                # include padding
                il = round(self._l + margin_left + border_width + padding_left)
                it = round(self._t - margin_top - border_width - padding_top)
                iw = round(self._w - (margin_left + border_width + padding_left + padding_right + border_width + margin_right))
                ih = round(self._h - (margin_top + border_width + padding_top + padding_bottom + border_width + margin_bottom))
            else:
                # do not include padding
                il = round(self._l + margin_left + border_width)
                it = round(self._t - margin_top - border_width)
                iw = round(self._w - (margin_left + border_width + border_width + margin_right))
                ih = round(self._h - (margin_top + border_width + border_width + margin_bottom))
            ScissorStack.push(il, it, iw, ih)
            for child in self._children_all: child.draw(depth+1)
            ScissorStack.pop()

        ScissorStack.pop()

    def get_under_mouse(self, p:Point2D):
        if not self.is_visible: return None
        if p.x < self._l or p.x >= self._l + self._w: return None
        if p.y > self._t or p.y <= self._t - self._h: return None
        for child in reversed(self._children):
            r = child.get_under_mouse(p)
            if r: return r
        return self


    def structure(self, depth=0, all_children=False):
        l = self._children if not all_children else self._children_all
        return '\n'.join([('  '*depth) + str(self)] + [child.structure(depth+1) for child in l])


    ################################################################################
    # event-related functionality

    def add_eventListener(self, event, callback, useCapture=False):
        assert event in self._events, 'Attempting to add unhandled event handler type "%s"' % event
        sig = signature(callback)
        old_callback = callback
        if len(sig.parameters) == 0:
            callback = lambda e: old_callback()
        self._events[event] += [(useCapture, callback, old_callback)]

    def remove_eventListener(self, event, callback):
        # returns True if callback was successfully removed
        assert event in self._events, 'Attempting to remove unhandled event handler type "%s"' % event
        l = len(self._events[event])
        self._events[event] = [(capture,cb,old_cb) for (capture,cb,old_cb) in self._events[event] if old_cb != callback]
        return l != len(self._events[event])

    def _fire_event(self, event, details):
        ph = details.event_phase
        cap, bub, df = details.capturing, details.bubbling, not details.default_prevented
        if (cap and ph == 'capturing') or (df and ph == 'at target'):
            for (cap,cb,old_cb) in self._events[event]:
                if cap: cb(details)
        if (bub and ph == 'bubbling') or (df and ph == 'at target'):
            for (cap,cb,old_cb) in self._events[event]:
                if not cap: cb(details)

    def dispatch_event(self, event, mouse=None, key=None, ui_event=None):
        if mouse is None: mouse = ui_document.actions.mouse
        if ui_event is None: ui_event = UI_Event(target=self, mouse=mouse, key=key)
        path = self.get_pathToRoot()[1:] # skipping first item, which is self
        ui_event.event_phase = 'capturing'
        for cur in path[::-1]: cur._fire_event(event, ui_event)
        ui_event.event_phase = 'at target'
        self._fire_event(event, ui_event)
        ui_event.event_phase = 'bubbling'
        for cur in path: cur._fire_event(event, ui_event)

    ################################################################################
    # the following methods can be overridden to create different types of UI

    ## Layout, Positioning, and Drawing
    # `self.layout_children()` should set `self._content_width` and `self._content_height` based on children.
    def compute_content(self): pass
    def compute_preferred_size(self): pass



class UI_Proxy:
    def __init__(self, default_element):
        # NOTE: use self.__dict__ here!!!
        self.__dict__['_default_element'] = default_element
        self.__dict__['_mapping'] = {}
        self.__dict__['_translate'] = {}
    def map(self, attribs, ui_element):
        if type(attribs) is str: attribs = [attribs]
        t = self._translate
        attribs = [t.get(a, a) for a in attribs]
        for attrib in attribs: self._mapping[attrib] = ui_element
    def translate(self, attrib_from, attrib_to):
        self._translate[attrib_from] = attrib_to
    def translate_map(self, attrib_from, attrib_to, ui_element):
        self.translate(attrib_from, attrib_to)
        self.map([attrib_to], ui_element)
    def unmap(self, attribs):
        if type(attribs) is str: attribs = [attribs]
        for attrib in attribs: self._mapping[attrib] = None
    def __dir__(self):
        return dir(self._default_element)
    def __getattr__(self, attrib):
        ui_element = self._mapping.get(attrib, None)
        if ui_element is None: ui_element = self._default_element
        return getattr(ui_element, attrib)
    def __setattr__(self, attrib, val):
        if attrib in self.__dict__:
            self.__dict__[attrib] = val
            return val
        ui_element = self._mapping.get(attrib, None)
        if ui_element is None: ui_element = self._default_element
        return setattr(ui_element, attrib, val)


class UI_Document_FSM:
    fsm = FSM()
    FSM_State = fsm.wrapper

class UI_Document(UI_Document_FSM):
    default_keymap = {
        'commit': {'RET',},
        'cancel': {'ESC',},
        'keypress':
            {c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'} |
            {'NUMPAD_%d'%i for i in range(10)} | {'NUMPAD_PERIOD','NUMPAD_MINUS','NUMPAD_PLUS','NUMPAD_SLASH','NUMPAD_ASTERIX'} |
            {'ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE'} |
            {'PERIOD', 'MINUS', 'SPACE', 'SEMI_COLON', 'COMMA', 'QUOTE', 'ACCENT_GRAVE', 'PLUS', 'SLASH', 'BACK_SLASH', 'EQUAL', 'LEFT_BRACKET', 'RIGHT_BRACKET'},
    }

    doubleclick_time = 0.25
    allow_disabled_to_blur = False
    key_repeat_delay = 0.1500 * 0.8
    key_repeat_pause = 0.0700 * 0.2

    def __init__(self):
        self._context = None
        self._area = None

    def init(self, context, **kwargs):
        self._context = context
        self._area = context.area
        self.actions = Actions(bpy.context, UI_Document.default_keymap)
        self._body = UI_Element(tagName='body')
        self._timer = context.window_manager.event_timer_add(1.0 / 120, window=context.window)
        self.fsm.init(self, start='main')

        self.ignore_hover_change = False

        self._under_mouse = None
        self._under_down = None
        self._focus = None

        self._last_mx = -1
        self._last_my = -1
        self._last_mouse = Point2D((-1, -1))
        self._last_lmb = False
        self._last_mmb = False
        self._last_rmb = False
        self._last_under_mouse = None
        self._last_under_click = None
        self._last_click_time = 0
        self._last_sz = None

    @property
    def body(self):
        return self._body

    def update(self, context, event):
        if context.area != self._area: return

        self.actions.update(context, event, self._timer, print_actions=False)

        self._mx,self._my = self.actions.mouse if self.actions.mouse else (-1,-1)
        self._mouse = Point2D((self._mx, self._my))
        self._under_mouse = self._body.get_under_mouse(self._mouse)
        self._lmb = self.actions.using('LEFTMOUSE')
        self._mmb = self.actions.using('MIDDLEMOUSE')
        self._rmb = self.actions.using('RIGHTMOUSE')

        self.fsm.update()

        self._last_mx = self._mx
        self._last_my = self._my
        self._last_mouse = self._mouse
        self._last_lmb = self._lmb
        self._last_mmb = self._mmb
        self._last_rmb = self._rmb
        self._last_under_mouse = self._under_mouse

        uictrld = False
        uictrld |= self._under_mouse is not None and self._under_mouse != self._body
        uictrld |= self.fsm.state != 'main'
        # uictrld |= self._focus is not None
        return {'hover'} if uictrld else None


    def _addrem_pseudoclass(self, pseudoclass, remove_from=None, add_to=None):
        rem = set(remove_from.get_pathToRoot()) if remove_from else set()
        add = set(add_to.get_pathToRoot()) if add_to else set()
        for e in rem - add: e.del_pseudoclass(pseudoclass)
        for e in add - rem: e.add_pseudoclass(pseudoclass)

    def handle_hover(self, change_cursor=True):
        # handle :hover, on_mouseenter, on_mouseleave
        if self.ignore_hover_change: return

        if change_cursor and self._under_mouse and self._under_mouse._tagName != 'body':
            cursor = self._under_mouse._computed_styles.get('cursor', 'default')
            Globals.drawing.set_cursor(convert_token_to_cursor(cursor))

        if self._under_mouse == self._last_under_mouse: return

        self._addrem_pseudoclass('hover', remove_from=self._last_under_mouse, add_to=self._under_mouse)
        if self._last_under_mouse: self._last_under_mouse.dispatch_event('on_mouseleave')
        if self._under_mouse: self._under_mouse.dispatch_event('on_mouseenter')

    def handle_mousemove(self, ui_element=None):
        ui_element = ui_element or self._under_mouse
        if ui_element is None: return
        if self._last_mouse.x == self._mouse.x and self._last_mouse.y == self._mouse.y: return
        ui_element.dispatch_event('on_mousemove')


    @UI_Document_FSM.FSM_State('main', 'enter')
    def modal_main_enter(self):
        Globals.drawing.set_cursor('DEFAULT')

    @UI_Document_FSM.FSM_State('main')
    def modal_main(self):
        if self._mmb and not self._last_mmb:
            return 'scroll'

        if self._lmb and not self._last_lmb:
            return 'mousedown'

        self.handle_hover()
        self.handle_mousemove()

        if False:
            print('---------------------------')
            if self._focus:      print('FOCUS', self._focus, self._focus.pseudoclasses)
            else: print('FOCUS', None)
            if self._under_down: print('DOWN',  self._under_down, self._under_down.pseudoclasses)
            else: print('DOWN', None)
            if under_mouse:      print('UNDER', under_mouse, under_mouse.pseudoclasses)
            else: print('UNDER', None)


    @UI_Document_FSM.FSM_State('scroll', 'can enter')
    def modal_scroll_canenter(self):
        # find first along root to path that can scroll
        if not self._under_mouse: return False
        self._scrollable = [e for e in self._under_mouse.get_pathToRoot() if e.is_scrollable]
        if not self._scrollable: return False

    @UI_Document_FSM.FSM_State('scroll', 'enter')
    def modal_scroll_enter(self):
        e = self._scrollable[0]
        self._scroll_element = e
        self._scroll_point = self._mouse
        self._scroll_last = RelPoint2D((e.scrollLeft, e.scrollTop))
        Globals.drawing.set_cursor('SCROLL_Y')

    @UI_Document_FSM.FSM_State('scroll')
    def modal_scroll(self):
        if not self._mmb:
            # done scrolling
            return 'main'
        nx = self._scroll_element.scrollLeft + (self._scroll_point.x - self._mx)
        ny = self._scroll_element.scrollTop  - (self._scroll_point.y - self._my)
        self._scroll_element.scrollLeft = nx
        self._scroll_element.scrollTop = ny
        print(self._scroll_element, nx, ny)
        self._scroll_point = self._mouse
        self._scroll_element._setup_ltwh()


    @UI_Document_FSM.FSM_State('mousedown', 'can enter')
    def modal_mousedown_canenter(self):
        can_enter = True
        can_enter &= bool(self._under_mouse) and not self._under_mouse.is_disabled
        if UI_Document.allow_disabled_to_blur and not can_enter and self._focus:
            # blur previous
            self._focus.del_pseudoclass('focus')
            self._focus.dispatch_event('on_blur')
            self._focus = None
        return can_enter

    @UI_Document_FSM.FSM_State('mousedown', 'enter')
    def modal_mousedown_enter(self):
        change_focus = self._focus != self._under_mouse
        if change_focus:
            self.blur()
            if self._under_mouse.can_focus:
                self.focus(self._under_mouse)

        self._under_mousedown = self._under_mouse
        self._addrem_pseudoclass('active', add_to=self._under_mousedown)
        # self._under_mousedown.add_pseudoclass('active')
        self._under_mousedown.dispatch_event('on_mousedown')

    @UI_Document_FSM.FSM_State('mousedown')
    def modal_mousedown(self):
        if not self._lmb:
            # done with mousedown
            return 'focus' if self._under_mousedown.can_focus else 'main'
        self.handle_hover(change_cursor=False)
        self.handle_mousemove(ui_element=self._under_mousedown)

    @UI_Document_FSM.FSM_State('mousedown', 'exit')
    def modal_mousedown_exit(self):
        self._under_mousedown.dispatch_event('on_mouseup')
        if self._under_mouse == self._under_mousedown:
            # CLICK!
            dblclick = True
            dblclick &= self._under_mousedown == self._last_under_click
            dblclick &= time.time() < self._last_click_time + self.doubleclick_time
            self._under_mousedown.dispatch_event('on_mouseclick')
            self._last_under_click = self._under_mousedown
            if dblclick:
                self._under_mousedown.dispatch_event('on_mousedblclick')
                # self._last_under_click = None
            if self._under_mousedown.forId:
                # send mouseclick events to ui_element indicated by forId!
                ui_for = self._under_mousedown.get_root().getElementById(self._under_mousedown.forId)
                if ui_for is None: return
                ui_for.dispatch_event('mouseclick', ui_event=e)
            self._last_click_time = time.time()
        else:
            self._last_under_click = None
            self._last_click_time = 0
        self._addrem_pseudoclass('active', remove_from=self._under_mousedown)
        # self._under_mousedown.del_pseudoclass('active')

    def blur(self):
        if self._focus is None: return
        self._focus.del_pseudoclass('focus')
        self._focus.dispatch_event('on_blur')
        self._focus = None

    def focus(self, ui_element):
        if ui_element is None: return
        if self._focus == ui_element: return
        self.blur()
        self._focus = ui_element
        self._focus.add_pseudoclass('focus')
        self._focus.dispatch_event('on_focus')

    @UI_Document_FSM.FSM_State('focus', 'enter')
    def modal_focus_enter(self):
        self._last_pressed = None
        self._last_press_time = 0
        self._last_press_start = 0

    @UI_Document_FSM.FSM_State('focus')
    def modal_focus(self):
        if self.actions.pressed('LEFTMOUSE', unpress=False):
            return 'mousedown'
        # if self.actions.pressed('ESC'):
        #     self.blur()
        #     return 'main'
        self.handle_hover()
        self.handle_mousemove()

        pressed = None
        if self.actions.using('keypress', ignoreshift=True):
            pressed = self.actions.as_char(self.actions.last_pressed)
        for k,v in kmi_to_keycode.items():
            if self.actions.using(k): pressed = v
        if pressed:
            cur = time.time()
            if self._last_pressed != pressed:
                self._last_press_start = cur
                self._last_press_time = 0
                self._focus.dispatch_event('on_keypress', key=pressed)
            elif cur >= self._last_press_start + UI_Document.key_repeat_delay and cur >= self._last_press_time + UI_Document.key_repeat_pause:
                self._last_press_time = cur
                self._focus.dispatch_event('on_keypress', key=pressed)
        self._last_pressed = pressed

        if not self._focus: return 'main'

    def draw(self, context):
        if self._area != context.area: return
        w,h = context.region.width, context.region.height
        sz = Size2D(width=w, max_width=w, height=h, max_height=h)

        ScissorStack.start(context)
        Globals.ui_draw.update()
        bgl.glEnable(bgl.GL_BLEND)

        if (w,h) != self._last_sz:
            self._last_sz = (w,h)
            self._body.dirty_flow()
            # self._body.dirty('region size changed', 'style', children=True)
        self._body.clean()
        self._body.layout(first_on_line=True, fitting_size=sz, fitting_pos=Point2D((0,h-1)), parent_size=sz, nonstatic_elem=None, document_elem=self._body)
        self._body.set_view_size(sz)
        self._body._call_postflow()
        self._body.layout(first_on_line=True, fitting_size=sz, fitting_pos=Point2D((0,h-1)), parent_size=sz, nonstatic_elem=None, document_elem=self._body)
        self._body.set_view_size(sz)
        self._body.draw()

        ScissorStack.end()

ui_document = Globals.set(UI_Document())


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





