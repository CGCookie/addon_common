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
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d

from .globals import Globals
from .blender import get_preferences
from .decorators import blender_version_wrapper
from .fontmanager import FontManager as fm
from .maths import Point2D, Vec2D, Point, Ray, Direction, mid
from .profiler import profiler
from .debug import dprint


class Drawing:
    _instance = None
    _dpi_mult = 1
    _prefs = get_preferences()

    @staticmethod
    @blender_version_wrapper('<','2.79')
    def update_dpi():
        dbl = 2 if Drawing._prefs.system.virtual_pixel_mode == 'DOUBLE' else 1
        Drawing._dpi_mult = int(Drawing._prefs.system.dpi * Drawing._prefs.system.pixel_size * dbl) / 72

    @staticmethod
    @blender_version_wrapper('==','2.79')
    def update_dpi():
        Drawing._dpi_mult = Drawing._prefs.view.ui_scale * Drawing._prefs.system.pixel_size * Drawing._prefs.system.dpi / 72

    @staticmethod
    @blender_version_wrapper('>=','2.80')
    def update_dpi():
        Drawing._dpi_mult = Drawing._prefs.view.ui_scale * Drawing._prefs.system.pixel_size

    @staticmethod
    def initialize():
        Drawing.update_dpi()
        if Globals.is_set('drawing'): return
        Drawing._creating = True
        Globals.set(Drawing())
        del Drawing._creating
        Drawing._instance = Globals.drawing

    def __init__(self):
        assert hasattr(self, '_creating'), "Do not instantiate directly.  Use Drawing.get_instance()"

        self.space,self.rgn,self.r3d,self.window = None,None,None,None
        # self.font_id = 0
        self.fontsize = None
        self.fontsize_scaled = None
        self.line_cache = {}
        self.size_cache = {}
        self.set_font_size(12)

    def set_region(self, space, rgn, r3d, window):
        self.space = space
        self.rgn = rgn
        self.r3d = r3d
        self.window = window

    @staticmethod
    def set_cursor(cursor):
        # DEFAULT, NONE, WAIT, CROSSHAIR, MOVE_X, MOVE_Y, KNIFE, TEXT,
        # PAINT_BRUSH, HAND, SCROLL_X, SCROLL_Y, SCROLL_XY, EYEDROPPER
        for wm in bpy.data.window_managers:
            for win in wm.windows:
                win.cursor_modal_set(cursor)

    def scale(self, s): return s * self._dpi_mult if s is not None else None
    def unscale(self, s): return s / self._dpi_mult if s is not None else None
    def get_dpi_mult(self): return self._dpi_mult
    def get_pixel_size(self): return self._pixel_size
    def line_width(self, width): bgl.glLineWidth(max(1, self.scale(width)))
    def point_size(self, size): bgl.glPointSize(max(1, self.scale(size)))

    def set_font_color(self, fontid, color):
        fm.color(color, fontid=fontid)

    def set_font_size(self, fontsize, fontid=None, force=False):
        fontsize, fontsize_scaled = int(fontsize), int(int(fontsize) * self._dpi_mult)
        if not force and fontsize_scaled == self.fontsize_scaled:
            return self.fontsize
        fontsize_prev = self.fontsize
        fontsize_scaled_prev = self.fontsize_scaled
        self.fontsize = fontsize
        self.fontsize_scaled = fontsize_scaled

        fm.size(fontsize_scaled, 72, fontid=fontid)
        # blf.size(self.font_id, fontsize_scaled, 72) #self._sysdpi)

        # cache away useful details about font (line height, line base)
        key = (self.fontsize_scaled)
        if key not in self.line_cache:
            dprint('Caching new scaled font size:', key)
            all_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()`~[}{]/?=+\\|-_\'",<.>'
            all_caps = all_chars.upper()
            self.line_cache[key] = {
                'line height': round(fm.dimensions(all_chars, fontid=fontid)[1] + self.scale(4)),
                'line base': round(fm.dimensions(all_caps, fontid=fontid)[1]),
            }
        info = self.line_cache[key]
        self.line_height = info['line height']
        self.line_base = info['line base']

        return fontsize_prev

    def get_text_size_info(self, text, item, fontsize=None, fontid=None):
        if fontsize: size_prev = self.set_font_size(fontsize, fontid=fontid)

        if text is None: text, lines = '', []
        elif type(text) is list: text, lines = '\n'.join(text), text
        else: text, lines = text, text.splitlines()

        fontid = fm.load(fontid)
        key = (text, self.fontsize_scaled, fontid)
        # key = (text, self.fontsize_scaled, self.font_id)
        if key not in self.size_cache:
            d = {}
            if not text:
                d['width'] = 0
                d['height'] = 0
                d['line height'] = self.line_height
            else:
                get_width = lambda t: math.ceil(fm.dimensions(t, fontid=fontid)[0])
                get_height = lambda t: math.ceil(fm.dimensions(t, fontid=fontid)[1])
                d['width'] = max(get_width(l) for l in lines)
                d['height'] = get_height(text)
                d['line height'] = self.line_height * len(lines)
            self.size_cache[key] = d
            if False:
                print('')
                print('--------------------------------------')
                print('> computed new size')
                print('>   key: %s' % str(key))
                print('>   size: %s' % str(d))
                print('--------------------------------------')
                print('')
        if fontsize: self.set_font_size(size_prev, fontid=fontid)
        return self.size_cache[key][item]

    def get_text_width(self, text, fontsize=None, fontid=None):
        return self.get_text_size_info(text, 'width', fontsize=fontsize, fontid=fontid)
    def get_text_height(self, text, fontsize=None, fontid=None):
        return self.get_text_size_info(text, 'height', fontsize=fontsize, fontid=fontid)
    def get_line_height(self, text=None, fontsize=None, fontid=None):
        return self.get_text_size_info(text, 'line height', fontsize=fontsize, fontid=fontid)

    def set_clipping(self, xmin, ymin, xmax, ymax, fontid=None):
        fm.clipping((xmin, ymin), (xmax, ymax), fontid=fontid)
        # blf.clipping(self.font_id, xmin, ymin, xmax, ymax)
        self.enable_clipping()
    def enable_clipping(self, fontid=None):
        fm.enable_clipping(fontid=fontid)
        # blf.enable(self.font_id, blf.CLIPPING)
    def disable_clipping(self, fontid=None):
        fm.disable_clipping(fontid=fontid)
        # blf.disable(self.font_id, blf.CLIPPING)

    def enable_stipple(self):
        bgl.glLineStipple(4, 0x5555)
        bgl.glEnable(bgl.GL_LINE_STIPPLE)
    def disable_stipple(self):
        bgl.glDisable(bgl.GL_LINE_STIPPLE)
    def set_stipple(self, enable):
        if enable: self.enable_stipple()
        else: self.disable_stipple()

    @blender_version_wrapper('<=','2.79')
    def text_draw2D(self, text, pos:Point2D, color=None, dropshadow=None, fontsize=None, fontid=None, lineheight=True):
        if fontsize: size_prev = self.set_font_size(fontsize, fontid=fontid)

        lines = str(text).splitlines()
        l,t = round(pos[0]),round(pos[1])
        lh = self.line_height
        lb = self.line_base

        if dropshadow: self.text_draw2D(text, (l+1,t-1), dropshadow, fontsize=fontsize)

        bgl.glEnable(bgl.GL_BLEND)
        if color is not None: bgl.glColor4f(*color)
        for line in lines:
            th = self.get_line_height(line) if lineheight else self.get_text_height(line)
            fm.draw(line, xyz=(l, t-lb, 0), fontid=fontid)
            # blf.position(self.font_id, l, t - lb, 0)
            # blf.draw(self.font_id, line)
            t -= lh

        if fontsize: self.set_font_size(size_prev, fontid=fontid)

    @blender_version_wrapper('>=', '2.80')
    def text_draw2D(self, text, pos:Point2D, color=None, dropshadow=None, fontsize=None, fontid=None, lineheight=True):
        if fontsize: size_prev = self.set_font_size(fontsize, fontid=fontid)

        lines = str(text).splitlines()
        l,t = round(pos[0]),round(pos[1])
        lh = self.line_height
        lb = self.line_base

        if dropshadow: self.text_draw2D(text, (l+1,t-1), dropshadow, fontsize=fontsize)

        bgl.glEnable(bgl.GL_BLEND)
        if color is not None: fm.color(color, fontid=fontid)
        for line in lines:
            th = self.get_line_height(line) if lineheight else self.get_text_height(line)
            fm.draw(line, xyz=(l, t-lb, 0), fontid=fontid)
            t -= lh

        if fontsize: self.set_font_size(size_prev, fontid=fontid)

    def get_mvp_matrix(self, view3D=True):
        '''
        if view3D == True: returns MVP for 3D view
        else: returns MVP for pixel view
        TODO: compute separate M,V,P matrices
        '''
        if not self.r3d: return None
        if view3D:
            # 3D view
            return self.r3d.perspective_matrix
        else:
            # pixel view
            return self.get_pixel_matrix()

        mat_model = Matrix()
        mat_view = Matrix()
        mat_proj = Matrix()

        view_loc = self.r3d.view_location # vec
        view_rot = self.r3d.view_rotation # quat
        view_per = self.r3d.view_perspective # 'PERSP' or 'ORTHO'

        return mat_model,mat_view,mat_proj

    def get_pixel_matrix_list(self):
        if not self.r3d: return None
        x,y = self.rgn.x,self.rgn.y
        w,h = self.rgn.width,self.rgn.height
        ww,wh = self.window.width,self.window.height
        return [[2/w,0,0,-1],  [0,2/h,0,-1],  [0,0,1,0],  [0,0,0,1]]

    def get_pixel_matrix(self):
        '''
        returns MVP for pixel view
        TODO: compute separate M,V,P matrices
        '''
        return Matrix(self.get_pixel_matrix_list()) if self.r3d else None

    def get_pixel_matrix_buffer(self):
        if not self.r3d: return None
        return bgl.Buffer(bgl.GL_FLOAT, [4,4], self.get_pixel_matrix_list())

    def get_view_matrix_list(self):
        return list(self.get_view_matrix()) if self.r3d else None

    def get_view_matrix(self):
        return self.r3d.perspective_matrix if self.r3d else None

    def get_view_version(self):
        m = self.r3d.view_matrix
        return [v for r in m for v in r] + [self.space.lens]

    def get_view_matrix_buffer(self):
        if not self.r3d: return None
        return bgl.Buffer(bgl.GL_FLOAT, [4,4], self.get_view_matrix_list())

    def textbox_draw2D(self, text, pos:Point2D, padding=5, textbox_position=7, fontid=None):
        '''
        textbox_position specifies where the textbox is drawn in relation to pos.
        ex: if textbox_position==7, then the textbox is drawn where pos is the upper-left corner
        tip: textbox_position is arranged same as numpad
                    +-----+
                    |7 8 9|
                    |4 5 6|
                    |1 2 3|
                    +-----+
        '''
        lh = self.line_height

        # TODO: wrap text!
        lines = text.splitlines()
        w = max(self.get_text_width(line) for line in lines)
        h = len(lines) * lh

        # find top-left corner (adjusting for textbox_position)
        l,t = round(pos[0]),round(pos[1])
        textbox_position -= 1
        lcr = textbox_position % 3
        tmb = int(textbox_position / 3)
        l += [w+padding,round(w/2),-padding][lcr]
        t += [h+padding,round(h/2),-padding][tmb]

        bgl.glEnable(bgl.GL_BLEND)

        bgl.glColor4f(0.0, 0.0, 0.0, 0.25)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glVertex2f(l+w+padding,t+padding)
        bgl.glVertex2f(l-padding,t+padding)
        bgl.glVertex2f(l-padding,t-h-padding)
        bgl.glVertex2f(l+w+padding,t-h-padding)
        bgl.glEnd()

        bgl.glColor4f(0.0, 0.0, 0.0, 0.75)
        self.drawing.line_width(1.0)
        bgl.glBegin(bgl.GL_LINE_STRIP)
        bgl.glVertex2f(l+w+padding,t+padding)
        bgl.glVertex2f(l-padding,t+padding)
        bgl.glVertex2f(l-padding,t-h-padding)
        bgl.glVertex2f(l+w+padding,t-h-padding)
        bgl.glVertex2f(l+w+padding,t+padding)
        bgl.glEnd()

        bgl.glColor4f(1,1,1,0.5)
        for i,line in enumerate(lines):
            th = self.get_text_height(line)
            y = t - (i+1)*lh + int((lh-th) / 2)
            fm.draw(line, xyz=(l, y, 0), fontid=fontid)
            # blf.position(self.font_id, l, y, 0)
            # blf.draw(self.font_id, line)

    def glCheckError(self, title):
        err = bgl.glGetError()
        if err == bgl.GL_NO_ERROR: return

        derrs = {
            bgl.GL_INVALID_ENUM: 'invalid enum',
            bgl.GL_INVALID_VALUE: 'invalid value',
            bgl.GL_INVALID_OPERATION: 'invalid operation',
            bgl.GL_STACK_OVERFLOW: 'stack overflow',
            bgl.GL_STACK_UNDERFLOW: 'stack underflow',
            bgl.GL_OUT_OF_MEMORY: 'out of memory',
            bgl.GL_INVALID_FRAMEBUFFER_OPERATION: 'invalid framebuffer operation',
        }
        if err in derrs:
            print('ERROR (%s): %s' % (title, derrs[err]))
        else:
            print('ERROR (%s): code %d' % (title, err))
        traceback.print_stack()

    def Point2D_to_Ray(self, p2d):
        o = Point(region_2d_to_origin_3d(self.rgn, self.r3d, p2d))
        d = Direction(region_2d_to_vector_3d(self.rgn, self.r3d, p2d))
        return Ray(o, d)

    def Point_to_Point2D(self, p3d):
        return Point2D(location_3d_to_region_2d(self.rgn, self.r3d, p3d))

Drawing.initialize()



class ScissorStack:
    buf = bgl.Buffer(bgl.GL_INT, 4)
    region_box = None                   # (l,b,w,h) of region in window-coords
    is_started = False
    scissor_test_was_enabled = False
    stack = None                        # stack of (l,b,w,h) in region-coordinates, because viewport is set to region

    @staticmethod
    def start(context):
        assert not ScissorStack.is_started, 'Attempting to start a started ScissorStack'

        # region pos and size are window-coordinates
        rgn = context.region
        rl,rb,rw,rh = rgn.x, rgn.y, rgn.width, rgn.height
        ScissorStack.region_box = (rl, rb, rw, rh)

        # remember the current scissor box settings so we can return to them when done
        ScissorStack.scissor_test_was_enabled = (bgl.glIsEnabled(bgl.GL_SCISSOR_TEST) == bgl.GL_TRUE)
        if ScissorStack.scissor_test_was_enabled:
            bgl.glGetIntegerv(bgl.GL_SCISSOR_BOX, ScissorStack.buf)
            pl, pb, pw, ph = ScissorStack.buf
            ScissorStack.stack = [(pl, pb, pw, ph)]
            # don't need to enable, because we are already scissoring!
            # TODO: this is not tested!
        else:
            ScissorStack.stack = [(0, 0, rw, rh)]
            bgl.glEnable(bgl.GL_SCISSOR_TEST)

        # we're ready to go!
        ScissorStack.is_started = True

    @staticmethod
    def end():
        assert ScissorStack.is_started, 'Attempting to end a non-started ScissorStack'
        assert len(ScissorStack.stack) == 1, 'Attempting to end a non-empty ScissorStack (size: %d)' % (len(ScissorStack.stack)-1)
        if not ScissorStack.scissor_test_was_enabled: bgl.glDisable(bgl.GL_SCISSOR_TEST)
        ScissorStack.is_started = False

    @staticmethod
    def _set_scissor():
        assert ScissorStack.is_started, 'Attempting to set scissor settings with non-started ScissorStack'
        bgl.glScissor(*ScissorStack.stack[-1])

    @staticmethod
    def push(nl, nt, nw, nh, clamp=True):
        # note: pos and size are already in region-coordinates, but it is specified from top-left corner

        assert ScissorStack.is_started, 'Attempting to push to a non-started ScissorStack!'

        # compute right and bottom of new scissor box
        nr = nl + (nw - 1)
        nb = nt - (nh + 1)

        if clamp:
            # get previous scissor box
            pl, pb, pw, ph = ScissorStack.stack[-1]
            pr = pl + (pw - 1)
            pt = pb + (ph - 1)
            # clamp new box to previous (extra +1/-1 is to handle 0-sized width/height if boxes do not intersect)
            cl, cr, ct, cb = mid(nl,pl,pr), mid(nr+1,pl,pr)-1, mid(nt+1,pt,pb)-1, mid(nb,pt,pb)
            cw, ch = max(0, cr - cl + 1), max(0, ct - cb + 1)
            ScissorStack.stack.append((cl, cb, cw, ch))
        else:
            ScissorStack.stack.append((nl, nb, nw, nh))

        ScissorStack._set_scissor()

    @staticmethod
    def pop():
        assert len(ScissorStack.stack) > 1, 'Attempting to pop from empty ScissorStack!'
        ScissorStack.stack.pop()
        ScissorStack._set_scissor()

    @staticmethod
    def get_current_view():
        assert ScissorStack.is_started
        assert ScissorStack.stack
        l, b, w, h = ScissorStack.stack[-1]
        r, t = l+w-1, b+h-1
        return (l, t, w, h)

    @staticmethod
    def is_visible():
        assert ScissorStack.is_started
        assert ScissorStack.stack
        vl, vb, vw, vh = ScissorStack.stack[-1]
        return vw > 0 and vh > 0

    @staticmethod
    def is_box_visible(l, t, w, h):
        assert ScissorStack.is_started
        assert ScissorStack.stack
        vl, vb, vw, vh = ScissorStack.get_current_view()
        vr, vt = vl+vw-1, vb+vh-1
        r, b = l+w-1, t-h+1
        return not (l > vr or r < vl or t < vb or b > vt)
