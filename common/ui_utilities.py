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
import random
from functools import lru_cache

from .globals import Globals
from .decorators import debug_test_call, blender_version_wrapper
from .maths import Color
from .shaders import Shader

'''
Links to useful resources

- How Browsers Work: https://www.html5rocks.com/en/tutorials/internals/howbrowserswork
- WebCore Rendering
    - https://webkit.org/blog/114/webcore-rendering-i-the-basics/
    - https://webkit.org/blog/115/webcore-rendering-ii-blocks-and-inlines/
    - https://webkit.org/blog/116/webcore-rendering-iii-layout-basics/
    - https://webkit.org/blog/117/webcore-rendering-iv-absolutefixed-and-relative-positioning/
    - https://webkit.org/blog/118/webcore-rendering-v-floats/
- Mozilla's Layout Engine: https://www-archive.mozilla.org/newlayout/doc/layout-2006-12-14/master.xhtml
- Mozilla's Notes on HTML Reflow: https://www-archive.mozilla.org/newlayout/doc/reflow.html
- How Browser Rendering Works: http://dbaron.github.io/browser-rendering/
- Render-tree Construction, Layout, and Paint: https://developers.google.com/web/fundamentals/performance/critical-rendering-path/render-tree-construction
- Beginner's Guide to Choose Between CSS Grid and Flexbox: https://medium.com/youstart-labs/beginners-guide-to-choose-between-css-grid-and-flexbox-783005dd2412
'''


###########################################################################
# below is a helper class for drawing ui



class UIRender:
    def __init__(self):
        self._children = []
    def append_child(self, child):
        self._children.append(child)

class UIRender_Block(UIRender):
    def __init__(self):
        super.__init__(self)

class UIRender_Inline(UIRender):
    def __init__(self):
        super.__init__(self)


#####################################################################################
# below are various token converters

# dictionary to convert color name to color values, either (R,G,B) or (R,G,B,a)
# https://www.quackit.com/css/css_color_codes.cfm
colorname_to_color = {
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

# dictionary to convert cursor name to Blender cursor enum
# https://docs.blender.org/api/blender2.8/bpy.types.Window.html#bpy.types.Window.cursor_modal_set
#   DEFAULT, NONE, WAIT, HAND,
#   CROSSHAIR, TEXT,
#   PAINT_BRUSH, EYEDROPPER, KNIFE,
#   MOVE_X, MOVE_Y,
#   SCROLL_X, SCROLL_Y, SCROLL_XY
cursorname_to_cursor = {
    'default': 'DEFAULT', 'auto': 'DEFAULT', 'initial': 'DEFAULT',
    'none': 'NONE',
    'wait': 'WAIT',
    'grab': 'HAND',
    'crosshair': 'CROSSHAIR', 'pointer': 'CROSSHAIR',
    'text': 'TEXT',
    'e-resize': 'MOVE_X', 'w-resize': 'MOVE_X', 'ew-resize': 'MOVE_X',
    'n-resize': 'MOVE_Y', 's-resize': 'MOVE_Y', 'ns-resize': 'MOVE_Y',
    'all-scroll': 'SCROLL_XY',
}


# @debug_test_call('rgb(  255,128,  64  )')
# @debug_test_call('rgba(255, 128, 64, 0.5)')
# @debug_test_call('hsl(0, 100%, 50%)')
# @debug_test_call('hsl(240, 100%, 50%)')
# @debug_test_call('hsl(147, 50%, 47%)')
# @debug_test_call('hsl(300, 76%, 72%)')
# @debug_test_call('hsl(39, 100%, 50%)')
# @debug_test_call('hsla(248, 53%, 58%, 0.5)')
# @debug_test_call('#FFc080')
# @debug_test_call('transparent')
# @debug_test_call('white')
# @debug_test_call('black')
def convert_token_to_color(c):
    r,g,b,a = 0,0,0,1
    if type(c) is re.Match: c = c.group(0)

    if c in colorname_to_color:
        c = colorname_to_color[c]
        if len(c) == 3: r,g,b = c
        else: r,g,b,a = c

    elif c.startswith('#'):
        r,g,b = map(lambda v:int(v,16), [c[1:3],c[3:5],c[5:7]])

    elif c.startswith('rgb(') or c.startswith('rgba('):
        c = c.replace('rgb(','').replace('rgba(','').replace(')','').replace(' ','').split(',')
        c = list(map(float, c))
        r,g,b = c[:3]
        if len(c) == 4: a = c[3]

    elif c.startswith('hsl(') or c.startswith('hsla('):
        c = c.replace('hsl(','').replace('hsla(','').replace(')','').replace(' ','').replace('%', '').split(',')
        c = list(map(float, c))
        h,s,l = c[0]/360, c[1]/100, c[2]/100
        if len(c) == 4: a = c[3]
        # https://gist.github.com/mjackson/5311256
        # TODO: use equations on https://www.rapidtables.com/convert/color/hsl-to-rgb.html
        if s <= 0.00001:
            r,g,b = 255
        else:
            def hue2rgb(p, q, t):
                t %= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            q = (l * ( 1 + s)) if l < 0.5 else (l + s - l * s)
            p = 2 * l - q
            r = hue2rgb(p, q, h + 1/3) * 255
            g = hue2rgb(p, q, h) * 255
            b = hue2rgb(p, q, h - 1/3) * 255

    else:
        assert 'could not convert "%s" to color' % c

    c = Color((r/255, g/255, b/255, a))
    c.freeze()
    return c

def convert_token_to_cursor(c):
    if type(c) is re.Match: c = c.group(0)
    if c in cursorname_to_cursor: return cursorname_to_cursor[c]
    if c in cursorname_to_cursor.values(): return c
    assert False, 'could not convert "%s" to cursor' % c

def convert_token_to_number(n):
    if type(n) is re.Match: n = n.group('num')
    return float(n)

def convert_token_to_numberunit(n):
    assert type(n) is re.Match
    v = n.group('num')
    u = n.group('unit')
    return (float(v), u)

def skip_token(n):
    return None

def convert_token_to_string(s):
    if type(s) is re.Match: s = s.group(0)
    return str(s)

def get_converter_to_string(group):
    def getter(s):
        if type(s) is re.Match: s = s.group(group)
        return str(s)
    return getter


#####################################################################################
# below are various helper functions for ui functions

def helper_argtranslate(key_from, key_to, kwargs):
    if key_from in kwargs:
        kwargs[key_to] = kwargs[key_from]
        del kwargs[key_from]

@lru_cache(maxsize=1024)
def helper_wraptext(text='', width=None, fontid=0, fontsize=12, preserve_newlines=False, collapse_spaces=True, wrap_text=True):
    # TODO: get textwidth of space and each word rather than rebuilding the string
    size_prev = Globals.drawing.set_font_size(fontsize, fontid=fontid, force=True)
    tw = Globals.drawing.get_text_width
    wrap_text &= width is not None

    if not preserve_newlines:
        text = re.sub(r'\n', ' ', text)
    if collapse_spaces:
        text = re.sub(r' +', ' ', text)
    if wrap_text:
        if width is None: width = float('inf')
        cline,*ltext = text.split(' ')
        nlines = []
        for cword in ltext:
            nline = '%s %s'%(cline,cword)
            if tw(nline) <= width: cline = nline
            else: nlines,cline = nlines+[cline],cword
        nlines += [cline]
        text = '\n'.join(nlines)

    Globals.drawing.set_font_size(size_prev, fontid=fontid, force=True)
    if False: print('wrapped ' + str(random.random()))
    return text
