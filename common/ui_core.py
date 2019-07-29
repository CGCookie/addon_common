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
from inspect import signature
import traceback

import bpy
import bgl

from .ui_styling import UI_Styling, ui_defaultstylings
from .ui_utilities import helper_wraptext
from .drawing import ScissorStack

from .useractions import Actions

from .globals import Globals
from .decorators import debug_test_call, blender_version_wrapper
from .maths import Vec2D, Color, mid, Box2D, Size1D, Size2D, Point2D
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


def get_image_path(fn, ext=None, subfolders=None):
    # if no subfolders are given, assuming image path is <root>/icons
    # or <root>/images where <root> is the 2 levels above this file
    if subfolders is None: subfolders = ['icons', 'images']
    if ext: fn = '%s.%s' % (fn,ext)
    path_root = os.path.join(os.path.dirname(__file__), '..', '..')
    paths = [os.path.join(path_root, p, fn) for p in subfolders]
    return iter_head((p for p in paths if os.path.exists(p)), None)


def load_image_png(fn):
    if not hasattr(load_image_png, 'cache'): load_image_png.cache = {}
    if not fn in load_image_png.cache:
        # have not seen this image before
        # note: assuming 4 channels (rgba) per pixel!
        w,h,d,m = png.Reader(get_image_path(fn)).read()
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
            set_uniform_float_mult('margin_left',    'margin-left',   0)
            set_uniform_float_mult('margin_right',   'margin-right',  0)
            set_uniform_float_mult('margin_top',     'margin-top',    0)
            set_uniform_float_mult('margin_bottom',  'margin-bottom', 0)
            set_uniform_float_mult('border_width',   'border-width',  0)
            set_uniform_float_mult('border_radius',  'border-radius', 0)
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
    @staticmethod
    def add_cleaning_callback(label, labels_dirtied=None):
        # NOTE: this function decorator does NOT call self.dirty!
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

    # _cleaning_callbacks = {}
    # @staticmethod
    # def add_cleaning_callback(order):
    #     # TODO: change order to label, and add set of labels that are dirtied after cleaning
    #     #       create a graph of labels to use for cleaning ordering
    #     def wrapper(fn):
    #         def wrapped(self, *args, **kwargs):
    #             ret = fn(self, *args, **kwargs)
    #             return ret
    #         l = UI_Element_Utils._cleaning_callbacks.get(order, [])
    #         UI_Element_Utils._cleaning_callbacks[order] = l + [wrapped]
    #         return wrapped
    #     return wrapper

    def call_cleaning_callbacks(self, *args, **kwargs):
        # print('cleaning %s' % str(self))
        g = UI_Element_Utils._cleaning_graph
        working = set(UI_Element_Utils._cleaning_graph_roots)
        done = set()
        while working:
            current = working.pop()
            assert current not in done, 'cycle detected in cleaning callbacks (%s)' % current
            if not all(p in done for p in g[current]['parents']): continue
            if current in self._dirty_properties:
                # print('  calling on %s' % current)
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
        # keys = sorted(_cleaning_callbacks.keys())
        # for k in keys:
        #     for cb in UI_Element_Utils._cleaning_callbacks[k]:
        #         cb(self, *args, **kwargs)


    #####################################################################
    # helper functions
    # MUST BE CALLED AFTER `compute_style()` METHOD IS CALLED!

    re_percent = re.compile(r'(?P<v>\d+)%')
    def _get_style_num(self, k, def_v, percent_of=None, min_v=None, max_v=None, scale=None):
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
        # print(self, k, def_v, percent_of, min_v, max_v, scale, v)
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
        self.dirty('style changed', 'style')
    def add_style(self, style):
        self._style_str = '%s;%s' % (self._style_str, str(style or ''))
        self._styling_custom = None
        self.dirty('style changed', 'style')

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, nid):
        nid = '' if nid is None else nid.strip()
        if self._id == nid: return
        self._id = nid
        self.dirty('changing id can affect styles', parent=True, children=True)

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
        self.dirty('changing classes can affect styles', parent=True, children=True)
    def add_class(self, cls):
        assert ' ' not in cls, 'cannot add class "%s" to "%s" because it has a space in it' % (cls, self._tagName)
        if cls in self._classes: return
        self._classes.add(cls)
        self._classes_str = '%s %s' (self._classes_str, cls)
        self.dirty('adding classes can affect styles', parent=True, children=True)
    def del_class(self, cls):
        assert ' ' not in cls, 'cannot del class "%s" from "%s" because it has a space in it' % (cls, self._tagName)
        if cls not in self._classes: return
        self._classes.remove(cls)
        self._classes_str = ' '.join(self._classes)
        self.dirty('deleting classes can affect styles', parent=True, children=True)

    @property
    def pseudoclasses(self):
        return set(self._pseudoclasses)
    def clear_pseudoclass(self):
        if not self._pseudoclasses: return
        self._pseudoclasses = set()
        self.dirty('clearing psuedoclasses affects style', parent=True, children=True)
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)
        self.dirty('adding psuedoclasses affects style', parent=True, children=True)
    def del_pseudoclass(self, pseudo):
        if pseudo not in self._pseudoclasses: return
        self._pseudoclasses.discard(pseudo)
        self.dirty('deleting psuedoclasses affects style', parent=True, children=True)
    @property
    def is_active(self): return 'active' in self._pseudoclasses
    @property
    def is_hovered(self): return 'hover' in self._pseudoclasses
    @property
    def is_focused(self): return 'focus' in self._pseudoclasses

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
        return self._src
    @src.setter
    def src(self, v):
        # TODO: load the resource and do something with it!!
        self._src = v
        self.dirty('changing src affects content', parent=True, children=False)

    @property
    def title(self):
        return self._title
    @title.setter
    def title(self, v):
        self._title = v
        self.dirty('title changed', parent=True, children=False)

    @property
    def scrollTop(self):
        # TODO: clamp value?
        return self._content_box.y
    @scrollTop.setter
    def scrollTop(self, v):
        # TODO: clamp value?
        if self._content_box.y == v: return
        self._content_box.y = v

    @property
    def scrollLeft(self):
        # TODO: clamp value?
        return -self._content_box.x    # negated so that positive values of scrollLeft scroll content left
    @scrollLeft.setter
    def scrollLeft(self, v):
        # TODO: clamp value?
        if self._content_box.x == -v: return
        self._content_box.x = -v

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

    @property
    def content_width(self):
        return self._static_content_size.width
    @property
    def content_height(self):
        return self._static_content_size.height



class UI_Element_Dirtiness:
    def dirty(self, cause, properties=None, parent=True, children=False):
        parent &= self._parent is not None
        if properties is None: properties = {'style', 'size', 'blocks', 'content'}
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
                self._parent.dirty('propagating dirtiness (%s) from %s to parent %s' % (str(self._dirty_propagation['parent']), str(self), str(self._parent)), self._dirty_propagation['parent'], parent=True, children=False)
            self._dirty_propagation['parent'].clear()
        if self._dirty_propagation['children']:
            for child in self._children:
                child.dirty('propagating dirtiness (%s) from %s to child %s' % (str(self._dirty_propagation['children']), str(self), str(child)), self._dirty_propagation['children'], parent=False, children=True)
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
        self.call_cleaning_callbacks()
        #assert not self.is_dirty, '%s is still dirty after cleaning: %s' % (str(self), str(self._dirty_properties))
        # self._compute_style()
        # self._compute_content()
        # self._compute_content_size()



class UI_SizeInfo:
    def __init__(self, ui_element, **kwargs):
        i = float('inf')
        inside_width  = ui_element._inside_size.biggest_width() or 0
        inside_height = ui_element._inside_size.biggest_height() or 0
        self._kwargs      = dict(kwargs)
        self.dpi_mult     = Globals.drawing.get_dpi_mult()
        self.border_width = ui_element._get_style_num('border-width', 0)
        self.styles       = ui_element._computed_styles
        self.display      = self.styles.get('display', 'block')
        self.is_nonstatic = self.styles.get('position','static') in {'absolute','relative','fixed','sticky'}
        self.width        = self.styles.get('width',  'auto', percent_of=inside_width)              # could be 'auto'
        self.height       = self.styles.get('height', 'auto', percent_of=inside_height)             # could be 'auto'
        self.min_width    = ui_element._get_style_num('min-width',  0, percent_of=inside_width)
        self.min_height   = ui_element._get_style_num('min-height', 0, percent_of=inside_height)
        self.max_width    = ui_element._get_style_num('max-width',  i, percent_of=inside_width)
        self.max_height   = ui_element._get_style_num('max-height', i, percent_of=inside_height)
        self.margin_top,  self.margin_right,  self.margin_bottom,  self.margin_left  = ui_element._get_style_trbl('margin')
        self.padding_top, self.padding_right, self.padding_bottom, self.padding_left = ui_element._get_style_trbl('padding')

    def __getattr__(self, k):
        return self._kwargs.get(k, self._default_val)


# class UI_Block:
#     '''
#     UI_Block is similar to an HTML element with display:block style.
#     all children ...
#     '''
#     def __init__(self, children):
#         self._children = children



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
        self._src           = None      # path to resource, such as image
        self._title         = None      # tooltip

        #################################################################
        # read-only attributes of UI_Element
        self._parent        = None      # read-only property; set in parent.append_child(child)
        self._children      = []        # read-only list of all children; append_child, delete_child, clear_children
        self._pseudoclasses = set()     # TODO: should order matter here? (make list)
                                        # updated by main ui system (hover, active, focus)
        self._pseudoelement = ''        # set only if element is a pseudoelement ('::before' or '::after')

        #################################################################################
        # boxes for viewing (wrt blender region) and content (wrt view)
        # NOTE: content box is larger than viewing => scrolling, which is
        #       managed by offsetting the content box up (y+1) or left (x-1)
        self._static_content_size  = None       # size of static content (text, image, etc.) w/o margin,border,padding
        self._dynamic_content_size = None       # size of dynamic content (static or wrapped children) w/o mbp
        self._dynamic_full_size    = None       # size of dynamic content with mbp added
        self._relative_element     = None
        self._relative_pos         = None
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
        #       - second item is the callback function
        self._events = {
            'on_focus':         [],     # focus is gained (:active is added)
            'on_blur':          [],     # focus is lost (:active is removed)
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
        }

        ####################################################################
        # cached properties
        # TODO: go back through these to make sure we've caught everything
        self._classes          = []     # classes applied to element, set by self.classes property, based on self._classes_str
        self._styling_custom   = None   # custom style UI_Style, set by self.style property, based on self._style_str
        self._computed_styles  = None   # computed style UI_Style after applying all styling
        self._is_visible       = False  # indicates if self is visible, set in compute_style(), based on self._computed_styles
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
        self._innerTextAsIs    = None   # text to display as-is (no wrapping)

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
        self._l, self._t, self._w, self._h = 0,0,0,0
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
        info = ['tagName', 'id', 'innerTextAsIs']
        info = [(k, getattr(self, k)) for k in info]
        info = ['%s="%s"' % (k, str(v)) for k,v in info if v]
        return '<UI_Element %s>' % ' '.join(info)

    @UI_Element_Utils.add_cleaning_callback('style', {'size', 'content'})
    def _compute_style(self):
        '''
        rebuilds self._selector and computes the stylesheet, propagating computation to children
        '''
        if self._defer_clean: return
        if 'style' not in self._dirty_properties: return

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
            sel_tagName = self._tagName
            sel_id = '#%s' % self._id if self._id else ''
            sel_cls = ''.join('.%s' % c for c in self._classes)
            sel_pseudo = ''.join(':%s' % p for p in self._pseudoclasses)
            self._selector = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo]
            self._selector_before = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo + '::before']
            self._selector_after  = sel_parent + [sel_tagName + sel_id + sel_cls + sel_pseudo + '::after']

        # initialize styles in order: default, focus, active, hover, hover+active
        if self._styling_default is None:
            self._styling_default = UI_Styling()
            for pseudoclasses in [None, 'focus', 'active', 'hover', ['hover','active']]:
                filtered_decllist = ui_defaultstylings.filter_styling(self._tagName, pseudoclasses)
                self._styling_default.append(filtered_decllist)

        # compute styles applied to self based on selector
        styling_list = [self._styling_default, ui_draw.stylesheet, self._styling_custom]
        if not self._styling_custom:
            self._styling_custom = UI_Styling('*{%s;}' % self._style_str)
        self._computed_styles = UI_Styling.compute_style(self._selector, *styling_list)
        self._is_visible = self._computed_styles.get('display', 'auto') != 'none'
        if self._is_visible and not self._pseudoelement:
            # need to compute ::before and ::after styles to know whether there is content to compute and render
            self._computed_styles_before = UI_Styling.compute_style(self._selector_before, *styling_list)
            self._computed_styles_after  = UI_Styling.compute_style(self._selector_after,  *styling_list)
        else:
            self._computed_styles_before = None
            self._computed_styles_after = None

        fontfamily = self._computed_styles.get('font-family', 'sans-serif')
        fontstyle = self._computed_styles.get('font-style', 'normal')
        fontweight = self._computed_styles.get('font-weight', 'normal')
        self._fontid = get_font(fontfamily, fontstyle, fontweight)
        self._fontsize = float(self._computed_styles.get('font-size', (12,''))[0])
        self._fontcolor = self._computed_styles.get('color', (0,0,0,1))

        self._whitespace = self._computed_styles.get('white-space', 'normal')

        # tell children to recompute selector
        for child in self._children: child._compute_style()

        self.dirty('style change might have changed content (::before / ::after)', 'content')
        self.dirty('style change might have changed size', 'size')
        self._dirty_flow = True
        self._dirty_properties.discard('style')

        self.defer_dirty_propagation = False

    @UI_Element_Utils.add_cleaning_callback('content', {'blocks'})
    def _compute_content(self):
        if self._defer_clean: return
        if 'content' not in self._dirty_properties: return
        if not self.is_visible:
            self._dirty_properties.discard('content')
            return

        self.defer_dirty_propagation = True

        if self._computed_styles_before and self._computed_styles_before.get('content', ''):
            # TODO: cache this!!
            # print('%s::before = %s' % (str(self), self._compute_style_before.get('content', '')))
            self._child_before = UI_Element(tagName=self._tagName, pseudoelement='before')
            self._child_before.clean()
        else:
            self._child_before = None

        if self._computed_styles_after and self._computed_styles_after.get('content', ''):
            # TODO: cache this!!
            # print('%s::after = %s' % (str(self), self._compute_style_after.get('content', '')))
            self._child_after = UI_Element(tagName=self._tagName, pseudoelement='after')
            self._child_after.clean()
        else:
            self._child_after = None

        if self._innerText:
            # TODO: cache this!!
            self._textwrap_opts = {
                'text':              self._innerText,
                'fontid':            self._fontid,
                'fontsize':          self._fontsize,
                'preserve_newlines': self._whitespace in {'pre', 'pre-line', 'pre-wrap'},
                'collapse_spaces':   self._whitespace not in {'pre', 'pre-wrap'},
                'wrap_text':         self._whitespace != 'pre',
            }
            innerTextWrapped = helper_wraptext(**self._textwrap_opts)
            if self._innerTextWrapped != innerTextWrapped:
                self._innerTextWrapped = innerTextWrapped
                self._children_text = []
                for l in self._innerTextWrapped.splitlines():
                    if self._children_text: self._children_text.append(UI_Element(tagName='br'))
                    self._children_text += [UI_Element(innerTextAsIs=w, _parent=self) for w in l.split()]
                self._children_text_min_size = Size2D(width=0, height=0)
                for child in self._children_text:
                    child.clean()
                    self._children_text_min_size.width = max(self._children_text_min_size.width, child._static_content_size.width)
                    self._children_text_min_size.height = max(self._children_text_min_size.height, child._static_content_size.height)
        else:
            self._children_text = None
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
        self._dirty_flow = True
        self._dirty_properties.discard('content')

        self.defer_dirty_propagation = False

    @UI_Element_Utils.add_cleaning_callback('blocks', {'size'})
    def _compute_blocks(self):
        # split up all children into layout blocks

        if self._defer_clean: return
        if 'blocks' not in self._dirty_properties: return
        if not self.is_visible:
            self._dirty_properties.discard('blocks')
            return

        self.defer_dirty_propagation = True

        if self._computed_styles.get('display', 'inline') == 'flexbox':
            # all children are treated as flex blocks, regardless of their display
            pass
        else:
            # collect children into blocks
            self._blocks = []
            blocking = False
            for child in self._children_all:
                d = child._computed_styles.get('display', 'inline')
                if d == 'inline':
                    if not blocking:
                        self._blocks.append([])
                        blocking = True
                    self._blocks[-1] += [child]
                else:
                    self._blocks.append([child])
                    blocking = False

        for child in self._children_all:
            child._compute_blocks()

        # content changes might have changed size
        self.dirty('block changes might have changed size', 'size')
        self._dirty_flow = True
        self._dirty_properties.discard('blocks')

        self.defer_dirty_propagation = False

    ################################################################################################
    # NOTE: COMPUTE STATIC CONTENT SIZE (TEXT, IMAGE, ETC.), NOT INCLUDING MARGIN, BORDER, PADDING
    #       WE MIGHT NOT NEED TO COMPUTE MIN AND MAX??
    @UI_Element_Utils.add_cleaning_callback('size')
    def _compute_static_content_size(self):
        if self._defer_clean: return
        if 'size' not in self._dirty_properties: return
        if not self.is_visible:
            self._dirty_properties.discard('size')
            return

        self.defer_dirty_propagation = True

        for child in self._children_all:
            child._compute_static_content_size()

        self._static_content_size = None

        # set size based on content (computed size)
        if self._innerTextAsIs:
            # TODO: allow word breaking?
            # size_prev = Globals.drawing.set_font_size(self._textwrap_opts['fontsize'], fontid=self._textwrap_opts['fontid'], force=True)
            size_prev = Globals.drawing.set_font_size(self._fontsize, fontid=self._fontid, force=True)
            self._static_content_size = Size2D()
            self._static_content_size.set_all_widths(Globals.drawing.get_text_width(self._innerTextAsIs))
            self._static_content_size.set_all_heights(Globals.drawing.get_line_height(self._innerTextAsIs))
            # Globals.drawing.set_font_size(size_prev, fontid=self._textwrap_opts['fontid'], force=True)
            Globals.drawing.set_font_size(size_prev, fontid=self._fontid, force=True)
        elif self._src:
            # TODO: set to image size?
            dpi_mult = Globals.drawing.get_dpi_mult()
            self._static_content_size = Size2D()
            self._static_content_size.set_all_widths(10 * dpi_mult)
            self._static_content_size.set_all_heights(10 * dpi_mult)
            pass
        else:
            # self._static_content_size.min_width  = min(min(child._content_size.min_width  for child in block) for block in self._blocks)
            # self._static_content_size.max_width  = min(sum(child._content_size.max_width  for child in block) for block in self._blocks)
            # self._static_content_size.min_height = sum(min(child._content_size.min_height for child in block) for block in self._blocks)
            # self._static_content_size.max_height = sum(sum(child._content_size.max_height for child in block) for block in self._blocks)
            pass

        # # override computed sizes with styled sizes
        # def setter(content_property, style_property):
        #     # TODO: handle percentages??
        #     v = self._computed_styles.get(style_property, 'auto')
        #     if v != 'auto': setattr(self._static_content_size, content_property, sz.dpi_mult * v)
        # setter('width', 'width')
        # setter('height', 'height')
        # setter('min_width', 'min-width')
        # setter('min_height', 'min-height')
        # setter('max_width', 'max-width')
        # setter('max_height', 'max-height')

        # # add margin, border, and padding
        # if self._static_content_size.width is not None:
        #     self._static_content_size.add_width(sz.dpi_mult * (
        #         sz.margin_left + sz.margin_right  + sz.border_width +   # left side
        #         sz.border_width + sz.padding_left + sz.padding_right    # right side
        #     ))
        # if self._static_content_size.height is not None:
        #     self._static_content_size.add_height(sz.dpi_mult * (
        #         sz.margin_top + sz.margin_bottom + sz.border_width +    # top side
        #         sz.border_width + sz.padding_top  + sz.padding_bottom   # bottom side
        #     ))
        # if self._static_content_size.min_width is not None:
        #     self._static_content_size.add_min_width(sz.dpi_mult * (
        #         sz.margin_left + sz.margin_right  + sz.border_width +   # left side
        #         sz.border_width + sz.padding_left + sz.padding_right    # right side
        #     ))
        # if self._static_content_size.max_width is not None:
        #     self._static_content_size.add_max_width(sz.dpi_mult * (
        #         sz.margin_left + sz.margin_right  + sz.border_width +   # left side
        #         sz.border_width + sz.padding_left + sz.padding_right    # right side
        #     ))
        # if self._static_content_size.min_height is not None:
        #     self._static_content_size.add_min_height(sz.dpi_mult * (
        #         sz.margin_top + sz.margin_bottom + sz.border_width +    # top side
        #         sz.border_width + sz.padding_top  + sz.padding_bottom   # bottom side
        #     ))
        # if self._static_content_size.max_height is not None:
        #     self._static_content_size.add_max_height(sz.dpi_mult * (
        #         sz.margin_top + sz.margin_bottom + sz.border_width +    # top side
        #         sz.border_width + sz.padding_top  + sz.padding_bottom   # bottom side
        #     ))

        self._dirty_properties.discard('size')
        self._dirty_flow = True
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

        if not self._dirty_flow: return
        #if not self.is_dirty: return
        #if self._defer_recalc: return
        if not self.is_visible: return

        fitting_size   = kwargs['fitting_size']     # size from parent that we should try to fit in (only max)
        fitting_pos    = kwargs['fitting_pos']      # top-left position wrt parent where we go if not absolute or fixed
        parent_size    = kwargs['parent_size']      # size of inside of parent
        nonstatic_elem = kwargs['nonstatic_elem']   # last non-static element
        document_elem  = kwargs['document_elem']    # whole document element (root)

        dpi_mult     = Globals.drawing.get_dpi_mult()
        styles       = self._computed_styles
        display      = styles.get('display', 'block')
        style_pos    = styles.get('position', 'static')
        is_nonstatic = style_pos in {'absolute','relative','fixed','sticky'}
        is_contribute = style_pos not in {'absolute', 'fixed'}
        next_nonstatic_elem = self if is_nonstatic else nonstatic_elem
        parent_width  = parent_size.biggest_width()  or 0
        parent_height = parent_size.biggest_height() or 0
        width        = self._get_style_num('width',      'auto', percent_of=parent_width)   # could be 'auto'
        height       = self._get_style_num('height',     'auto', percent_of=parent_height)  # could be 'auto'
        min_width    = self._get_style_num('min-width',  'auto', percent_of=parent_width)   # could be 'auto'
        min_height   = self._get_style_num('min-height', 'auto', percent_of=parent_height)  # could be 'auto'
        max_width    = self._get_style_num('max-width',  'auto', percent_of=parent_width)   # could be 'auto'
        max_height   = self._get_style_num('max-height', 'auto', percent_of=parent_height)  # could be 'auto'
        border_width = self._get_style_num('border-width', 0)
        margin_top,  margin_right,  margin_bottom,  margin_left  = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')

        mbp_left   = dpi_mult * (margin_left    + border_width + padding_left)
        mbp_right  = dpi_mult * (padding_right  + border_width + margin_right)
        mbp_top    = dpi_mult * (margin_top     + border_width + padding_top)
        mbp_bottom = dpi_mult * (padding_bottom + border_width + margin_bottom)
        mbp_width  = mbp_left + mbp_right
        mbp_height = mbp_top  + mbp_bottom

        if self._static_content_size:
            # self has static content size
            dw = mbp_width  + self._static_content_size.width
            dh = mbp_height + self._static_content_size.height

        else:
            # self has no static content, so flow and size is determined from children
            # note: will keep track of accumulated size and possibly update inside size as needed
            # note: style size overrides passed fitting size
            inside_size = Size2D()
            if fitting_size.max_width  is not None: inside_size.max_width  = max(0, fitting_size.max_width  - mbp_width)
            if fitting_size.max_height is not None: inside_size.max_height = max(0, fitting_size.max_height - mbp_height)
            if max_width  != 'auto': inside_size.max_width  = max(0, max_width  - mbp_width)
            if max_height != 'auto': inside_size.max_height = max(0, max_height - mbp_height)

            lines = []
            accum_width  = 0    # max width for all lines
            accum_height = 0    # sum heights for all lines
            for block in self._blocks:
                # each block might be wrapped onto multiple lines
                cur_line = []
                line_width = 0
                line_height = 0
                for element in block:
                    processed = False
                    while not processed:
                        rw = float('inf') if inside_size.max_width  is None else (inside_size.max_width  - line_width)
                        rh = float('inf') if inside_size.max_height is None else (inside_size.max_height - accum_height)
                        remaining = Size2D(max_width=rw, max_height=rh)
                        pos = Point2D((mbp_left + line_width, -(mbp_top + accum_height)))
                        element.layout(
                            fitting_size=remaining,
                            fitting_pos=pos,
                            parent_size=inside_size,
                            nonstatic_elem=next_nonstatic_elem,
                            document_elem=document_elem
                        )
                        w = element._dynamic_full_size.width
                        h = element._dynamic_full_size.height
                        c = element._computed_styles.get('position', 'static') not in {'absolute', 'fixed'}
                        is_good = False
                        is_good |= not cur_line                 # always add child to an empty line
                        is_good |= c and w<=rw and h<=rh        # child fits on current line
                        is_good |= not c                        # child does not contribute to our size
                        if is_good:
                            cur_line.append(element)
                            # TODO: clamp only if not scrolling!!
                            if c:
                                w,h = remaining.clamp_size(w,h)
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
                            element._dirty_flow = True
                if cur_line:
                    lines.append(cur_line)
                    accum_height += line_height
                    accum_width = max(accum_width, line_width)
            dw = accum_width + mbp_width
            dh = accum_height + mbp_height

        # possibly override with text size
        if self._children_text_min_size:
            dw = max(dw, self._children_text_min_size.width + mbp_width)
            dh = max(dh, self._children_text_min_size.height + mbp_height)
        # override with style settings
        if width      != 'auto': dw = width
        if height     != 'auto': dh = height
        if min_width  != 'auto': dw = max(min_width,  dw)
        if min_height != 'auto': dh = max(min_height, dh)
        if max_width  != 'auto': dw = min(max_width,  dw)
        if max_height != 'auto': dh = min(max_height, dh)

        self._dynamic_content_size = Size2D(width=dw-mbp_width, height=dh-mbp_height)
        self._dynamic_full_size = Size2D(width=dw, height=dh)
        self._absolute_pos = None
        self._parent_size = parent_size

        if style_pos == 'fixed':
            self._relative_element = document_elem
            self._relative_pos = Vec2D((0, 0))
        elif style_pos == 'absolute':
            self._relative_element = nonstatic_elem
            self._relative_pos = Vec2D((0, 0))
        else:
            self._relative_element = self._parent
            self._relative_pos = Vec2D(fitting_pos)

        self._dirty_flow = False

    def set_view_size(self, size:Size2D):
        # parent is telling us how big we will be.  note: this does not trigger a reflow!
        # TODO: clamp scroll
        # TODO: handle vertical and horizontal element alignment
        # TODO: handle justified and right text alignment
        self._absolute_size = size

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

    def draw(self, depth=0):
        if not self.is_visible: return

        parent_pos = self._parent.absolute_pos if self._parent else Point2D((0, self._parent_size.max_height-1))
        self._absolute_pos = parent_pos + self._relative_pos + self._scroll_offset
        self._l = int(self._absolute_pos.x)
        self._t = int(self._absolute_pos.y)
        self._w = int(self._absolute_size.width)
        self._h = int(self._absolute_size.height)

        ScissorStack.push(self._l, self._t, self._w, self._h)

        dpi_mult = Globals.drawing.get_dpi_mult()
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin', scale=dpi_mult)
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding', scale=dpi_mult)
        border_width = self._get_style_num('border-width', 0, scale=dpi_mult)

        # print(' '*(2*depth), self, self._l, self._t, self._w, self._h, self._dynamic_full_size.width, self._dynamic_full_size.height)

        if True or ScissorStack.is_visible() and ScissorStack.is_box_visible(self._l, self._t, self._w, self._h):
            # print('Drawing %s at %s' % (self._tagName, str((self._l,self._t,self._w,self._h))))
            # print('  %s:%s' % (str(self._selector),str(self._computed_styles)))
            if self._innerTextAsIs:
                pos = Point2D((self._l, self._t))
                #print('writing "%s" at %s (%f, %f)' % (self._innerTextAsIs, str(pos), self._l, self._t))
                size_prev = Globals.drawing.set_font_size(self._fontsize, fontid=self._fontid, force=True)
                Globals.drawing.text_draw2D(self._innerTextAsIs, pos, self._fontcolor)
                Globals.drawing.set_font_size(size_prev, fontid=self._fontid, force=True)
            else:
                ui_draw.draw(self._l, self._t, self._w, self._h, dpi_mult, self._computed_styles)
            for child in self._children_all: child.draw(depth+1)

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
        self._sz = None

    @property
    def body(self):
        return self._body

    def update(self, context, event):
        self.actions.update(context, event, self._timer, print_actions=True)

        mx,my = self.actions.mouse if self.actions.mouse else (0,0)
        under_mouse = self._body.get_under_mouse(mx, my)
        if self._under_mouse != under_mouse:
            # print(mx,my,under_mouse)
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
        w,h = context.region.width, context.region.height
        sz = Size2D(width=w, max_width=w, height=h, max_height=h)

        ScissorStack.start(context)
        Globals.ui_draw.update()
        bgl.glEnable(bgl.GL_BLEND)

        if (w,h) != self._sz:
            self._sz = (w,h)
            self._body.dirty('region size changed', 'size', children=True)
        self._body.clean()
        self._body.layout(fitting_size=sz, fitting_pos=Point2D((0,h-1)), parent_size=sz, nonstatic_elem=None, document_elem=self._body)
        self._body.set_view_size(sz)
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





