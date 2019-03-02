'''
Copyright (C) 2018 CG Cookie
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
from bpy.types import BoolProperty
from mathutils import Matrix

from .decorators import blender_version_wrapper
from .maths import Point2D, Vec2D, clamp, mid, Color
from .profiler import profiler
from .drawing import Drawing, ScissorStack
from .utils import iter_head
from .shaders import Shader
from .fontmanager import FontManager

from ..ext import png

major, minor, rev = bpy.app.version
blenderver = '%d.%02d' % (major, minor)
if blenderver >= '2.80':
    import gpu
    from gpu_extras.batch import batch_for_shader

debug_draw    = False   # set to True to enable debug drawing of UI (borders, padding, etc.)
debug_profile = False   # set to True to enable profiling of UI

class profiler_nop:
    def done(self): pass
def profile_fn(fn):
    global debug_profile
    if not debug_profile: return fn
    return profiler.profile(fn)
def profile_start(*args, **kwargs):
    global debug_profile
    if not debug_profile: return profiler_nop()
    return profiler.start(*args, **kwargs)


'''
TODO items:

- remove background from Container
- EqualContainer does not use visible

'''


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

def load_font_ttf(fn):
    fontid = FontManager.load(get_font_path(fn))
    FontManager.aspect(1, fontid)
    FontManager.enable_kerning_default(fontid)
    return fontid

def kwargopts(kwargs, defvals=None, **mykwargs):
    opts = defvals.copy() if defvals else {}
    opts.update(mykwargs)
    opts.update(kwargs)
    if 'opts' in kwargs: opts.update(opts['opts'])
    def factory():
        class Opts():
            ''' pretend to be a dictionary, but also add . access fns '''
            def __init__(self):
                self.touched = set()
            def __getattr__(self, opt):
                self.touched.add(opt)
                return opts[opt]
            def __getitem__(self, opt):
                self.touched.add(opt)
                return opts[opt]
            def __len__(self): return len(opts)
            def has_key(self, opt): return opt in opts
            def keys(self): return opts.keys()
            def values(self): return opts.values()
            def items(self): return opts.items()
            def __contains__(self, opt): return opt in opts
            def __iter__(self): return iter(opts)
            def print_untouched(self):
                print('untouched: %s' % str(set(opts.keys()) - self.touched))
            def pass_through(self, *args):
                return {key:self[key] for key in args}
        return Opts()
    return factory()




class GetSet:
    def __init__(self, fn_get, fn_set):
        self.fn_get = fn_get
        self.fn_set = fn_set
    def get(self): return self.fn_get()
    def set(self, v): return self.fn_set(v)


class UI_Event:
    def __init__(self, type, value):
        self.type = type
        self.value = value


'''

CookieCutter UI Styling

This styling file is formatted _very_ similarly to CSS.

Important notes/differences from CSS:

- rules are applied top-down, so any later conflicting rule will override an earlier rule
    - in other words, specificity is ignored here (https://developer.mozilla.org/en-US/docs/Web/CSS/Specificity)
- all units are in pixels; do not specify units (ex: `px`, `in`, `em`)
- colors must be specified with `rgb(<r>,<g>,<b>)` or `rgba(<r>,<g>,<b>,<a>)` or by color name
    - red, green, and blue value ranges are 0--255; alpha is 0.0--1.0
    - no `#FFFFFF` or `hsv()` colors
- all element types must be explicitly specified, except at beginning or when following a `>`; use `*` to match any type
    - ex: `elem1 .class` is the same as `elem1.class` and `elem1 . class`, but never `elem1 *.class`
- spaces are completely ignored except to separate tokens
- only `>` and ` ` combinators are implemented
- setting `width` or `height` will set both of the corresponding `min-*` and `max-*` properties
- `min-*` and `max-*` are used as suggestions to the UI system; they will not be strictly followed
- numbers cannot begin with a decimal (ex: `.014`); start with `0.` (ex: `0.014`)
- background has only color (`background: <background-color>;`)
- border has no style (`border: <border-width> <border-color>;`) and has uniform width

'''


class UI_Styling:
    class Lexer:
        def __init__(self, charstream):
            chars_ignore = ' \t\r\n'
            chars_id  = [
                'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_',
                'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
            ]
            chars_num = [
                '0123456789-',
                '0123456789.'
            ]
            keywords = [
                'auto',
                #'transparent',
                'visible',
                'hidden',
            ]
            keywords_pseudoclasses = [
                'hover',
                'active',
            ]
            keywords_colornames = {
                'transparent': (255, 0, 255, 0),

                # https://www.quackit.com/css/css_color_codes.cfm
                'indianred': (205,92,92),
                'lightcoral': (240,128,128),
                'salmon': (250,128,114),
                'darksalmon': (233,150,122),
                'lightsalmon': (255,160,122),
                'crimson': (220,20,60),
                'red': (255,0,0),
                'firebrick': (178,34,34),
                'darkred': (139,0,0),
                'pink': (255,192,203),
                'lightpink': (255,182,193),
                'hotpink': (255,105,180),
                'deeppink': (255,20,147),
                'mediumvioletred': (199,21,133),
                'palevioletred': (219,112,147),
                'coral': (255,127,80),
                'tomato': (255,99,71),
                'orangered': (255,69,0),
                'darkorange': (255,140,0),
                'orange': (255,165,0),
                'gold': (255,215,0),
                'yellow': (255,255,0),
                'lightyellow': (255,255,224),
                'lemonchiffon': (255,250,205),
                'lightgoldenrodyellow': (250,250,210),
                'papayawhip': (255,239,213),
                'moccasin': (255,228,181),
                'peachpuff': (255,218,185),
                'palegoldenrod': (238,232,170),
                'khaki': (240,230,140),
                'darkkhaki': (189,183,107),
                'lavender': (230,230,250),
                'thistle': (216,191,216),
                'plum': (221,160,221),
                'violet': (238,130,238),
                'orchid': (218,112,214),
                'fuchsia': (255,0,255),
                'magenta': (255,0,255),
                'mediumorchid': (186,85,211),
                'mediumpurple': (147,112,219),
                'blueviolet': (138,43,226),
                'darkviolet': (148,0,211),
                'darkorchid': (153,50,204),
                'darkmagenta': (139,0,139),
                'purple': (128,0,128),
                'rebeccapurple': (102,51,153),
                'indigo': (75,0,130),
                'mediumslateblue': (123,104,238),
                'slateblue': (106,90,205),
                'darkslateblue': (72,61,139),
                'greenyellow': (173,255,47),
                'chartreuse': (127,255,0),
                'lawngreen': (124,252,0),
                'lime': (0,255,0),
                'limegreen': (50,205,50),
                'palegreen': (152,251,152),
                'lightgreen': (144,238,144),
                'mediumspringgreen': (0,250,154),
                'springgreen': (0,255,127),
                'mediumseagreen': (60,179,113),
                'seagreen': (46,139,87),
                'forestgreen': (34,139,34),
                'green': (0,128,0),
                'darkgreen': (0,100,0),
                'yellowgreen': (154,205,50),
                'olivedrab': (107,142,35),
                'olive': (128,128,0),
                'darkolivegreen': (85,107,47),
                'mediumaquamarine': (102,205,170),
                'darkseagreen': (143,188,143),
                'lightseagreen': (32,178,170),
                'darkcyan': (0,139,139),
                'teal': (0,128,128),
                'aqua': (0,255,255),
                'cyan': (0,255,255),
                'lightcyan': (224,255,255),
                'paleturquoise': (175,238,238),
                'aquamarine': (127,255,212),
                'turquoise': (64,224,208),
                'mediumturquoise': (72,209,204),
                'darkturquoise': (0,206,209),
                'cadetblue': (95,158,160),
                'steelblue': (70,130,180),
                'lightsteelblue': (176,196,222),
                'powderblue': (176,224,230),
                'lightblue': (173,216,230),
                'skyblue': (135,206,235),
                'lightskyblue': (135,206,250),
                'deepskyblue': (0,191,255),
                'dodgerblue': (30,144,255),
                'cornflowerblue': (100,149,237),
                'royalblue': (65,105,225),
                'blue': (0,0,255),
                'mediumblue': (0,0,205),
                'darkblue': (0,0,139),
                'navy': (0,0,128),
                'midnightblue': (25,25,112),
                'cornsilk': (255,248,220),
                'blanchedalmond': (255,235,205),
                'bisque': (255,228,196),
                'navajowhite': (255,222,173),
                'wheat': (245,222,179),
                'burlywood': (222,184,135),
                'tan': (210,180,140),
                'rosybrown': (188,143,143),
                'sandybrown': (244,164,96),
                'goldenrod': (218,165,32),
                'darkgoldenrod': (184,134,11),
                'peru': (205,133,63),
                'chocolate': (210,105,30),
                'saddlebrown': (139,69,19),
                'sienna': (160,82,45),
                'brown': (165,42,42),
                'maroon': (128,0,0),
                'white': (255,255,255),
                'snow': (255,250,250),
                'honeydew': (240,255,240),
                'mintcream': (245,255,250),
                'azure': (240,255,255),
                'aliceblue': (240,248,255),
                'ghostwhite': (248,248,255),
                'whitesmoke': (245,245,245),
                'seashell': (255,245,238),
                'beige': (245,245,220),
                'oldlace': (253,245,230),
                'floralwhite': (255,250,240),
                'ivory': (255,255,240),
                'antiquewhite': (250,235,215),
                'linen': (250,240,230),
                'lavenderblush': (255,240,245),
                'mistyrose': (255,228,225),
                'gainsboro': (220,220,220),
                'lightgray': (211,211,211),
                'lightgrey': (211,211,211),
                'silver': (192,192,192),
                'darkgray': (169,169,169),
                'darkgrey': (169,169,169),
                'gray': (128,128,128),
                'grey': (128,128,128),
                'dimgray': (105,105,105),
                'dimgrey': (105,105,105),
                'lightslategray': (119,136,153),
                'lightslategrey': (119,136,153),
                'slategray': (112,128,144),
                'slategrey': (112,128,144),
                'darkslategray': (47,79,79),
                'darkslategrey': (47,79,79),
                'black': (0,0,0),
            }

            i_char = 0
            def nexttoken():
                nonlocal i_char, charstream
                while i_char < len(charstream) and charstream[i_char] in chars_ignore:
                    i_char += 1
                fi_char = i_char
                if i_char == len(charstream):
                    return ('eof', None, fi_char)

                if charstream[i_char] in chars_num[0]:
                    w = ''
                    while i_char < len(charstream) and charstream[i_char] in chars_num[1]:
                        w += charstream[i_char]
                        i_char += 1
                    return ('num', float(w), fi_char)

                if charstream[i_char] in chars_id[0]:
                    w = ''
                    while i_char < len(charstream) and charstream[i_char] in chars_id[1]:
                        w += charstream[i_char]
                        i_char += 1
                    if w in keywords:
                        return (w, w, fi_char)
                    if w in {'rgb','rgba'}:
                        is_rgba = (w == 'rgba')
                        assert nexttoken()[0] == '(', 'expected ( for color'
                        t,r,_ = nexttoken()
                        assert t == 'num', 'expected num for red'
                        assert nexttoken()[0] == ',', 'expected , after red'
                        t,g,_ = nexttoken()
                        assert t == 'num', 'expected num for green'
                        assert nexttoken()[0] == ',', 'expected , after green'
                        t,b,_ = nexttoken()
                        assert t == 'num', 'expected num for blue'
                        if is_rgba:
                            assert nexttoken()[0] == ',', 'expected , after blue'
                            t,a,_ = nexttoken()
                            assert t == 'num', 'expected num for alpha'
                        else:
                            a = 1.0
                        assert nexttoken()[0] == ')', 'expected ) for color'
                        return ('color', Color((r/255, g/255, b/255, a)), fi_char)
                    if w in keywords_colornames:
                        c = keywords_colornames[w]
                        if len(c) == 3:
                            r,g,b = c
                            a = 1.0
                        else:
                            r,g,b,a = c
                        return ('color', Color((r/255, g/255, b/255, a)), fi_char)
                    if w in keywords_pseudoclasses:
                        return ('pseudoclass', w, fi_char)
                    return ('id', w, fi_char)

                c = charstream[i_char]
                i_char += 1
                return (c, c, fi_char)

            self.tokens = []
            while True:
                token = nexttoken()
                if token[0] is 'eof': break
                self.tokens += [token]
            self.i = 0

        def match(self, t):
            assert self.i < len(self.tokens), 'hit end on token stream'
            token = self.tokens[self.i]
            if type(t) is str:
                assert token[0] == t, 'expected "%s" but saw "%s" (t: %s, ti: %d, ci: %d)' % (t, token[0], token[1], self.i, token[2])
            else:
                assert token[0] in t, 'expected "%s" but saw "%s" (t: %s, ti: %d, ci: %d)' % ('/'.join(t), token[0], token[1], self.i, token[2])
            self.i += 1
            return token[1]

        def next(self):
            assert self.i < len(self.tokens), 'hit end of token stream'
            token = self.tokens[self.i]
            self.i += 1
            return token[1]

        def peek(self, value=False):
            if self.i == len(self.tokens): return 'eof'
            token = self.tokens[self.i]
            return token[0 if not value else 1]

    class Declaration:
        def __init__(self, lexer):
            self.property = lexer.match('id')
            lexer.match(':')
            v = lexer.next();
            if lexer.peek() == ';':
                self.value = v
            else:
                # tuple!
                l = [v]
                while lexer.peek() != ';':
                    l.append(lexer.next())
                self.value = tuple(l)
            lexer.match(';')
        def __str__(self):
            return '<Declaration "%s=%s">' % (self.property, str(self.value))
        def __repr__(self): return self.__str__()

    class RuleSet:
        def __init__(self, lexer):
            def elem():
                if lexer.peek() not in {'.','#',':'}:
                    e = lexer.match({'id','*'})
                else:
                    e = '*'
                while lexer.peek() in {'.','#',':'}:
                    if lexer.peek() in {'.','#'}:
                        e += lexer.match({'.','#'})
                        e += lexer.match('id')
                    else:
                        e += lexer.match(':')
                        e += lexer.match('pseudoclass')
                return e

            # get selector
            self.selectors = [[]]
            while lexer.peek() != '{':
                if lexer.peek() in {'id','*'}:
                    self.selectors[-1].append(elem())
                elif lexer.peek() in {'>'}:
                    # TODO: handle + and ~ combinators?
                    sibling = lexer.match({'>'})
                    self.selectors[-1].append(sibling)
                    self.selectors[-1].append(elem())
                elif lexer.peek() == ',':
                    lexer.match(',')
                    self.selectors.append([])

            # get declarations list
            self.decllist = []
            lexer.match('{')
            while lexer.peek() != '}':
                while lexer.peek() == ';': lexer.match(';')
                if lexer.peek() == '}': break
                self.decllist.append(UI_Styling.Declaration(lexer))
            lexer.match('}')

        def __str__(self):
            s = ', '.join(' '.join(selector) for selector in self.selectors)
            if not self.decllist: return '<RuleSet "%s">' % (s,)
            return '<RuleSet "%s"\n%s\n>' % (s,'\n'.join('  '+l for d in self.decllist for l in str(d).splitlines()))
        def __repr__(self): return self.__str__()

        def match(self, selector):
            # returns true if self.selector matches passed selector
            def splitsel(sel):
                p = {'type':'', 'class':[], 'id':'', 'pseudo':[]}
                transition = {'.':'class', '#':'id', ':':'pseudo'}
                v,m = '','type'
                for c in sel:
                    if c in '.:#':
                        if type(p[m]) is list: p[m].append(v)
                        else: p[m] = v
                        v,m = '',transition[c]
                    else:
                        v += c
                if type(p[m]) is list: p[m].append(v)
                else: p[m] = v
                return p
            def msel(sa, sb, cont=True):
                if len(sa) == 0: return True
                if len(sb) == 0: return False
                a0,b0 = sa[0],sb[0]
                if b0 == '>': return msel(sa, sb[1:], cont=False)
                ap,bp = splitsel(a0),splitsel(b0)
                m = True
                m &= bp['type'] == '*' or ap['type'] == bp['type']
                m &= bp['id'] == '' or ap['id'] == bp['id']
                m &= all(c in ap['class'] for c in bp['class'])
                m &= all(c in ap['pseudo'] for c in bp['pseudo'])
                if m and msel(sa[1:], sb[1:]): return True
                if cont: return msel(sa, sb[1:])
                return False
            return any(msel(selector, sel) for sel in self.selectors)

    def __init__(self, lines):
        lines = re.sub(r'/\*[\s\S]*?\*/', '', lines)    # remove multi-line comments
        lines = re.sub(r'//.*', '', lines)              # remove single-line comments
        lexer = UI_Styling.Lexer(lines)                 # tokenize the input
        self.rules = []
        while lexer.peek() != 'eof': self.rules.append(UI_Styling.RuleSet(lexer))

    def __str__(self):
        if not self.rules: return '<UI_Styling>'
        return '<UI_Styling\n%s\n>' % ('\n'.join('  '+l for r in self.rules for l in str(r).splitlines()))

    def get_style(self, selector, override=None):
        # collect all the declarations that apply to selector
        full = [d for rule in self.rules if rule.match(selector) for d in rule.decllist]
        if override: full += override.get_style(selector)

        # expand and override declarations
        decllist = {}
        for decl in full:
            p,v = decl.property, decl.value
            if p in {'margin','padding'}:
                if type(v) is tuple:
                    if len(v) == 2:
                        decllist['%s-top'%p] = v[0]
                        decllist['%s-right'%p] = v[1]
                        decllist['%s-bottom'%p] = v[0]
                        decllist['%s-left'%p] = v[1]
                    elif len(v) == 3:
                        decllist['%s-top'%p] = v[0]
                        decllist['%s-right'%p] = v[1]
                        decllist['%s-bottom'%p] = v[2]
                        decllist['%s-left'%p] = v[1]
                    else:
                        decllist['%s-top'%p] = v[0]
                        decllist['%s-right'%p] = v[1]
                        decllist['%s-bottom'%p] = v[2]
                        decllist['%s-left'%p] = v[3]
                else:
                    decllist['%s-top'%p] = v
                    decllist['%s-right'%p] = v
                    decllist['%s-bottom'%p] = v
                    decllist['%s-left'%p] = v
            elif p == 'border':
                decllist['border-width'] = v[0]
                if len(v) == 2:
                    decllist['border-top-color'] = v[1]
                    decllist['border-right-color'] = v[1]
                    decllist['border-bottom-color'] = v[1]
                    decllist['border-left-color'] = v[1]
                elif len(v) == 3:
                    decllist['border-top-color'] = v[1]
                    decllist['border-right-color'] = v[2]
                    decllist['border-bottom-color'] = v[1]
                    decllist['border-left-color'] = v[2]
                elif len(v) == 4:
                    decllist['border-top-color'] = v[1]
                    decllist['border-right-color'] = v[2]
                    decllist['border-bottom-color'] = v[3]
                    decllist['border-left-color'] = v[2]
                else:
                    decllist['border-top-color'] = v[1]
                    decllist['border-right-color'] = v[2]
                    decllist['border-bottom-color'] = v[3]
                    decllist['border-left-color'] = v[4]
            elif p == 'border-color':
                if type(v) is tuple:
                    if len(v) == 2:
                        decllist['border-top-color'] = v[0]
                        decllist['border-right-color'] = v[1]
                        decllist['border-bottom-color'] = v[0]
                        decllist['border-left-color'] = v[1]
                    elif len(v) == 3:
                        decllist['border-top-color'] = v[0]
                        decllist['border-right-color'] = v[1]
                        decllist['border-bottom-color'] = v[2]
                        decllist['border-left-color'] = v[1]
                    else:
                        decllist['border-top-color'] = v[0]
                        decllist['border-right-color'] = v[1]
                        decllist['border-bottom-color'] = v[2]
                        decllist['border-left-color'] = v[3]
                else:
                    decllist['border-top-color'] = v
                    decllist['border-right-color'] = v
                    decllist['border-bottom-color'] = v
                    decllist['border-left-color'] = v
            elif p == 'background':
                decllist['background-color'] = v
            elif p == 'width':
                decllist['min-width'] = v
                decllist['max-width'] = v
            elif p == 'height':
                decllist['min-height'] = v
                decllist['max-height'] = v
            else:
                decllist[p] = v

        # delete properties with `initial` values
        for k in [k for (k,v) in decllist.items() if v == 'initial']:
            del decllist[k]

        return decllist


# this is just a test
path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'ui.css')
lines = open(path, 'rt').read()
styling = UI_Styling(lines)
# print(styling)
if False:
    tests = [
        ['button'],
        ['button:hover'],
        ['button.foo.bar#baz'],
        ['vertical','element:hover'],
        ['vertical','button','element'],
    ]
    for test in tests:
        print('%s' % str(test))
        print('\n'.join('   %s=%s' % (str(k),str(v)) for k,v in styling.get_style(test).items()))



class UI_Draw:
    @blender_version_wrapper('<=', '2.79')
    def init_draw(self):
        # TODO: test this implementation!
        assert False, 'function implementation not tested yet!!!'

        UI_Draw._shader = Shader.load_from_file('ui', 'uielement.glsl', checkErrors=True)

        sizeOfFloat, sizeOfInt = 4, 4

        pos = [(0,0),(1,0),(1,1),  (0,0),(1,1),(0,1)]
        count = len(pos)
        buf_pos = bgl.Buffer(bgl.GL_FLOAT, [count, 2], pos)

        vbos = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGenBuffers(1, vbos)
        vbo_pos = vbos[0]
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vbo_pos)
        bgl.glBufferData(bgl.GL_ARRAY_BUFFER, count * 2 * sizeOfFloat, buf_pos, bgl.GL_STATIC_DRAW)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)

        en = UI_Draw._shader.enable
        di = UI_Draw._shader.disable
        eva = UI_Draw._shader.vertexAttribPointer
        dva = UI_Draw._shader.disableVertexAttribArray
        a = UI_Draw._shader.assign
        def draw(left, top, width, height, style):
            nonlocal vbo_pos, count, en, di, eva, dva, a
            en()
            a('left',   left)
            a('top',    top)
            a('right',  left+width-1)
            a('bottom', top-height+1)
            a('margin_left',   style['margin-left'])
            a('margin_right',  style['margin-right'])
            a('margin_top',    style['margin-top'])
            a('margin_bottom', style['margin-bottom'])
            a('border_width',  style['border-width'])
            a('border_radius', style['border-radius'])
            a('border_left_color',   style['border-left-color'])
            a('border_right_color',  style['border-right-color'])
            a('border_top_color',    style['border-top-color'])
            a('border_bottom_color', style['border-bottom-color'])
            a('background_color',    style['background-color'])
            eva(vbo_pos, 'pos', 2, bgl.GL_FLOAT)
            bgl.glDrawArrays(bgl.GL_TRIANGLES, 0, count)
            dva('pos')
            di()
        UI_Draw._draw = draw

    @blender_version_wrapper('>=', '2.80')
    def init_draw(self):
        vertex_positions = [(0,0),(1,0),(1,1),  (1,1),(0,1),(0,0)]
        fmt = gpu.types.GPUVertFormat()
        fmt.attr_add(id="pos", comp_type='F32', len=2, fetch_mode='FLOAT')
        vbo = gpu.types.GPUVertBuf(len=len(vertex_positions), format=fmt)
        vbo.attr_fill(id="pos", data=vertex_positions)
        pos = [(0,0),(1,0),(1,1),  (1,1),(0,1),(0,0)]
        vertex_shader, fragment_shader = Shader.parse_file('uielement.glsl')
        vertex_shader = '\n'.join(vertex_shader.splitlines()[1:])
        fragment_shader = '\n'.join(fragment_shader.splitlines()[1:])
        shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
        batch = batch_for_shader(shader, 'TRIS', {"pos": pos})
        get_pixel_matrix = Drawing.get_instance().get_pixel_matrix

        def upd():
            nonlocal shader, get_pixel_matrix
            shader.bind()
            shader.uniform_float("uMVPMatrix", get_pixel_matrix())

        def draw(left, top, width, height, style):
            nonlocal shader, batch
            shader.bind()
            shader.uniform_float('left',   left)
            shader.uniform_float('top',    top)
            shader.uniform_float('right',  left+width-1)
            shader.uniform_float('bottom', top-height+1)
            shader.uniform_float('margin_left',   style['margin-left'])
            shader.uniform_float('margin_right',  style['margin-right'])
            shader.uniform_float('margin_top',    style['margin-top'])
            shader.uniform_float('margin_bottom', style['margin-bottom'])
            shader.uniform_float('border_width',  style['border-width'])
            shader.uniform_float('border_radius', style['border-radius'])
            shader.uniform_float('border_left_color',   style['border-left-color'])
            shader.uniform_float('border_right_color',  style['border-right-color'])
            shader.uniform_float('border_top_color',    style['border-top-color'])
            shader.uniform_float('border_bottom_color', style['border-bottom-color'])
            shader.uniform_float('background_color',    style['background-color'])
            batch.draw(shader)

        UI_Draw._update = upd
        UI_Draw._draw = draw

    def __init__(self):
        if not hasattr(UI_Draw, '_shader'):
            self.init_draw()

    def update(self):
        UI_Draw._update()

    def draw(self, left, top, width, height, style):
        UI_Draw._draw(left, top, width, height, style)

ui_draw = UI_Draw()
#ui_draw.draw(0, 0, 1, 1, styling.get_style(['button']))


class UI_Basic:
    selector_type = 'basic'

    def __init__(self, stylesheet=None, id=None, classes=None, style=None):
        self._parent = None
        self._selector = None
        self._stylesheet = None
        self._id = None
        self._classes = set()
        self._pseudoclasses = set()
        self._style = None
        self._style_str = ''
        self._children = []
        self._is_visible = False
        self._computed_styles = None
        self._scissor_buffer = bgl.Buffer(bgl.GL_INT, 4)

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

        self.stylesheet = stylesheet or (parent.get_stylesheet() if parent else None)
        self.style = style
        self.id = id
        self.classes = classes

        self._defer_recalc = False
        self.dirty()

    def dirty(self, parent=True, children=False):
        self._is_dirty = True
        if parent and self._parent:
            self._parent.dirty()
        if children:
            for child in self._children:
                child.dirty(parent=False, children=True)

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

    def _visible_children(self):
        return [child for child in self._children if child._is_visible]

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
        self._id = id.strip()
        self.dirty(parent=True, children=True) # changing id can affect children styles!

    @property
    def classes(self):
        return ' '.join(self._classes)
    @classes.setter
    def classes(self, classes):
        if not classes: self._classes = set()
        else: self._classes = set(c for c in classes.split(' ') if c)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def add_class(self, cls):
        if cls in self._classes: return
        self._classes.add(cls)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!
    def del_class(self, cls):
        assert cls in self._classes, 'attempting to delete class that does not exist?'
        self._classes.discard(cls)
        self.dirty(parent=True, children=True) # changing classes can affect children styles!

    def clear_pseudoclass(self):
        self._pseudoclasses = set()
        self.dirty(parent=True, children=True)
    def add_pseudoclass(self, pseudo):
        if pseudo in self._pseudoclasses: return
        self._pseudoclasses.add(pseudo)
    def del_pseudoclass(self, pseudo):
        assert pseudo in self._pseudoclasses, 'attempting to delete a pseudoclass that does not exist?'
        self._pseudoclasses.discard(pseudo)
        self.dirty(parent=True, children=True)

    def _get_style_num(self, k, def_v=0, min_v=0, max_v=None):
        v = self._computed_styles.get(k, def_v)
        if v == 'auto': v = def_v
        if min_v is not None: v = max(min_v, v)
        if max_v is not None: v = min(max_v, v)
        return v
    def _get_style_trbl(self, kb):
        t = self._get_style_num('%s-top' % kb)
        r = self._get_style_num('%s-right' % kb)
        b = self._get_style_num('%s-bottom' % kb)
        l = self._get_style_num('%s-left' % kb)
        return (t,r,b,l)

    def _recalculate(self):
        # recalculates width and height
        if not self._is_dirty: return
        if self._defer_recalc: return

        sel_parent = [] if not self._parent else self._parent._selector
        sel_type = self.selector_type
        sel_id = '#%s' % self._id if self._id else ''
        sel_cls = ''.join('.%s' % c for c in self._classes)
        sel_pseudo = ''.join(':%s' % p for p in self._pseudoclasses)
        self._selector = sel_parent + [sel_type + sel_id + sel_cls + sel_pseudo]

        self._computed_styles = self._stylesheet.get_style(self._selector, self._style)
        self._is_visible = self._computed_styles.get('visibility', 'visible') != 'hidden'
        if not self._is_visible:
            #self._min_width, self._min_height, self._max_width, self._max_height = 0,0,0,0
            self._is_dirty = False
            return

        min_width, min_height = self._get_style_num('min-width'), self._get_style_num('min-height')
        max_width, max_height = self._get_style_num('max-width', def_v=float('inf')), self._get_style_num('max-height', def_v=float('inf'))
        margin_top, margin_right, margin_bottom, margin_left = self._get_style_trbl('margin')
        padding_top, padding_right, padding_bottom, padding_left = self._get_style_trbl('padding')
        border_width = self._get_style_num('border-width')

        self._min_width  = min_width
        self._min_height = min_height
        self._max_width  = max_width
        self._max_height = max_height

        for child in self._children: child._recalculate()

        self._recalculate_children()

        # make sure there is room for margin + border + padding
        self._min_width  = (margin_left + border_width + padding_left) + self._min_width  + (padding_right  + border_width + margin_right )
        self._min_height = (margin_top  + border_width + padding_top ) + self._min_height + (padding_bottom + border_width + margin_bottom)
        self._max_width  = (margin_left + border_width + padding_left) + self._max_width  + (padding_right  + border_width + margin_right )
        self._max_height = (margin_top  + border_width + padding_top ) + self._max_height + (padding_bottom + border_width + margin_bottom)

        # do not clean self if any children are still dirty (ex: they are deferring recalculation)
        self._is_dirty = any(child._is_dirty for child in self._children)

    def _recalculate_children(self):
        # assuming all children are drawn on top on one another
        w,h = self._min_width,self._min_height
        W,H = self._max_width,self._max_height
        for child in self._visible_children():
            w = max(w, child._min_width)
            h = max(h, child._min_height)
            W = min(W, child._max_width)
            H = min(H, child._max_height)
        self._min_width,self.min_height = w,h
        self._max_width,self.max_height = W,H

    def _position(self, left, top, width, height):
        # pos and size define where this element exists
        self._l, self._t = left, top
        self._w, self._h = width, height
        # might need to wrap text
        self._position_children(left, top, width, height)
        # TODO: update self._x and self._y

    def _position_children(self, left, top, width, height):
        for child in self._visible_children():
            child._position(left, top, width, height)






class UI_Element:
    def __init__(self, margin=0, margin_left=None, margin_right=None, margin_top=None, margin_bottom=None, min_size=(0,0), max_size=None):
        self.is_dirty = True
        self.dirty_callbacks = []
        self.defer_recalc = False

        self.drawing = Drawing.get_instance()
        self.context = bpy.context
        self.last_dpi = self.drawing.get_dpi_mult()

        self._visible = None
        self._size = None
        self._width = 0
        self._height = 0
        self._margin_left = None
        self._margin_right = None
        self._margin_top = None
        self._margin_bottom = None
        self._min_size = None
        self._max_size = None

        self.pos = None
        self.size = None
        self.clip = None
        self.margin = margin
        if margin_left is not None: self.margin_left = margin_left
        if margin_right is not None: self.margin_right = margin_right
        if margin_top is not None: self.margin_top = margin_top
        if margin_bottom is not None: self.margin_bottom = margin_bottom
        self.min_size = min_size
        self.max_size = max_size
        self.visible = True
        self.scissor_buffer = bgl.Buffer(bgl.GL_INT, 4)
        self.scissor_enabled = None
        self.deleted = False

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, v):
        if self._visible == v: return
        self._visible = v
        self.dirty()

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, s):
        if self._size == s: return
        self._size = s
        self.dirty()

    @property
    def min_size(self):
        return self._min_size

    @min_size.setter
    def min_size(self, v):
        vx, vy = v
        vx, vy = max(0, vx), max(0, vy)
        if self._min_size and self._min_size.x == vx and self._min_size.y == vy: return
        self._min_size = Vec2D((vx, vy))
        self.dirty()

    @property
    def max_size(self):
        return self._max_size

    @max_size.setter
    def max_size(self, v):
        if v is None:
            if self._max_size is None: return
            self._max_size = v
        else:
            vx, vy = v
            if self._max_size and self._max_size.x == vx and self._max_size.y == vy: return
            self._max_size = Vec2D((vx, vy))
        self.dirty()

    @property
    def margin(self):
        return max(self._margin_left, self._margin_right, self._margin_top, self._margin_bottom)

    @margin.setter
    def margin(self, v):
        v = max(0, v)
        if self._margin_left == v and self._margin_right == v and self._margin_top == v and self._margin_bottom == v: return
        self._margin_left = v
        self._margin_right = v
        self._margin_top = v
        self._margin_bottom = v
        self.dirty()

    @property
    def margin_left(self):
        return self._margin_left

    @margin_left.setter
    def margin_left(self, v):
        v = max(0, v)
        if self._margin_left == v: return
        self._margin_left = v
        self.dirty()

    @property
    def margin_right(self):
        return self._margin_right

    @margin_right.setter
    def margin_right(self, v):
        v = max(0, v)
        if self._margin_right == v: return
        self._margin_right = v
        self.dirty()

    @property
    def margin_top(self):
        return self._margin_top

    @margin_top.setter
    def margin_top(self, v):
        v = max(0, v)
        if self._margin_top == v: return
        self._margin_top = v
        self.dirty()

    @property
    def margin_bottom(self):
        return self._margin_bottom

    @margin_bottom.setter
    def margin_bottom(self, v):
        v = max(0, v)
        if self._margin_bottom == v: return
        self._margin_bottom = v
        self.dirty()

    def register_dirty_callback(self, ui_item):
        self.dirty_callbacks.append(ui_item)

    def unregister_dirty_callback(self, ui_item):
        self.dirty_callbacks = [ui for ui in self.dirty_callbacks if ui != ui_item]

    def dirty(self):
        # print('Marking %s as dirty' % type(self))
        # if type(self) is UI_Label: print('  %s' % self.text)
        self.is_dirty = True
        for ui_item in self.dirty_callbacks:
            ui_item.dirty()

    def delete(self):
        self.deleted = True
        self._delete()
        self.dirty()

    def hover_ui(self, mouse):
        if self.clip:
            cl,ct,cw,ch = self.clip
            cr,cb = cl+cw, ct-ch
            mx,my = mouse
            if mx < cl or mx > cr or my > ct or my < cb: return None
        return self._hover_ui(mouse)
    def _hover_ui(self, mouse): return self.__hover_ui(mouse)
    def __hover_ui(self, mouse):
        if not self.visible: return None
        if not self.pos or not self.size: return None
        x,y = mouse
        l,t = self.pos
        w,h = self.size
        if x < l or x >= l + w: return None
        if y > t or y <= t - h: return None
        return self

    #@profiler.profile
    def draw(self, left, top, width, height):
        if not self.visible: return

        if self.last_dpi != self.drawing.get_dpi_mult():
            self.last_dpi = self.drawing.get_dpi_mult()
            self.dirty()

        ml = self.drawing.scale(self._margin_left)
        mr = self.drawing.scale(self._margin_right)
        mt = self.drawing.scale(self._margin_top)
        mb = self.drawing.scale(self._margin_bottom)

        self.pos = Point2D((left + ml, top - mt))
        self.size = Vec2D((width - ml - mr, height - mt - mb))
        self.pos0 = Point2D((left, top))
        self.size0 = Vec2D((width, height))
        self.clip = ScissorStack.get_current_view()

        if debug_draw:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glColor4f(1,0,0,0.5)
            bgl.glVertex2f(left, top)
            bgl.glVertex2f(left, top - height)
            bgl.glVertex2f(left + ml, top - height + mb)
            bgl.glVertex2f(left + ml, top - mt)

            bgl.glColor4f(0,1,0,0.5)
            bgl.glVertex2f(left, top - height)
            bgl.glVertex2f(left + width, top - height)
            bgl.glVertex2f(left + width - mr, top - height + mb)
            bgl.glVertex2f(left + ml, top - height + mb)

            bgl.glColor4f(0,0,1,0.5)
            bgl.glVertex2f(left + width, top - height)
            bgl.glVertex2f(left + width, top)
            bgl.glVertex2f(left + width - mr, top - mt)
            bgl.glVertex2f(left + width - mr, top - height + mb)

            bgl.glColor4f(1,0,1,0.5)
            bgl.glVertex2f(left + width, top)
            bgl.glVertex2f(left, top)
            bgl.glVertex2f(left + ml, top - mt)
            bgl.glVertex2f(left + width - mr, top - mt)
            bgl.glEnd()

        ScissorStack.push(self.pos, self.size)
        self.predraw()
        if ScissorStack.is_visible() and ScissorStack.is_box_visible(*self.pos, *self.size):
            self._draw()
        ScissorStack.pop()

    @profiler.profile
    def recalc_size(self):
        if not self.is_dirty: return (self._width, self._height)
        if self.defer_recalc: return (self._width, self._height)

        self._width, self._height = 0, 0
        self._width_inner, self._height_inner = 0, 0
        if not self.visible: return (self._width, self._height)

        pr = profiler.start('UI_Element: calling _recalc_size on %s' % str(type(self)))
        self._recalc_size()

        self._width_inner = max(self._min_size.x, self._width_inner)
        self._height_inner = max(self._min_size.y, self._height_inner)
        if self._max_size:
            self._width_inner = min(self._max_size.x, self._width_inner)
            self._height_inner = min(self._max_size.y, self._height_inner)

        pr.done()
        if self._width_inner <= 0 or self._height_inner <= 0:
            return (self._width, self._height)
        self._width = self._width_inner + self.drawing.scale(self._margin_left + self._margin_right)
        self._height = self._height_inner + self.drawing.scale(self._margin_top + self._margin_bottom)

        self.is_dirty = False
        return (self._width, self._height)

    def find_rel_pos_size(self, ui_item):
        if self == ui_item: return (0, 0, self._width, self._height)
        pos_size = self._find_rel_pos_size(ui_item)
        if not pos_size: return pos_size
        x, y, w, h = pos_size
        return (self._margin_left + x, self._margin_top + y, w, h)
    def _find_rel_pos_size(self, ui_item):
        return None

    def get_width(self): return self._width if self.visible else 0
    def get_height(self): return self._height if self.visible else 0
    def get_inner_width(self): return self._width_inner if self.visible else 0
    def get_inner_height(self): return self._height_inner if self.visible else 0

    def _delete(self): return
    def _recalc_size(self): pass
    def predraw(self): pass
    def _draw(self): pass
    def mouse_enter(self): pass
    def mouse_leave(self): pass
    def mouse_down(self, mouse): pass
    def mouse_move(self, mouse): pass
    def mouse_up(self, mouse): pass
    def mouse_cancel(self): pass
    def capture_start(self): pass
    def capture_event(self, event): pass

    def _get_tooltip(self, mouse): pass

    def mouse_cursor(self): return 'DEFAULT'


class UI_Padding(UI_Element):
    def __init__(self, ui_item=None, margin=5, margin_left=None, margin_right=None, min_size=(0,0), max_size=None):
        self.ui_item = None

        super().__init__(margin=margin, margin_left=margin_left, margin_right=margin_right, min_size=min_size, max_size=max_size)
        self.defer_recalc = True
        self.set_ui_item(ui_item)
        self.defer_recalc = False

    def _find_rel_pos_size(self, ui_item):
        if self.ui_item == None: return None
        return self.ui_item.find_rel_pos_size(ui_item)

    def set_ui_item(self, ui_item):
        if self.ui_item == ui_item: return
        if self.ui_item:
            self.ui_item.unregister_dirty_callback(self)
        self.ui_item = ui_item
        if self.ui_item:
            self.ui_item.register_dirty_callback(self)
        self.dirty()
        return self.ui_item

    def _delete(self):
        if self.ui_item:
            self.ui_item.unregister_dirty_callback(self)

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        ui = None if not self.ui_item else self.ui_item.hover_ui(mouse)
        return ui or self

    def _recalc_size(self):
        if not self.ui_item or not self.ui_item.visible:
            self._width_inner, self._height_inner = 0, 0
        else:
            self._width_inner, self._height_inner = self.ui_item.recalc_size()

    @profiler.profile
    def _draw(self):
        if not self.ui_item or not self.ui_item.visible: return
        l,t = self.pos
        w,h = self.size
        self.ui_item.draw(l,t,w,h)


class UI_Background(UI_Element):
    def __init__(self, background=None, rounded=False, border=None, border_thickness=1, ui_item=None, margin=0):
        super().__init__(margin=margin)
        self.defer_recalc = True

        self.ui_item = None

        self.background = background
        self.rounded_background = rounded
        self.border = border
        # TODO: should border_thickness add to margin?
        self.border_thickness = 0
        self.set_ui_item(ui_item)

        self.defer_recalc = False

    def set_ui_item(self, ui_item):
        if self.ui_item == ui_item: return
        if self.ui_item:
            self.ui_item.unregister_dirty_callback(self)
        self.ui_item = ui_item
        if self.ui_item:
            self.ui_item.register_dirty_callback(self)
        self.dirty()
        return self.ui_item

    def _delete(self):
        if self.ui_item:
            self.ui_item.unregister_dirty_callback(self)

    def _find_rel_pos_size(self, ui_item):
        if self.ui_item == None: return None
        return self.ui_item.find_rel_pos_size(ui_item)

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        ui = None if not self.ui_item else self.ui_item.hover_ui(mouse)
        return ui or self

    def _recalc_size(self):
        if not self.ui_item or not self.ui_item.visible:
            self._width_inner, self._height_inner = 0, 0
        else:
            self._width_inner, self._height_inner = self.ui_item.recalc_size()

    @profiler.profile
    def _draw(self):
        if not self.ui_item or not self.ui_item.visible: return
        l,t = self.pos
        w,h = self.size

        bgl.glEnable(bgl.GL_BLEND)

        if self.background:
            bgl.glColor4f(*self.background)
            bgl.glBegin(bgl.GL_QUADS)
            if self.rounded_background:
                bgl.glVertex2f(l+1, t)
                bgl.glVertex2f(l+w-1, t)
                bgl.glVertex2f(l+w-1, t-h)
                bgl.glVertex2f(l+1, t-h)

                bgl.glVertex2f(l, t-1)
                bgl.glVertex2f(l+1, t-1)
                bgl.glVertex2f(l+1, t-h+1)
                bgl.glVertex2f(l, t-h+1)

                bgl.glVertex2f(l+w-1, t-1)
                bgl.glVertex2f(l+w, t-1)
                bgl.glVertex2f(l+w, t-h+1)
                bgl.glVertex2f(l+w-1, t-h+1)
            else:
                bgl.glVertex2f(l, t)
                bgl.glVertex2f(l+w, t)
                bgl.glVertex2f(l+w, t-h)
                bgl.glVertex2f(l, t-h)
            bgl.glEnd()
        if self.border:
            bgl.glColor4f(*self.border)
            self.drawing.line_width(self.border_thickness)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            if self.rounded_background:
                bgl.glVertex2f(l+1,t)
                bgl.glVertex2f(l,t-1)
                bgl.glVertex2f(l,t-h+1)
                bgl.glVertex2f(l+1,t-h)
                bgl.glVertex2f(l+w-1,t-h)
                bgl.glVertex2f(l+w,t-h+1)
                bgl.glVertex2f(l+w,t-1)
                bgl.glVertex2f(l+w-1,t)
                bgl.glVertex2f(l+1,t)
            else:
                bgl.glVertex2f(l,t)
                bgl.glVertex2f(l,t-h)
                bgl.glVertex2f(l+w,t-h)
                bgl.glVertex2f(l+w,t)
                bgl.glVertex2f(l,t)
            bgl.glEnd()

        self.ui_item.draw(l,t,w,h)


class UI_VScrollable(UI_Padding):
    def __init__(self, ui_item=None, margin=0, min_size=(0,0), max_size=None):
        super().__init__(margin=margin, min_size=min_size, max_size=max_size)
        self.defer_recalc = True
        self.set_ui_item(ui_item)
        self.defer_recalc = False

    def set_ui_item(self, ui_item):
        super().set_ui_item(ui_item)
        self.offset = 0
        return self.ui_item

    def _find_rel_pos_size(self, ui_item):
        if self.ui_item == None: return None
        return self.ui_item.find_rel_pos_size(ui_item)

    def scroll_to_top(self):
        self.offset = 0

    def scroll_to_bottom(self):
        self.offset = self.get_height()

    # def _hover_ui(self, mouse):
    #     if not super()._hover_ui(mouse): return None
    #     ui = None if not self.ui_item else self.ui_item.hover_ui(mouse)
    #     return ui or self

    # def _recalc_size(self):
    #     if not self.ui_item:
    #         self._width_inner, self._height_inner = 0, 0
    #     else:
    #         self._width_inner, self._height_inner = self.ui_item.recalc_size()

    def predraw(self):
        if self.offset == 0: return
        sl,st,sw,sh = ScissorStack.get_current_view()
        ah = self.get_height()
        self.offset = mid(self.offset, 0, ah - sh)

    @profiler.profile
    def _draw(self):
        if not self.ui_item or not self.ui_item.visible: return

        l,t = self.pos
        w,h = self.size
        sl,st,sw,sh = ScissorStack.get_current_view()
        ah = self.get_height()
        aih = self.get_inner_height()

        self.ui_item.draw(l,t+self.offset,w,ah)

        # draw fade bars at top and bottom if contents extend beyond scissor
        #print(ah, sh, ah / sh)
        bars_show = (ah / sh > 1.0)
        bar_top = (self.offset > 0)
        bar_bot = (self.offset < ah - sh - 1)
        if bars_show and (bar_top or bar_bot):
            s = self.drawing.scale(30)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBegin(bgl.GL_QUADS)
            if bar_top:
                bgl.glColor4f(0.25, 0.30, 0.35, 1.00)
                bgl.glVertex2f(sl+sw, st+1)
                bgl.glVertex2f(sl, st+1)
                bgl.glColor4f(0.25, 0.30, 0.35, 0.00)
                bgl.glVertex2f(sl, st-s)
                bgl.glVertex2f(sl+sw, st-s)
            if bar_bot:
                bgl.glColor4f(0.25, 0.30, 0.35, 1.00)
                bgl.glVertex2f(sl, st-sh)
                bgl.glVertex2f(sl+sw, st-sh)
                bgl.glColor4f(0.25, 0.30, 0.35, 0.00)
                bgl.glVertex2f(sl+sw, st-sh+s)
                bgl.glVertex2f(sl, st-sh+s)
            bgl.glEnd()


class UI_Spacer(UI_Element):
    def __init__(self, width=1, height=1, background=None):
        super().__init__()
        self.defer_recalc = True

        self._spacer_width = None
        self._spacer_height = None

        self.width = width
        self.height = height
        self.margin = 0
        self.background = background

        self.defer_recalc = False

    @property
    def width(self):
        return self._spacer_width

    @width.setter
    def width(self, w):
        w = max(0, w)
        if self._spacer_width == w: return
        self._spacer_width = w
        self.dirty()

    @property
    def height(self):
        return self._spacer_height

    @height.setter
    def height(self, h):
        h = max(0, h)
        if self._spacer_height == h: return
        self._spacer_height = h
        self.dirty()

    def _recalc_size(self):
        self._width_inner = self.drawing.scale(self.width)
        self._height_inner = self.drawing.scale(self.height)

    def _draw(self):
        l,t = self.pos
        w,h = self.size

        if debug_draw:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glColor4f(0,1,1,0.5)
            bgl.glVertex2f(l, t)
            bgl.glVertex2f(l, t - h)
            bgl.glVertex2f(l + w, t - h)
            bgl.glVertex2f(l + w, t)
            bgl.glEnd()

        if self.background:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*self.background)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l, t)
            bgl.glVertex2f(l+w, t)
            bgl.glVertex2f(l+w, t-h)
            bgl.glVertex2f(l, t-h)
            bgl.glEnd()


class UI_Rule(UI_Element):
    def __init__(self, thickness=2, padding=0, color=(1.0,1.0,1.0,0.25)):
        super().__init__(margin=0)
        self.defer_recalc = True

        self._padding = None
        self._thickness = None

        self.thickness = thickness
        self.color = color
        self.padding = padding

        self.defer_recalc = False

    @property
    def padding(self):
        return self._padding

    @padding.setter
    def padding(self, p):
        p = max(0, p)
        if p == self._padding: return
        self._padding = p
        self.dirty()

    @property
    def thickness(self):
        return self._thickness

    @thickness.setter
    def thickness(self, t):
        t = max(0, t)
        if self._thickness == t: return
        self._thickness = t
        self.dirty()

    def _recalc_size(self):
        self._width_inner = self.drawing.scale(self.padding*2 + 1)
        self._height_inner = self.drawing.scale(self.padding*2 + self.thickness)

    @profiler.profile
    def _draw(self):
        left,top = self.pos
        width,height = self.size
        t2 = round(self.thickness/2)
        padding = self.padding
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*self.color)
        self.drawing.line_width(self.thickness)
        bgl.glBegin(bgl.GL_LINES)
        bgl.glVertex2f(left+padding, top-padding-t2)
        bgl.glVertex2f(left+width-padding, top-padding-t2)
        bgl.glEnd()


class UI_Container(UI_Element):
    def __init__(self, vertical=True, background=None, margin=0, separation=2, min_size=(0,0)):
        self._vertical = None
        self._separation = None

        super().__init__(margin=margin, min_size=min_size)
        self.defer_recalc = True

        self.vertical = vertical
        self.ui_items = []
        self.background = background
        self.rounded_background = False
        self.separation = separation

        self.defer_recalc = False

    @property
    def vertical(self):
        return self._vertical

    @vertical.setter
    def vertical(self, v):
        if self._vertical == v: return
        self._vertical = v
        self.dirty()

    @property
    def separation(self):
        return self._separation

    @separation.setter
    def separation(self, s):
        s = max(0, s)
        if self._separation == s: return
        self._separation = s
        self.dirty()

    def _delete(self):
        for ui_item in self.ui_items:
            ui_item.unregister_dirty_callback(self)

    def add(self, ui_item):
        self.ui_items.append(ui_item)
        ui_item.register_dirty_callback(self)
        self.dirty()
        return ui_item

    def clear(self):
        for ui_item in self.ui_items:
            ui_item.unregister_dirty_callback(self)
        self.ui_items = []

    def _find_rel_pos_size(self, ui_item):
        oy = 0
        for my_ui_item in self.ui_items:
            res = my_ui_item.find_rel_pos_size(ui_item)
            if res:
                x,y,w,h = res
                return (x,y+oy,w,h)
            oy += my_ui_item.get_height()
        return None

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        for ui in self.ui_items:
            hover = ui.hover_ui(mouse)
            if hover: return hover
        return self

    def _recalc_size(self):
        sizes = [ui_item.recalc_size() for ui_item in self.ui_items if ui_item.visible]
        #sizes = [sz for (sz,ui_item) in zip(sizes, self.ui_items) if ui_item.visible]
        sizes = [(w,h) for (w,h) in sizes if w > 0 and h > 0]
        widths = [w for (w,h) in sizes]
        heights = [h for (w,h) in sizes]
        c = len(sizes)
        if c == 0:
            self._width, self._height = 0, 0
            self._width_inner, self._height_inner = 0, 0
            return
        sep = self.drawing.scale(self.separation)
        if self.vertical:
            self._width_inner = max(widths)
            self._height_inner = sum(heights) + (sep * max(0,c-1))
        else:
            self._width_inner = sum(widths) + (sep * max(0,c-1))
            self._height_inner = max(heights)

    @profiler.profile
    def _draw(self):
        l,t = self.pos
        w,h = self.size
        sep = self.drawing.scale(self.separation)

        if self.background:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*self.background)
            bgl.glBegin(bgl.GL_QUADS)
            if self.rounded_background:
                bgl.glVertex2f(l+1, t)
                bgl.glVertex2f(l+w-1, t)
                bgl.glVertex2f(l+w-1, t-h)
                bgl.glVertex2f(l+1, t-h)

                bgl.glVertex2f(l, t-1)
                bgl.glVertex2f(l+1, t-1)
                bgl.glVertex2f(l+1, t-h+1)
                bgl.glVertex2f(l, t-h+1)

                bgl.glVertex2f(l+w-1, t-1)
                bgl.glVertex2f(l+w, t-1)
                bgl.glVertex2f(l+w, t-h+1)
                bgl.glVertex2f(l+w-1, t-h+1)
            else:
                bgl.glVertex2f(l, t)
                bgl.glVertex2f(l+w, t)
                bgl.glVertex2f(l+w, t-h)
                bgl.glVertex2f(l, t-h)
            bgl.glEnd()

        if self.vertical:
            pr = profiler.start('vertical')
            y = t
            ui_items = [ui for ui in self.ui_items if ui.get_height() > 0]
            last = len(ui_items) - 1
            for i,ui in enumerate(ui_items):
                eh = ui.get_height() if i < last else h
                if debug_draw and 0 < i < last:
                    bgl.glEnable(bgl.GL_BLEND)
                    bgl.glBegin(bgl.GL_QUADS)
                    bgl.glColor4f(1,1,1,0.5)
                    bgl.glVertex2f(l,y+sep)
                    bgl.glVertex2f(l,y)
                    bgl.glVertex2f(l+w,y)
                    bgl.glVertex2f(l+w,y+sep)
                    bgl.glEnd()
                ui.draw(l,y,w,eh)
                y -= eh + sep
                h -= eh + sep
            pr.done()
        else:
            pr = profiler.start('horizontal')
            x = l
            ui_items = [ui for ui in self.ui_items if ui.get_width() > 0]
            last = len(ui_items) - 1
            for i,ui in enumerate(ui_items):
                ew = ui.get_width() if i < last else w
                ui.draw(x,t,ew,h)
                x += ew + sep
                w -= ew + sep
            pr.done()

    def get_ui_items(self):
        return list(self.ui_items)


class UI_EqualContainer(UI_Container):
    def __init__(self, vertical=True, margin=0):
        super().__init__(vertical=vertical, margin=margin)

    @profiler.profile
    def _draw(self):
        if len(self.ui_items) == 0: return
        l,t = self.pos
        w,h = self.size
        if self.vertical:
            y = t
            ui_items = [ui for ui in self.ui_items if ui.get_height() > 0]
            eh = math.floor(h / len(ui_items))
            for ui in ui_items:
                ui.draw(l,y,w,eh)
                y -= eh
        else:
            x = l
            ui_items = [ui for ui in self.ui_items if ui.get_width() > 0]
            ew = math.floor(w / len(ui_items))
            for ui in ui_items:
                ui.draw(x,t,ew,h)
                x += ew


class UI_Label(UI_Element):
    def __init__(self, label, icon=None, tooltip=None, color=(1,1,1,1), bgcolor=None, align=-1, valign=-1, fontsize=12, shadowcolor=None, margin=2, min_size=(0,0)):
        self.text = None
        self._fontsize = None
        self._icon = None

        super().__init__(margin=margin, min_size=min_size)
        self.defer_recalc = True

        self.icon = icon
        self.tooltip = tooltip
        self.color = color
        self.shadowcolor = shadowcolor
        self.align = align
        self.valign = valign
        self.fontsize = fontsize
        self.set_label(label)
        self.set_bgcolor(bgcolor)
        self.cursor_pos = None
        self.cursor_symbol = None
        self.cursor_color = (0.1,0.7,1,1)

        self.defer_recalc = False

    @property
    def fontsize(self):
        return self._fontsize

    @fontsize.setter
    def fontsize(self, f):
        f = max(1, f)
        if self._fontsize == f: return
        self._fontsize = f
        self.dirty()

    @property
    def icon(self):
        return self._icon

    @icon.setter
    def icon(self, i):
        if self._icon == i: return
        self._icon = i
        self.dirty()

    def set_bgcolor(self, bgcolor): self.bgcolor = bgcolor

    def get_label(self): return self.text

    @profiler.profile
    def set_label(self, label):
        label = str(label)
        if self.text == label: return
        self.text = label
        self.dirty()

    def _recalc_size(self):
        fontsize_prev = self.drawing.set_font_size(self.fontsize)
        self.text_width = self.drawing.get_text_width(self.text)
        self.text_height = self.drawing.get_line_height(self.text)
        self.drawing.set_font_size(fontsize_prev)
        self._width_inner = self.text_width
        self._height_inner = self.text_height

    def _get_tooltip(self, mouse): return self.tooltip

    @profiler.profile
    def _draw(self):
        l,t = self.pos
        w,h = self.size

        if self.bgcolor:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*self.bgcolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        if self.align < 0: loc_x = l
        elif self.align > 0: loc_x = l + w - self.text_width
        else: loc_x = l + (w - self.text_width) / 2

        if self.valign < 0: loc_y = t
        elif self.valign > 0: loc_f = t - h + self.text_height
        else: loc_y = t - (h - self.text_height) / 2

        size_prev = self.drawing.set_font_size(self.fontsize)

        if self.shadowcolor:
            self.drawing.text_draw2D(self.text, Point2D((loc_x+2, loc_y-2)), self.shadowcolor)

        self.drawing.text_draw2D(self.text, Point2D((loc_x, loc_y)), self.color)

        if self.cursor_pos is not None and self.cursor_symbol:
            pre = self.drawing.get_text_width(self.text[:self.cursor_pos])
            cwid = self.drawing.get_text_width(self.cursor_symbol)
            cloc = Point2D((loc_x+pre-cwid/2, loc_y))
            self.drawing.text_draw2D(self.cursor_symbol, cloc, self.cursor_color)

        self.drawing.set_font_size(size_prev)


class UI_WrappedLabel(UI_Element):
    '''
    Handles text wrapping
    '''
    def __init__(self, label, color=(1,1,1,1), min_size=(0, 0), max_size=(600, 36000), fontsize=12, bgcolor=None, margin=0, shadowcolor=None):
        super().__init__(margin=margin, min_size=min_size, max_size=max_size)
        self.defer_recalc = True

        self._fontsize = None
        self.text = None

        self.fontsize = fontsize
        self.set_label(label)
        self.set_bgcolor(bgcolor)
        self.color = color
        self.shadowcolor = shadowcolor
        self.wrapped_size = Vec2D(max_size)

        self.defer_recalc = False

    @property
    def fontsize(self):
        return self._fontsize

    @fontsize.setter
    def fontsize(self, f):
        f = max(1, f)
        if self._fontsize == f: return
        self._fontsize = f
        self.dirty()

    def set_bgcolor(self, bgcolor): self.bgcolor = bgcolor

    def set_label(self, label):
        # process message similarly to Markdown
        label = str(label)
        label = re.sub(r'^\n*', r'', label)                 # remove leading \n
        label = re.sub(r'\n*$', r'', label)                 # remove trailing \n
        label = re.sub(r'\n\n\n*', r'\n\n', label)          # 2+ \n => \n\n
        paras = label.split('\n\n')                         # split into paragraphs
        paras = [re.sub(r'\n', '  ', p) for p in paras]     # join sentences of paragraphs
        label = '\n\n'.join(paras)                          # join paragraphs

        if self.text == label: return

        self.text = label
        self.dirty()

    def predraw(self):
        # TODO: move code below to _recalc_size?

        size_prev = self.drawing.set_font_size(self.fontsize)
        mwidth = self.size.x
        twidth = self.drawing.get_text_width
        swidth = twidth(' ')
        wrapped = []
        def wrap(t):
            words = t.split(' ')
            words.reverse()
            lines = []
            line = []
            while words:
                word = words.pop()
                nline = line + [word]
                if line and twidth(' '.join(nline)) >= mwidth:
                    lines.append(' '.join(line))
                    line = [word]
                else:
                    line = nline
            lines.append(' '.join(line))
            return lines
        lines = self.text.split('\n')
        self.wrapped_lines = [wrapped_line for line in lines for wrapped_line in wrap(line)]
        w = twidth(self.wrapped_lines) #max(twidth(l) for l in self.wrapped_lines)
        h = self.drawing.get_line_height(self.wrapped_lines)
        self.wrapped_size = Vec2D((w, h))

        self.drawing.set_font_size(size_prev)

    def _recalc_size(self):
        self._width_inner = max(self.wrapped_size.x, self.drawing.scale(self.max_size.x))
        self._height_inner = self.wrapped_size.y

    @profiler.profile
    def _draw(self):
        size_prev = self.drawing.set_font_size(self.fontsize)
        line_height = self.drawing.get_line_height()

        l,t = self.pos
        w,h = self.size
        twidth = self.drawing.get_text_width
        theight = self.drawing.get_text_height

        if self.bgcolor:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*self.bgcolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        y = t
        for line in self.wrapped_lines:
            lheight = theight(line)
            if self.shadowcolor:
                self.drawing.text_draw2D(line, Point2D((l+2, y-2)), self.shadowcolor)
            self.drawing.text_draw2D(line, Point2D((l, y)), self.color)
            y -= self.drawing.get_line_height(line) #line_height #lheight

        self.drawing.set_font_size(size_prev)


class UI_Markdown(UI_Padding):
    def __init__(self, markdown, min_size=(0, 36), max_size=(600, 36000), margin=0, margin_left=None, margin_right=None):
        self._markdown = None

        super().__init__(margin=margin, margin_left=margin_left, margin_right=margin_right, min_size=min_size, max_size=max_size)
        self.defer_recalc = True

        #self.max_size = self.drawing.scale(Vec2D(max_size))
        self.set_markdown(markdown)

        self.defer_recalc = False

    def set_markdown(self, mdown):
        # process message similarly to Markdown
        mdown = re.sub(r'^\n*', r'', mdown)                 # remove leading \n
        mdown = re.sub(r'\n*$', r'', mdown)                 # remove trailing \n
        mdown = re.sub(r'\n\n\n*', r'\n\n', mdown)          # 2+ \n => \n\n

        if mdown == self._markdown: return
        self._markdown = mdown

        paras = mdown.split('\n\n')                         # split into paragraphs

        container = UI_Container(margin=4)
        for p in paras:
            if p.startswith('# '):
                # h1 heading!
                h1text = re.sub(r'# +', r'', p)
                container.add(UI_Spacer(height=4))
                h1 = container.add(UI_WrappedLabel(h1text, fontsize=20, shadowcolor=(0,0,0,0.5)))
                container.add(UI_Spacer(height=14))
            elif p.startswith('## '):
                # h2 heading!
                h2text = re.sub(r'## +', r'', p)
                container.add(UI_Spacer(height=8))
                h2 = container.add(UI_WrappedLabel(h2text, fontsize=16, shadowcolor=(0,0,0,0.5)))
                container.add(UI_Spacer(height=4))
            elif p.startswith('- '):
                # unordered list!
                ul = container.add(UI_Container())
                for litext in p.split('\n'):
                    litext = re.sub(r'- ', r'', litext)
                    li = ul.add(UI_Container(margin=0, vertical=False))
                    li.add(UI_Label('-')).margin=0
                    li.add(UI_Spacer(width=8))
                    li.add(UI_WrappedLabel(litext, max_size=self.max_size)).margin=0
            elif p.startswith('!['):
                # image!
                m = re.match(r'^!\[(?P<caption>.*)\]\((?P<filename>.*)\)$', p)
                fn = m.group('filename')
                img = container.add(UI_Image(fn))
            elif p.startswith('| '):
                # table
                data = [l for l in p.split('\n')]
                data = [re.sub(r'^\| ', r'', l) for l in data]
                data = [re.sub(r' \|$', r'', l) for l in data]
                data = [l.split(' | ') for l in data]
                rows,cols = len(data),len(data[0])
                t = container.add(UI_TableContainer(rows, cols))
                for r in range(rows):
                    for c in range(cols):
                        if c == 0:
                            t.set(r, c, UI_Label(data[r][c]))
                        else:
                            t.set(r, c, UI_WrappedLabel(data[r][c], min_size=(0, 12), max_size=(400, 12000)))
            else:
                p = re.sub(r'\n', '  ', p)      # join sentences of paragraph
                container.add(UI_WrappedLabel(p, max_size=self.max_size))
        self.set_ui_item(container)

class UI_OnlineMarkdown(UI_Markdown):
    def __init__(self, url, min_size=(0, 36), max_size=(600, 36000), margin=4):
        super().__init__(margin=margin, min_size=min_size, max_size=max_size)
        self.defer_recalc = True

        response = urllib.request.urlopen(url)
        data = response.read()
        text = data.decode('utf-8')

        markdown = text

        self.set_markdown(markdown)

        self.defer_recalc = False

class UI_Button(UI_Container):
    def __init__(self, label, fn_callback, icon=None, tooltip=None, color=(1,1,1,1), align=0, bgcolor=None, bordercolor=(0,0,0,0.4), hovercolor=(1,1,1,0.1), presscolor=(0,0,0,0.2), margin=0, padding=4):
        super().__init__(vertical=False, margin=margin)
        self.defer_recalc = True
        if icon:
            self.add(icon)
            self.add(UI_Spacer(width=4))
        self.tooltip = tooltip
        self.label = self.add(UI_Label(label, color=color, align=align, margin=padding))
        self.fn_callback = fn_callback
        self.pressed = False
        self.bgcolor = bgcolor
        self.bordercolor = bordercolor
        self.presscolor = presscolor
        self.hovercolor = hovercolor
        self.mouse = None
        self.hovering = False
        self.defer_recalc = False

    def get_label(self): return self.label.get_label()
    def set_label(self, label): self.label.set_label(label)

    def mouse_enter(self):
        self.hovering = True
    def mouse_leave(self):
        self.hovering = False
    def mouse_down(self, mouse):
        self.pressed = True
    def mouse_move(self, mouse):
        self.mouse = mouse
        self.pressed = self.hover_ui(mouse) is not None
    def mouse_up(self, mouse):
        if self.pressed: self.fn_callback()
        self.pressed = False

    def _hover_ui(self, mouse):
        #return self if self.hovering else None
        return self if super()._hover_ui(mouse) else None

    def mouse_cursor(self): return 'DEFAULT'

    @profiler.profile
    def _draw(self):
        l,t = self.pos
        w,h = self.size
        bgl.glEnable(bgl.GL_BLEND)
        self.drawing.line_width(1)

        if self.hovering:
            bgcolor = self.hovercolor or self.bgcolor
        else:
            bgcolor = self.bgcolor

        if bgcolor:
            bgl.glColor4f(*bgcolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        if self.pressed and self.presscolor:
            bgl.glColor4f(*self.presscolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        if self.bordercolor:
            bgl.glColor4f(*self.bordercolor)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glVertex2f(l,t)
            bgl.glEnd()

        super()._draw()

    def _get_tooltip(self, mouse): return self.tooltip


class UI_Options(UI_Container):
    color_select = (0.27, 0.50, 0.72, 0.90)
    color_unselect = None
    color_hover = (1.00, 1.00, 1.00, 0.10)

    def __init__(self, fn_get_option, fn_set_option, label=None, vertical=True, margin=2, separation=0, hovercolor=(1,1,1,0.1)):
        super().__init__(vertical=vertical, margin=margin, separation=separation)
        self.defer_recalc = True
        if vertical: align,valign = -1,-1
        else: align,valign = -1,0
        self.ui_label = super().add(UI_Label('', margin=0, align=align, valign=valign))
        self.set_label(label)
        self.container = super().add(UI_EqualContainer(vertical=vertical, margin=0))
        self.fn_get_option = fn_get_option
        self.fn_set_option = fn_set_option
        self.options = {}
        self.values = set()
        self.hovercolor = hovercolor
        self.mouse_prev = None
        self.defer_recalc = False

    def set_label(self, label):
        self.ui_label.visible = label is not None
        self.ui_label.set_label(label or '')

    class UI_Option(UI_Background):
        def __init__(self, options, label, value, icon=None, tooltip=None, color=(1,1,1,1), align=-1, showlabel=True, margin=2):
            super().__init__(rounded=True, margin=0)
            self.defer_recalc = True
            self.label = label
            self.value = value
            self.options = options
            self.tooltip = tooltip
            self.hovering = False
            if not showlabel: label = None
            container = self.set_ui_item(UI_Container(margin=margin, vertical=False))
            if icon:           container.add(icon)
            if icon and label: container.add(UI_Spacer(width=4))
            if label:          container.add(UI_Label(label, color=color, align=align, valign=0, margin=0))
            self.defer_recalc = False

        def _hover_ui(self, mouse):
            return self if super()._hover_ui(mouse) else None
        def mouse_enter(self):
            self.hovering = True
        def mouse_leave(self):
            self.hovering = False

        def predraw(self):
            if self.value == self.options.fn_get_option():
                self.background = UI_Options.color_select
                #self.border = (1,1,1,0.5)
                self.border = None
            elif self.hovering:
                self.background = UI_Options.color_hover
                self.border = (0,0,0,0.2)
            else:
                self.background = UI_Options.color_unselect
                #self.border = None

        #@profiler.profile
        #def _draw(self):
        #    super()._draw()

        def _get_tooltip(self, mouse): return self.tooltip

    def add_option(self, label, value=None, icon=None, tooltip=None, color=(1,1,1,1), align=-1, showlabel=True, margin=2):
        if value is None: value=label
        assert value not in self.values, "All option values must be unique!"
        option = self.container.add(UI_Options.UI_Option(self, label, value, icon=icon, tooltip=tooltip, color=color, align=align, showlabel=showlabel, margin=margin))
        self.values.add(value)
        self.options[option] = value

    def set_option(self, value):
        if self.fn_get_option() == value: return
        self.fn_set_option(value)

    def add(self, *args, **kwargs):
        assert False, "Do not call UI_Options.add()"

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        if self.mouse_prev != mouse:
            self.mouse_prev = mouse
            ui_hover = self.container._hover_ui(mouse)
            for ui in self.container.get_ui_items():
                if ui == ui_hover:
                    ui.mouse_enter()
                else:
                    ui.mouse_leave()
        return self
    def _get_tooltip(self, mouse):
        ui = super()._hover_ui(mouse)
        return ui._get_tooltip(mouse) if ui and ui != self else None

    def mouse_down(self, mouse): self.mouse_up(mouse)
    def mouse_move(self, mouse): self.mouse_up(mouse)
    def mouse_up(self, mouse):
        ui = self.container._hover_ui(mouse)
        if ui is None or ui == self.container: return
        self.set_option(self.options[ui])

    def mouse_leave(self):
        for ui in self.container.get_ui_items():
            ui.mouse_leave()

    @profiler.profile
    def _draw(self):
        l,t = self.pos
        w,h = self.size
        bgl.glEnable(bgl.GL_BLEND)
        self.drawing.line_width(1)
        bgl.glColor4f(0,0,0,0.2)
        bgl.glBegin(bgl.GL_LINE_STRIP)
        bgl.glVertex2f(l,t)
        bgl.glVertex2f(l,t-h)
        bgl.glVertex2f(l+w,t-h)
        bgl.glVertex2f(l+w,t)
        bgl.glVertex2f(l,t)
        bgl.glEnd()
        super()._draw()


class UI_Image(UI_Element):
    executor = ThreadPoolExecutor()

    def __init__(self, image_data, margin=0, async_load=True, width=None, height=None):
        super().__init__()
        self.defer_recalc = True
        self.image_data = image_data
        self.image_width,self.image_height = 16,16
        self.width = width or 16
        self.height = height or 16
        self.size_set = (width is not None) or (height is not None)
        self.loaded = False
        self.buffered = False
        self.deleted = False
        self.margin = margin

        self.texbuffer = bgl.Buffer(bgl.GL_INT, [1])
        bgl.glGenTextures(1, self.texbuffer)
        self.texture_id = self.texbuffer[0]

        if async_load: self.executor.submit(self.load_image)
        else: self.load_image()
        self.defer_recalc = False

    def load_image(self):
        image_data = self.image_data
        if type(image_data) is str: image_data = load_image_png(image_data)
        self.image_height,self.image_width,self.image_depth = len(image_data),len(image_data[0]),len(image_data[0][0])
        assert self.image_depth == 4
        self.image_flat = [d for r in image_data for c in r for d in c]
        self.loaded = True
        self.dirty()

    def buffer_image(self):
        if not self.loaded: return
        if self.buffered: return
        if self.deleted: return
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.texture_id)
        bgl.glTexEnvf(bgl.GL_TEXTURE_ENV, bgl.GL_TEXTURE_ENV_MODE, bgl.GL_MODULATE)
        bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_NEAREST)
        bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        # texbuffer = bgl.Buffer(bgl.GL_BYTE, [self.width,self.height,self.depth], image_data)
        image_size = self.image_width*self.image_height*self.image_depth
        texbuffer = bgl.Buffer(bgl.GL_BYTE, [image_size], self.image_flat)
        bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, self.image_width, self.image_height, 0, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, texbuffer)
        del texbuffer
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
        self.buffered = True

    def __del__(self):
        self.deleted = True
        bgl.glDeleteTextures(1, self.texbuffer)

    def _recalc_size(self):
        self._width_inner = self.drawing.scale(self.width if self.size_set else self.image_width)
        self._height_inner = self.drawing.scale(self.height if self.size_set else self.image_height)

    def get_image_width(self): return self._width_inner
    def get_image_height(self): return self._height_inner

    def set_width(self, w): self.width,self.size_set = w,True
    def set_height(self, h): self.height,self.size_set = h,True
    def set_size(self, w, h): self.width,self.height,self.size_set = w,h,True

    @profiler.profile
    def _draw(self):
        self.buffer_image()
        if not self.buffered: return

        cx,cy = (self.pos.x + self.size.x / 2, self.pos.y - self.size.y / 2)
        iw,ih = self.get_image_width(),self.get_image_height()
        il,it = cx-iw/2, cy+ih/2

        bgl.glColor4f(1,1,1,1)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.texture_id)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glTexCoord2f(0,0);  bgl.glVertex2f(il,it)
        bgl.glTexCoord2f(0,1);  bgl.glVertex2f(il,it-ih)
        bgl.glTexCoord2f(1,1);  bgl.glVertex2f(il+iw,it-ih)
        bgl.glTexCoord2f(1,0);  bgl.glVertex2f(il+iw,it)
        bgl.glEnd()
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)


class UI_Graphic(UI_Element):
    def __init__(self, graphic=None, margin=0, width=12, height=12):
        super().__init__(margin=margin)
        self.defer_recalc = True

        self._graphic_width = None
        self._graphic_height = None

        self._graphic = graphic
        self.width = width
        self.height = height
        self.defer_recalc = False

    @property
    def width(self):
        return self._graphic_width

    @width.setter
    def width(self, w):
        w = max(0, w)
        if self._graphic_width == w: return
        self._graphic_width = w
        self.dirty()

    @property
    def height(self):
        return self._graphic_height

    @height.setter
    def height(self, h):
        h = max(0, h)
        if self._graphic_height == h: return
        self._graphic_height =h
        self.dirty()

    def set_graphic(self, graphic): self._graphic = graphic

    def _recalc_size(self):
        self._width_inner = self.drawing.scale(self.width)
        self._height_inner = self.drawing.scale(self.height)

    @profiler.profile
    def _draw(self):
        cx = self.pos.x + self.size.x / 2
        cy = self.pos.y - self.size.y / 2
        w,h = self.drawing.scale(self.width),self.drawing.scale(self.height)
        l,t = cx-w/2, cy+h/2

        self.drawing.line_width(1.0)
        bgl.glEnable(bgl.GL_BLEND)

        if self._graphic == 'box unchecked':
            bgl.glColor4f(1,1,1,0.25)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glVertex2f(l,t)
            bgl.glEnd()

        elif self._graphic == 'box checked':
            bgl.glColor4f(0.27,0.50,0.72,0.90)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()
            bgl.glColor4f(1,1,1,1)
            if False:
                # outline
                bgl.glBegin(bgl.GL_LINE_STRIP)
                bgl.glVertex2f(l,t)
                bgl.glVertex2f(l,t-h)
                bgl.glVertex2f(l+w,t-h)
                bgl.glVertex2f(l+w,t)
                bgl.glVertex2f(l,t)
                bgl.glEnd()
            # check
            bgl.glBegin(bgl.GL_LINE_STRIP)
            bgl.glVertex2f(l+2,cy)
            bgl.glVertex2f(cx,t-h+2)
            bgl.glVertex2f(l+w-2,t-2)
            bgl.glEnd()

        elif self._graphic == 'triangle right':
            bgl.glColor4f(1,1,1,1)
            bgl.glBegin(bgl.GL_TRIANGLES)
            bgl.glVertex2f(l+2,t-2)
            bgl.glVertex2f(l+2,t-h+2)
            bgl.glVertex2f(l+w-2,cy)
            bgl.glEnd()

        elif self._graphic == 'triangle down':
            bgl.glColor4f(1,1,1,1)
            bgl.glBegin(bgl.GL_TRIANGLES)
            bgl.glVertex2f(l+2,t-2)
            bgl.glVertex2f(cx,t-h+2)
            bgl.glVertex2f(l+w-2,t-2)
            bgl.glEnd()

        elif self._graphic == 'dash':
            bgl.glColor4f(1,1,1,1)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l+2,cy-2)
            bgl.glVertex2f(l+w-2,cy-2)
            bgl.glVertex2f(l+w-2,cy+2)
            bgl.glVertex2f(l+2,cy+2)
            bgl.glEnd()

        elif self._graphic == 'plus':
            bgl.glColor4f(1,1,1,1)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l+2,cy-2)
            bgl.glVertex2f(l+w-2,cy-2)
            bgl.glVertex2f(l+w-2,cy+2)
            bgl.glVertex2f(l+2,cy+2)

            bgl.glVertex2f(cx-2,t-2)
            bgl.glVertex2f(cx-2,t-h+2)
            bgl.glVertex2f(cx+2,t-h+2)
            bgl.glVertex2f(cx+2,t-2)
            bgl.glEnd()

        elif self._graphic == 'minus':
            bgl.glColor4f(1,1,1,1)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l+2,cy-2)
            bgl.glVertex2f(l+w-2,cy-2)
            bgl.glVertex2f(l+w-2,cy+2)
            bgl.glVertex2f(l+2,cy+2)
            bgl.glEnd()


class UI_Checkbox(UI_Container):
    '''
    [ ] Label
    [V] Label
    '''
    def __init__(self, label, fn_get_checked, fn_set_checked, **kwopts):
        spacing = kwopts.get('spacing', 8)
        hovercolor = kwopts.get('hovercolor', (1,1,1,0.1))
        tooltip = kwopts.get('tooltip', None)

        super().__init__(vertical=False, margin=2, separation=spacing)
        self.defer_recalc = True

        self.chk = UI_Graphic()
        self.add(self.chk)
        if label:
            # self.add(UI_Spacer(width=spacing))
            self.lbl = self.add(UI_Label(label, margin=0))
        self.fn_get_checked = fn_get_checked
        self.fn_set_checked = fn_set_checked
        self.tooltip = tooltip
        self.hovercolor = hovercolor
        self.hovering = False
        self.defer_recalc = False

    def _get_tooltip(self, mouse): return self.tooltip

    def _hover_ui(self, mouse):
        return self if super()._hover_ui(mouse) else None

    def mouse_up(self, mouse): self.fn_set_checked(not self.fn_get_checked())

    def mouse_enter(self):
        self.hovering = True
    def mouse_leave(self):
        self.hovering = False

    def predraw(self):
        self.chk.set_graphic('box checked' if self.fn_get_checked() else 'box unchecked')
        if self.hovering:
            self.background = self.hovercolor
        else:
            self.background = None


class UI_Checkbox2(UI_Container):
    '''
    Label
    Label  <- highlighted if checked
    '''
    def __init__(self, label, fn_get_checked, fn_set_checked, **kwopts):
        hovercolor = kwopts.get('hovercolor', (1,1,1,0.1))
        tooltip = kwopts.get('tooltip', None)

        super().__init__(margin=0)
        self.defer_recalc = True

        self.bg = self.add(UI_Background(border_thickness=1, rounded=True))
        self.bg.set_ui_item(UI_Label(label, align=0))
        self.fn_get_checked = fn_get_checked
        self.fn_set_checked = fn_set_checked
        self.tooltip = tooltip
        self.hovercolor = hovercolor
        self.hovering = False

        self.defer_recalc = False

    def _get_tooltip(self, mouse): return self.tooltip

    def _hover_ui(self, mouse):
        return self if super()._hover_ui(mouse) else None
    def mouse_up(self, mouse): self.fn_set_checked(not self.fn_get_checked())

    def mouse_enter(self):
        self.hovering = True
    def mouse_leave(self):
        self.hovering = False

    def predraw(self):
        if self.fn_get_checked():
            self.bg.background = (0.27, 0.50, 0.72, 0.90)
            self.bg.border = (1,1,1,0.5)
        else:
            if self.hovering:
                self.bg.background = self.hovercolor
            else:
                self.bg.background = None
            self.bg.border = (0,0,0,0.2)

    @profiler.profile
    def _draw(self):
        l,t = self.pos
        w,h = self.size

        self.drawing.line_width(1.0)
        bgl.glEnable(bgl.GL_BLEND)

        super()._draw()

class UI_BoolValue(UI_Checkbox):
    pass


class UI_Number(UI_Container):
    def __init__(self, label, fn_get_value, fn_set_value, update_multiplier=0.1, fn_update_value=None, fn_formatter=None, fn_get_print_value=None, fn_set_print_value=None, margin=2, bgcolor=None, hovercolor=(1,1,1,0.1), presscolor=(0,0,0,0.2), **kwargs):
        assert (fn_get_print_value is None and fn_set_print_value is None) or (fn_get_print_value is not None and fn_set_print_value is not None)
        super().__init__(vertical=False, margin=margin, separation=4)
        self.defer_recalc = True

        self.fn_get_value = fn_get_value
        self.fn_set_value = fn_set_value
        self.update_multiplier = update_multiplier
        self.fn_update_value = fn_update_value
        self.fn_formatter = fn_formatter
        self.fn_get_print_value = fn_get_print_value
        self.fn_set_print_value = fn_set_print_value

        self.lbl = self.add(UI_Label(label, margin=0, align=-1, valign=0))
        self.add(UI_Label('=', margin=0))
        self.val = self.add(UI_Label(self.get_formatted_value(), margin=0))

        self.downed = False
        self.captured = False
        self.time_start = time.time()
        self.tooltip = kwargs.get('tooltip', None)
        self.bgcolor = bgcolor
        self.presscolor = presscolor
        self.hovercolor = hovercolor
        self.hovering = False
        self.defer_recalc = False

    def get_formatted_value(self):
        if self.fn_get_print_value:
            val = self.fn_get_print_value()
        else:
            val = self.fn_get_value()
        if self.fn_formatter:
            val = self.fn_formatter(val)
        return val

    def _get_tooltip(self, mouse): return self.tooltip

    def _hover_ui(self, mouse):
        return self if super()._hover_ui(mouse) else None

    def mouse_down(self, mouse):
        self.down_mouse = mouse
        self.prev_mouse = mouse
        self.down_val = self.fn_get_value()
        self.downed = True
        self.drawing.set_cursor('MOVE_X')

    def mouse_move(self, mouse):
        if self.fn_update_value:
            self.fn_update_value((mouse.x - self.prev_mouse.x) * self.update_multiplier)
            self.prev_mouse = mouse
        else:
            self.fn_set_value(self.down_val + (mouse.x - self.down_mouse.x) * self.update_multiplier)

    def mouse_up(self, mouse):
        self.downed = False

    def mouse_cancel(self):
        self.fn_set_value(self.down_val)

    def mouse_enter(self):
        self.hovering = True
    def mouse_leave(self):
        self.hovering = False

    def predraw(self):
        if not self.captured:
            self.val.set_label(self.get_formatted_value())
            self.val.cursor_pos = None
        else:
            self.val.cursor_pos = self.val_pos

    @profiler.profile
    def _draw(self):
        r,g,b,a = (0,0,0,0.1) if not (self.downed or self.captured) else (0.8,0.8,0.8,0.5)
        l,t = self.pos
        w,h = self.size
        bgl.glEnable(bgl.GL_BLEND)
        self.drawing.line_width(1)

        if self.hovering:
            bgcolor = self.hovercolor or self.bgcolor
        else:
            bgcolor = self.bgcolor

        if bgcolor:
            bgl.glColor4f(*bgcolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        bgl.glColor4f(r,g,b,a)
        bgl.glBegin(bgl.GL_LINE_STRIP)
        bgl.glVertex2f(l,t)
        bgl.glVertex2f(l,t-h)
        bgl.glVertex2f(l+w,t-h)
        bgl.glVertex2f(l+w,t)
        bgl.glVertex2f(l,t)
        bgl.glEnd()
        super()._draw()

    def capture_start(self):
        self.val_orig = self.get_formatted_value()
        self.val_edit = str(self.val_orig)
        self.val_pos = len(self.val_edit)
        self.captured = True
        self.keys = {
            'ZERO':   '0', 'NUMPAD_0':      '0',
            'ONE':    '1', 'NUMPAD_1':      '1',
            'TWO':    '2', 'NUMPAD_2':      '2',
            'THREE':  '3', 'NUMPAD_3':      '3',
            'FOUR':   '4', 'NUMPAD_4':      '4',
            'FIVE':   '5', 'NUMPAD_5':      '5',
            'SIX':    '6', 'NUMPAD_6':      '6',
            'SEVEN':  '7', 'NUMPAD_7':      '7',
            'EIGHT':  '8', 'NUMPAD_8':      '8',
            'NINE':   '9', 'NUMPAD_9':      '9',
            'PERIOD': '.', 'NUMPAD_PERIOD': '.',
            'MINUS':  '-', 'NUMPAD_MINUS':  '-',
        }
        self.drawing.set_cursor('TEXT')
        return True

    def capture_event(self, event):
        time_delta = time.time() - self.time_start
        self.val.cursor_symbol = None if int(time_delta*10)%5 == 0 else '|'
        if event.value == 'RELEASE':
            if event.type in {'RET','NUMPAD_ENTER'}:
                self.captured = False
                try:
                    v = float(self.val_edit or '0')
                except:
                    v = self.val_orig
                if self.fn_set_print_value: self.fn_set_print_value(v)
                else: self.fn_set_value(v)
                return True
            if event.type == 'ESC':
                self.captured = False
                return True
        if event.value == 'PRESS':
            if event.type == 'LEFT_ARROW':
                self.val_pos = max(0, self.val_pos - 1)
            if event.type == 'RIGHT_ARROW':
                self.val_pos = min(len(self.val_edit), self.val_pos + 1)
            if event.type == 'HOME':
                self.val_pos = 0
            if event.type == 'END':
                self.val_pos = len(self.val_edit)
            if event.type == 'BACK_SPACE' and self.val_pos > 0:
                self.val_edit = self.val_edit[:self.val_pos-1] + self.val_edit[self.val_pos:]
                self.val_pos -= 1
            if event.type == 'DEL' and self.val_pos < len(self.val_edit):
                self.val_edit = self.val_edit[:self.val_pos] + self.val_edit[self.val_pos+1:]
            if event.type in self.keys:
                self.val_edit = self.val_edit[:self.val_pos] + self.keys[event.type] + self.val_edit[self.val_pos:]
                self.val_pos += 1
            self.val.set_label(self.val_edit or '0')


class UI_Textbox(UI_Container):
    def __init__(self, fn_get_value, fn_set_value, always_commit=False, fn_enter=None, allow_chars=None, label=None, margin=2, bgcolor=None, hovercolor=(1,1,1,0.1), min_size=(0,0), **kwargs):
        super().__init__(vertical=False, margin=margin, separation=4)
        self.defer_recalc = True

        self.always_commit = always_commit
        self.fn_get_value = fn_get_value
        self.fn_set_value = fn_set_value
        self.fn_enter = fn_enter
        self.allow_chars = set(allow_chars) if allow_chars else None

        if label:
            self.add(UI_Label(label, margin=0, align=-1, valign=0))
            self.add(UI_Label('=', margin=0))
        self.val = self.add(UI_Label(self.get_formatted_value(), margin=0, min_size=min_size))

        self.downed = False
        self.captured = False
        self.time_start = time.time()
        self.tooltip = kwargs.get('tooltip', None)
        self.bgcolor = bgcolor
        self.hovercolor = hovercolor
        self.hovering = False
        self.defer_recalc = False

        self.lshift_pressed = False
        self.rshift_pressed = False

    def get_formatted_value(self):
        return self.fn_get_value()

    def _get_tooltip(self, mouse): return self.tooltip

    def _hover_ui(self, mouse):
        return self if super()._hover_ui(mouse) else None

    def mouse_down(self, mouse):
        self.down_mouse = mouse
        self.prev_mouse = mouse
        self.down_val = self.fn_get_value()
        self.downed = True
        self.drawing.set_cursor('MOVE_X')

    def mouse_up(self, mouse):
        self.downed = False

    def mouse_cancel(self):
        self.fn_set_value(self.down_val)

    def mouse_enter(self):
        self.hovering = True
    def mouse_leave(self):
        self.hovering = False

    def predraw(self):
        if not self.captured:
            self.val.set_label(self.get_formatted_value())
            self.val.cursor_pos = None
        else:
            self.val.cursor_pos = self.val_pos

    @profiler.profile
    def _draw(self):
        r,g,b,a = (0,0,0,0.1) if not (self.downed or self.captured) else (0.8,0.8,0.8,0.5)
        l,t = self.pos
        w,h = self.size
        bgl.glEnable(bgl.GL_BLEND)
        self.drawing.line_width(1)

        if self.hovering:
            bgcolor = self.hovercolor or self.bgcolor
        else:
            bgcolor = self.bgcolor

        if bgcolor:
            bgl.glColor4f(*bgcolor)
            bgl.glBegin(bgl.GL_QUADS)
            bgl.glVertex2f(l,t)
            bgl.glVertex2f(l,t-h)
            bgl.glVertex2f(l+w,t-h)
            bgl.glVertex2f(l+w,t)
            bgl.glEnd()

        bgl.glColor4f(r,g,b,a)
        bgl.glBegin(bgl.GL_LINE_STRIP)
        bgl.glVertex2f(l,t)
        bgl.glVertex2f(l,t-h)
        bgl.glVertex2f(l+w,t-h)
        bgl.glVertex2f(l+w,t)
        bgl.glVertex2f(l,t)
        bgl.glEnd()
        super()._draw()

    def capture_start(self):
        self.val_orig = self.get_formatted_value()
        self.val_edit = str(self.val_orig)
        self.val_pos = len(self.val_edit)
        self.captured = True
        # https://docs.blender.org/api/blender_python_api_current/bpy.types.Event.html#bpy.types.Event.type
        self.keys = {
            'ZERO':   '0', 'NUMPAD_0':      '0',
            'ONE':    '1', 'NUMPAD_1':      '1',
            'TWO':    '2', 'NUMPAD_2':      '2',
            'THREE':  '3', 'NUMPAD_3':      '3',
            'FOUR':   '4', 'NUMPAD_4':      '4',
            'FIVE':   '5', 'NUMPAD_5':      '5',
            'SIX':    '6', 'NUMPAD_6':      '6',
            'SEVEN':  '7', 'NUMPAD_7':      '7',
            'EIGHT':  '8', 'NUMPAD_8':      '8',
            'NINE':   '9', 'NUMPAD_9':      '9',
            'PERIOD': '.', 'NUMPAD_PERIOD': '.',
            'MINUS':  '-', 'NUMPAD_MINUS':  '-',
            'SPACE':  ' ',
            'SEMI_COLON': ';', 'COMMA': ',',
            'QUOTE': "'", 'ACCENT_GRAVE': '`',
            'PLUS': '+', 'SLASH': '/', 'BACK_SLASH': '\\',
            'EQUAL': '=', 'LEFT_BRACKET': '[', 'RIGHT_BRACKET': ']',
        }
        self.keys.update({ key.upper(): key.lower() for key in 'abcdefghijklmnopqrstuvwxyz' })
        self.upper_keys = {
            '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
            '-': '_', '[': '{', ']': '}', '/': '?', '=': '+',
            '\\': '|', "'": '"', ',': '<', '.': '>', ' ': ' ',
            '`': '~', '+': '+',
        }
        self.upper_keys.update({key.lower(): key.upper() for key in 'abcdefghijklmnopqrstuvwxyz'})
        self.drawing.set_cursor('TEXT')
        return True

    def capture_event(self, event):
        time_delta = time.time() - self.time_start
        self.val.cursor_symbol = None if int(time_delta*10)%5 == 0 else '|'
        if event.value == 'RELEASE':
            if event.type in {'RET','NUMPAD_ENTER'}:
                self.captured = False
                self.fn_set_value(self.val_edit)
                if self.fn_enter:
                    self.fn_enter()
                return True
            if event.type == 'ESC':
                self.captured = False
                return True
            if event.type == 'LEFT_SHIFT':
                self.lshift_pressed = False
            if event.type == 'RIGHT_SHIFT':
                self.rshift_pressed = False
        if event.value == 'PRESS':
            if event.type == 'LEFT_ARROW':
                self.val_pos = max(0, self.val_pos - 1)
            if event.type == 'RIGHT_ARROW':
                self.val_pos = min(len(self.val_edit), self.val_pos + 1)
            if event.type == 'HOME':
                self.val_pos = 0
            if event.type == 'END':
                self.val_pos = len(self.val_edit)
            if event.type == 'BACK_SPACE' and self.val_pos > 0:
                self.val_edit = self.val_edit[:self.val_pos-1] + self.val_edit[self.val_pos:]
                self.val_pos -= 1
            if event.type == 'DEL' and self.val_pos < len(self.val_edit):
                self.val_edit = self.val_edit[:self.val_pos] + self.val_edit[self.val_pos+1:]
            if event.type == 'LEFT_SHIFT':
                self.lshift_pressed = True
            if event.type == 'RIGHT_SHIFT':
                self.rshift_pressed = True
            if event.type in self.keys:
                k = self.keys[event.type]
                if self.lshift_pressed or self.rshift_pressed: k = self.upper_keys[k]
                if not self.allow_chars or k in self.allow_chars:
                    self.val_edit = self.val_edit[:self.val_pos] + k + self.val_edit[self.val_pos:]
                    self.val_pos += 1
            if self.always_commit:
                self.fn_set_value(self.val_edit)
            self.val.set_label(self.val_edit)


class UI_HBFContainer(UI_Container):
    '''
    container with header, body, and footer
    '''
    def __init__(self, vertical=True, separation=2, min_size=(0,0)):
        super().__init__(margin=0, separation=2, min_size=min_size)
        self.defer_recalc = True
        self.header = super().add(UI_Container())
        self.body_scroll = super().add(UI_VScrollable())
        self.body = self.body_scroll.set_ui_item(UI_Container(vertical=vertical, separation=separation, margin=0))
        self.footer = super().add(UI_Container())
        self.header.visible = False
        self.body_scroll.visible = False
        self.footer.visible = False
        self.defer_recalc = False

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        ui = self.header.hover_ui(mouse) or self.body.hover_ui(mouse) or self.footer.hover_ui(mouse)
        return ui or self

    def add(self, ui_item, header=False, footer=False):
        if header:
            self.header.add(ui_item)
            self.header.visible = True
        elif footer:
            self.footer.add(ui_item)
            self.footer.visible = True
        else:
            self.body.add(ui_item)
            self.body_scroll.visible = True
        return ui_item

    def _draw(self):
        l,t = self.pos
        w,h = self.size
        sl, st, sw, sh = ScissorStack.get_current_view()
        hh = self.header.get_height()
        fh = self.footer.get_height()
        bt = t
        bh = h
        sep = self.drawing.scale(self.separation)
        if hh > 0:
            bt -= hh + sep
            bh -= hh + sep
        if fh > 0:
            bh -= fh + sep
        self.body_scroll.draw(l, bt, w, bh)
        if hh > 0: self.header.draw(l, t, w, hh)
        if fh > 0: self.footer.draw(l, t - h + fh, w, fh)


class UI_Collapsible(UI_Container):
    def __init__(self, title, collapsed=True, fn_collapsed=None, equal=False, vertical=True):
        super().__init__(margin=0, separation=2)
        self.defer_recalc = True

        self.header = super().add(UI_Container(background=(0,0,0,0.2), margin=0, separation=0))
        self.body_wrap = super().add(UI_Container(vertical=False, margin=0, separation=0))
        self.footer = super().add(UI_Container(margin=0, separation=0))

        self.title = self.header.add(UI_Container(vertical=False, margin=0))
        self.title.add(UI_Spacer(width=4))
        self.title_arrow = self.title.add(UI_Graphic('triangle down'))
        self.title_label = self.title.add(UI_Label(title))
        # self.header.add(UI_Rule(color=(0,0,0,0.25)))

        self.body_wrap.add(UI_Spacer(width=8))
        #self.body_wrap.add(UI_Spacer(width=2, background=(1,1,1,0.1)))
        if equal:
            self.body = self.body_wrap.add(UI_EqualContainer(vertical=vertical, margin=1))
        else:
            self.body = self.body_wrap.add(UI_Container(vertical=vertical, margin=1, separation=0))

        #self.footer.add(UI_Spacer(height=1))
        #self.footer.add(UI_Rule(color=(0,0,0,0.25)))
        self.footer.add(UI_Spacer(height=1))

        def get_collapsed(): return fn_collapsed.get() if fn_collapsed else self.collapsed
        def set_collapsed(v):
            if v == get_collapsed(): return
            if fn_collapsed:
                fn_collapsed.set(v)
                self.collapsed = fn_collapsed.get()
            else:
                self.collapsed = v
            self.dirty()

        self.collapsed = fn_collapsed.get() if fn_collapsed else collapsed
        self.fn_collapsed = GetSet(get_collapsed, set_collapsed)

        self.graphics = {
            False: 'triangle down',
            True: 'triangle right',
        }
        self.defer_recalc = False

    def expand(self):
        self.fn_collapsed.set(False)
    def collapse(self):
        self.fn_collapsed.set(True)

    def predraw(self):
        #self.title.set_bgcolor(self.bgcolors[self.fn_collapsed.get()])
        self.title_arrow.set_graphic(self.graphics[self.fn_collapsed.get()])
        expanded = not self.fn_collapsed.get()
        self.body_wrap.visible = expanded
        self.footer.visible = expanded

    # def _recalc_size(self):
    #     sizes = [ui_item.recalc_size() for ui_item in self.ui_items]
    #     widths = [w for (w,h) in sizes]
    #     heights = [h for (w,h) in sizes]
    #     self._width_inner = max(widths)
    #     self._height_inner = sum(heights)

    def add(self, ui_item, header=False):
        if header: self.header.add(ui_item)
        else: self.body.add(ui_item)
        return ui_item

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        if self.fn_collapsed.get(): return self
        return self.body.hover_ui(mouse) or self

    def mouse_up(self, mouse):
        if self.fn_collapsed.get():
            self.expand()
        else:
            self.collapse()


class UI_Frame(UI_Container):
    def __init__(self, title, equal=False, vertical=True, separation=2):
        super().__init__()
        self.defer_recalc = True
        self.margin = 0
        self.separation = 0

        self.header = super().add(UI_Container(background=(0,0,0,0.2), margin=0, separation=0))
        self.body_wrap = super().add(UI_Container(vertical=False, margin=0, separation=0))
        self.footer = super().add(UI_Container(margin=0, separation=0))

        self.title = self.header.add(UI_Label(title))

        self.body_wrap.add(UI_Spacer(width=8))
        #self.body_wrap.add(UI_Spacer(width=2, background=(1,1,1,0.1)))
        if equal:
            self.body = self.body_wrap.add(UI_EqualContainer(vertical=vertical, margin=1))
        else:
            self.body = self.body_wrap.add(UI_Container(vertical=vertical, margin=1, separation=separation))

        self.footer.add(UI_Spacer(height=1))
        self.footer.add(UI_Rule(color=(0,0,0,0.25)))
        self.footer.add(UI_Spacer(height=1))
        self.defer_recalc = False

    # def _recalc_size(self):
    #     sizes = [ui_item.recalc_size() for ui_item in self.ui_items]
    #     widths = [w for (w,h) in sizes]
    #     heights = [h for (w,h) in sizes]
    #     self._width_inner = max(widths)
    #     self._height_inner = sum(heights)

    def add(self, ui_item):
        return self.body.add(ui_item)

    def _hover_ui(self, mouse):
        if not super()._hover_ui(mouse): return None
        return self.body.hover_ui(mouse) or self



class UI_Window(UI_Padding):
    screen_margin = 5

    def __init__(self, title, options):
        vertical = options.get('vertical', True)
        margin = options.get('padding', 0)
        separation = options.get('separation', 0)

        super().__init__(margin=0)
        self.defer_recalc = True

        fn_sticky = options.get('fn_pos', None)
        def get_sticky(): return fn_sticky.get() if fn_sticky else self.sticky
        def set_sticky(v):
            if fn_sticky:
                fn_sticky.set(v)
                self.sticky = fn_sticky.get()
            else:
                self.sticky = v

        self.sticky    = fn_sticky.get() if fn_sticky else options.get('pos', 5)
        self.fn_sticky = GetSet(get_sticky, set_sticky)
        self.visible   = options.get('visible', True)
        self.movable   = options.get('movable', True)
        self.bgcolor   = options.get('bgcolor', (0.1,0.1,0.1,0.75))

        self.fn_event_handler = options.get('event handler', None)

        self.mouse_pos = Point2D((0,0))

        self.ui_hover = None
        self.ui_grab = [self]
        padded = self.set_ui_item(UI_Padding(margin=margin))
        self.hbf = padded.set_ui_item(UI_HBFContainer(vertical=vertical, separation=separation))
        self.hbf.header.margin = 0
        self.hbf.body.margin = 0
        self.hbf.footer.margin = 0
        self.hbf.header.background = (0,0,0,0.2)

        #if title:
        self.hbf_title = self.hbf.add(UI_Label('', align=0, color=(1,1,1,0.5)), header=True)
        self.set_title(title)
        #self.hbf_title_rule = self.hbf.add(UI_Rule(color=(0,0,0,0.1)), header=True)
        self.ui_grab += self.hbf.header.ui_items # [self.hbf_title, self.hbf_title_rule]

        self.update_pos()

        self.FSM = {}
        self.FSM['main'] = self.modal_main
        self.FSM['move'] = self.modal_move
        self.FSM['down'] = self.modal_down
        self.FSM['capture'] = self.modal_capture
        self.FSM['scroll'] = self.modal_scroll
        self.state = 'main'
        self.defer_recalc = False

    def set_title(self, title):
        if title is None:
            self.hbf_title.visible = False
        else:
            self.hbf_title.set_label(title)
            self.hbf_title.visible = True

    def show(self): self.visible = True
    def hide(self): self.visible = False

    def add(self, *args, **kwargs): return self.hbf.add(*args, **kwargs)

    def update_pos(self):
        m = self.screen_margin
        self.recalc_size()
        w,h = self.get_width(),self.get_height()
        rgn = self.context.region
        if not rgn: return
        sw,sh = rgn.width,rgn.height
        cw,ch = round((sw-w)/2),round((sh+h)/2)
        sticky_positions = {
            7: (0, sh), 8: (cw, sh), 9: (sw, sh),
            4: (0, ch), 5: (cw, ch), 6: (sw, ch),
            1: (0, 0),  2: (cw, 0),  3: (sw, 0),
        }

        sticky = self.fn_sticky.get()
        if type(sticky) is not int:
            l,t = sticky
            stick_t,stick_b = t >= sh - m, t <= m + h
            stick_l,stick_r = l <= m, l >= sw - m - w
            nsticky = None
            if stick_t:
                if stick_l: nsticky = 7
                if stick_r: nsticky = 9
            elif stick_b:
                if stick_l: nsticky = 1
                if stick_r: nsticky = 3
            if nsticky:
                self.fn_sticky.set(nsticky)
                sticky = self.fn_sticky.get()
        pos = sticky_positions[sticky] if type(sticky) is int else sticky

        # clamp position so window is always seen
        l,t = pos
        w = min(w, sw-m*2)
        h = min(h, sh-m*2)
        l = max(m,   min(sw-m-w,l))
        t = max(m+h, min(sh-m,  t))

        self.pos = Point2D((l,t))
        self.size = Vec2D((w,h))

    def draw_postpixel(self):
        if not self.visible: return

        self.drawing.set_font_size(12)

        pr = profiler.start('UI_Window: updating position')
        self.update_pos()
        pr.done()

        l,t = self.pos
        w,h = self.size

        bgl.glEnable(bgl.GL_BLEND)

        # draw background
        bgl.glColor4f(*self.bgcolor)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glVertex2f(l,t)
        bgl.glVertex2f(l,t-h)
        bgl.glVertex2f(l+w,t-h)
        bgl.glVertex2f(l+w,t)
        bgl.glEnd()

        self.drawing.line_width(1.0)
        bgl.glColor4f(0,0,0,0.5)
        bgl.glBegin(bgl.GL_LINE_STRIP)
        bgl.glVertex2f(l,t)
        bgl.glVertex2f(l,t-h)
        bgl.glVertex2f(l+w,t-h)
        bgl.glVertex2f(l+w,t)
        bgl.glVertex2f(l,t)
        bgl.glEnd()

        pr = profiler.start('UI_Window: drawing contents')
        self.draw(l, t, w, h)
        pr.done()

    def update_hover(self, new_elem):
        if self.ui_hover == new_elem: return
        if self.ui_hover and self.ui_hover != self: self.ui_hover.mouse_leave()
        self.ui_hover = new_elem
        if self.ui_hover and self.ui_hover != self: self.ui_hover.mouse_enter()

    def mouse_enter(self): self.update_hover(self.hover_ui(self.mouse_pos))
    def mouse_leave(self): self.update_hover(None)

    def modal(self, context, event):
        if event.mouse_region_x >= 0 and event.mouse_region_y >= 0:
            self.mouse_pos = Point2D((float(event.mouse_region_x), float(event.mouse_region_y)))
        self.context = context
        self.event = event

        if not self.visible: return

        nstate = self.FSM[self.state]()
        self.state = nstate or self.state

        return {'hover'} if self.hover_ui(self.mouse_pos) or self.state != 'main' else {}

    def get_tooltip(self):
        self.mouse_enter()
        #self.ui_hover = self.hover_ui(self.mouse_pos)
        return self.ui_hover._get_tooltip(self.mouse_pos) if self.ui_hover else None

    def modal_main(self):
        self.mouse_enter()
        if not self.ui_hover: return
        self.drawing.set_cursor(self.ui_hover.mouse_cursor())

        if self.event.type == 'LEFTMOUSE' and self.event.value == 'PRESS':
            self.mouse_pos_down = self.mouse_pos
            if self.movable and self.ui_hover in self.ui_grab:
                self.mouse_pos_prev = self.mouse_pos
                self.pos_prev = self.pos
                return 'move'
            self.ui_down = self.ui_hover
            self.ui_down.mouse_down(self.mouse_pos)
            self.mouse_moved = False
            return 'down'

        if self.event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'PAGE_UP', 'PAGE_DOWN', 'TRACKPADPAN', 'UP_ARROW', 'DOWN_ARROW'}:
            if self.event.type == 'TRACKPADPAN':
                move = self.event.mouse_y - self.event.mouse_prev_y
            else:
                move = self.drawing.scale(24) * (-1 if 'UP' in self.event.type else 1)
            self.hbf.body_scroll.offset += move
            return

        if self.event.type == 'MIDDLEMOUSE' and self.event.value == 'PRESS':
            self.mouse_pos_down = self.mouse_pos
            self.mouse_pos_prev = self.mouse_pos
            return 'scroll'

    def modal_scroll(self):
        self.drawing.set_cursor('HAND')
        if self.event.type == 'MIDDLEMOUSE' and self.event.value == 'RELEASE':
            return 'main'
        move = (self.mouse_pos.y - self.mouse_pos_prev.y)
        self.hbf.body_scroll.offset += move
        self.mouse_pos_prev = self.mouse_pos

    def scrollto_top(self):
        self.hbf.body_scroll.offset = 0

    def scrollto_bottom(self):
        self.hbf.body_scroll.offset = self.hbf.body_scroll.get_height()

    def modal_move(self):
        self.drawing.set_cursor('HAND')
        if self.event.type == 'LEFTMOUSE' and self.event.value == 'RELEASE':
            return 'main'
        diff = self.mouse_pos - self.mouse_pos_down
        self.fn_sticky.set(self.pos_prev + diff)
        self.update_pos()
        self.mouse_pos_prev = self.mouse_pos

    def modal_down(self):
        if self.event.type == 'LEFTMOUSE' and self.event.value == 'RELEASE':
            self.ui_down.mouse_up(self.mouse_pos)
            if not self.mouse_moved and self.ui_down.capture_start(): return 'capture'
            return 'main'
        if self.event.type == 'ESC' and self.event.value == 'RELEASE':
            self.ui_down.mouse_cancel()
            return 'main'
        self.mouse_moved |= (self.mouse_pos_down != self.mouse_pos)
        self.ui_down.mouse_move(self.mouse_pos)

    def modal_capture(self):
        if self.ui_down.capture_event(self.event): return 'main'

    def distance(self, pt):
        px,py = self.pos
        sx,sy = self.size
        c = Point2D((mid(px, px+sx, pt.x), mid(py, py-sy, pt.y)))
        return (pt - c).length


class UI_WindowManager:
    def __init__(self, **kwargs):
        self.drawing = Drawing.get_instance()
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




