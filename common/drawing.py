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
from typing import List
import traceback
import functools
import contextlib
import urllib.request
from itertools import chain
from concurrent.futures import ThreadPoolExecutor

import bpy
import bgl
from bpy.types import BoolProperty
from mathutils import Matrix, Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d

from .hasher import Hasher
from .globals import Globals
from .shaders import Shader
from .blender import get_preferences, bversion
from .decorators import blender_version_wrapper
from .fontmanager import FontManager as fm
from .maths import Point2D, Vec2D, Point, Ray, Direction, mid, Color, Normal, Frame
from .profiler import profiler
from .debug import dprint, debugger
from .utils import find_fns,iter_pairs


class Cursors:
    # https://docs.blender.org/api/current/bpy.types.Window.html#bpy.types.Window.cursor_set
    _cursors = {

        # blender cursors
        'DEFAULT':      'DEFAULT',
        'NONE':         'NONE',
        'WAIT':         'WAIT',
        'CROSSHAIR':    'CROSSHAIR',
        'MOVE_X':       'MOVE_X',
        'MOVE_Y':       'MOVE_Y',
        'KNIFE':        'KNIFE',
        'TEXT':         'TEXT',
        'PAINT_BRUSH':  'PAINT_BRUSH',
        'HAND':         'HAND',
        'SCROLL_X':     'SCROLL_X',
        'SCROLL_Y':     'SCROLL_Y',
        'EYEDROPPER':   'EYEDROPPER',

        # lower case version of blender cursors
        'default':      'DEFAULT',
        'none':         'NONE',
        'wait':         'WAIT',
        'crosshair':    'CROSSHAIR',
        'move_x':       'MOVE_X',
        'move_y':       'MOVE_Y',
        'knife':        'KNIFE',
        'text':         'TEXT',
        'paint_brush':  'PAINT_BRUSH',
        'hand':         'HAND',
        'scroll_x':     'SCROLL_X',
        'scroll_y':     'SCROLL_Y',
        'eyedropper':   'EYEDROPPER',
    }

    @staticmethod
    def __getattr__(cursor):
        assert cursor in Cursors._cursors
        return Cursors._cursors.get(cursor, 'DEFAULT')

    @staticmethod
    def set(cursor):
        # print('Cursors.set', cursor)
        cursor = Cursors._cursors.get(cursor, 'DEFAULT')
        for wm in bpy.data.window_managers:
            for win in wm.windows:
                win.cursor_modal_set(cursor)

    @property
    @staticmethod
    def cursor(): return 'DEFAULT'   # TODO: how to get??
    @cursor.setter
    @staticmethod
    def cursor(cursor): Cursors.set(cursor)

    @staticmethod
    def warp(x, y): bpy.context.window.cursor_warp(x, y)

Globals.set(Cursors())




if bversion() >= "2.80":
    import gpu
    from gpu.types import GPUShader
    from gpu_extras.batch import batch_for_shader

    # https://docs.blender.org/api/blender2.8/gpu.html#triangle-with-custom-shader

    def create_shader(fn_glsl):
        path_here = os.path.dirname(os.path.realpath(__file__))
        path_shaders = os.path.join(path_here, 'shaders')
        path_glsl = os.path.join(path_shaders, fn_glsl)
        txt = open(path_glsl, 'rt').read()
        lines = txt.splitlines()
        mode = 'common'
        source = {'common':[], 'vertex':[], 'fragment':[]}
        for line in lines:
            if   line == '// vertex shader':   mode = 'vertex'
            elif line == '// fragment shader': mode = 'fragment'
            else: source[mode].append(line)
        vert_source = '\n'.join(source['common'] + source['vertex'])
        frag_source = '\n'.join(source['common'] + source['fragment'])
        try:
            return GPUShader(vert_source, frag_source)
        except Exception as e:
            print('ERROR WHILE COMPILING SHADER %s' % fn_glsl)
            assert False

    # 2D point
    shader_2D_point = create_shader('point_2D.glsl')
    batch_2D_point = batch_for_shader(shader_2D_point, 'TRIS', {"pos": [(0,0), (1,0), (1,1), (0,0), (1,1), (0,1)]})

    # 2D line segment
    shader_2D_lineseg = create_shader('lineseg_2D.glsl')
    batch_2D_lineseg = batch_for_shader(shader_2D_lineseg, 'TRIS', {"pos": [(0,0), (1,0), (1,1), (0,0), (1,1), (0,1)]})

    # 2D circle
    shader_2D_circle = create_shader('circle_2D.glsl')
    # create batch to draw large triangle that covers entire clip space (-1,-1)--(+1,+1)
    cnt = 100
    pts = [
        p for i0 in range(cnt)
        for p in [
            ((i0+0)/cnt,0), ((i0+1)/cnt,0), ((i0+1)/cnt,1),
            ((i0+0)/cnt,0), ((i0+1)/cnt,1), ((i0+0)/cnt,1),
        ]
    ]
    batch_2D_circle = batch_for_shader(shader_2D_circle, 'TRIS', {"pos": pts})

    # 3D circle
    shader_3D_circle = create_shader('circle_3D.glsl')
    # create batch to draw large triangle that covers entire clip space (-1,-1)--(+1,+1)
    cnt = 100
    pts = [
        p for i0 in range(cnt)
        for p in [
            ((i0+0)/cnt,0), ((i0+1)/cnt,0), ((i0+1)/cnt,1),
            ((i0+0)/cnt,0), ((i0+1)/cnt,1), ((i0+0)/cnt,1),
        ]
    ]
    batch_3D_circle = batch_for_shader(shader_3D_circle, 'TRIS', {"pos": pts})

    # 3D triangle
    shader_3D_triangle = create_shader('triangle_3D.glsl')
    batch_3D_triangle = batch_for_shader(shader_3D_triangle, 'TRIS', {'pos': [(1,0), (0,1), (0,0)]})

    # 3D triangle
    shader_2D_triangle = create_shader('triangle_2D.glsl')
    batch_2D_triangle = batch_for_shader(shader_2D_triangle, 'TRIS', {'pos': [(1,0), (0,1), (0,0)]})



class Drawing:
    _instance = None
    _dpi_mult = 1
    _custom_dpi_mult = 1
    _prefs = get_preferences()

    @staticmethod
    def get_custom_dpi_mult():
        return Drawing._custom_dpi_mult
    @staticmethod
    def set_custom_dpi_mult(v):
        Drawing._custom_dpi_mult = v
        Drawing.update_dpi()

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
        Drawing._dpi_mult = Drawing._custom_dpi_mult * Drawing._prefs.view.ui_scale * Drawing._prefs.system.dpi / 72 #* Drawing._prefs.system.pixel_size

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

        self.area,self.space,self.rgn,self.r3d,self.window = None,None,None,None,None
        # self.font_id = 0
        self.last_font_key = None
        self.fontid = 0
        self.fontsize = None
        self.fontsize_scaled = None
        self.line_cache = {}
        self.size_cache = {}
        self.set_font_size(12)

    def set_region(self, area, space, rgn, r3d, window):
        self.area = area
        self.space = space
        self.rgn = rgn
        self.r3d = r3d
        self.window = window

    @staticmethod
    def set_cursor(cursor): Cursors.set(cursor)

    def scale(self, s): return s * self._dpi_mult if s is not None else None
    def unscale(self, s): return s / self._dpi_mult if s is not None else None
    def get_dpi_mult(self): return self._dpi_mult
    def get_pixel_size(self): return self._pixel_size
    def line_width(self, width): bgl.glLineWidth(max(1, self.scale(width)))
    def point_size(self, size): bgl.glPointSize(max(1, self.scale(size)))

    def set_font_color(self, fontid, color):
        fm.color(color, fontid=fontid)

    def set_font_size(self, fontsize, fontid=None, force=False):
        if fontid is None: fontid = fm._last_fontid
        else: fontid = fm.load(fontid)
        fontsize_prev = self.fontsize
        fontsize, fontsize_scaled = int(fontsize), int(int(fontsize) * self._dpi_mult)
        cache_key = (fontid, fontsize_scaled)
        if self.last_font_key == cache_key and not force: return fontsize_prev
        fm.size(fontsize_scaled, 72, fontid=fontid)
        if cache_key not in self.line_cache:
            # cache away useful details about font (line height, line base)
            dprint('Caching new scaled font size:', cache_key)
            all_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()`~[}{]/?=+\\|-_\'",<.>'
            all_caps = all_chars.upper()
            self.line_cache[cache_key] = {
                'line height': round(fm.dimensions(all_chars, fontid=fontid)[1] + self.scale(4)),
                'line base': round(fm.dimensions(all_caps, fontid=fontid)[1]),
            }
        info = self.line_cache[cache_key]
        self.line_height = info['line height']
        self.line_base = info['line base']
        self.fontid = fontid
        self.fontsize = fontsize
        self.fontsize_scaled = fontsize_scaled
        self.last_font_key = cache_key

        return fontsize_prev

    def get_text_size_info(self, text, item, fontsize=None, fontid=None):
        if fontsize or fontid: size_prev = self.set_font_size(fontsize, fontid=fontid)

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

    @blender_version_wrapper('<', '2.80')
    def text_color_set(self, color, fontid):
        if color is not None: bgl.glColor4f(*color)
    @blender_version_wrapper('>=', '2.80')
    def text_color_set(self, color, fontid):
        if color is not None: fm.color(color, fontid=fontid)

    def text_draw2D(self, text, pos:Point2D, *, color=None, dropshadow=None, fontsize=None, fontid=None, lineheight=True):
        if fontsize: size_prev = self.set_font_size(fontsize, fontid=fontid)

        lines = str(text).splitlines()
        l,t = round(pos[0]),round(pos[1])
        lh,lb = self.line_height,self.line_base

        if dropshadow:
            self.text_draw2D(text, (l+1,t-1), color=dropshadow, fontsize=fontsize, fontid=fontid, lineheight=lineheight)

        bgl.glEnable(bgl.GL_BLEND)
        self.text_color_set(color, fontid)
        for line in lines:
            fm.draw(line, xyz=(l, t - lb, 0), fontid=fontid)
            t -= lh if lineheight else self.get_text_height(line)

        if fontsize: self.set_font_size(size_prev, fontid=fontid)

    @profiler.function
    def text_draw2D_simple(self, text, pos:Point2D):
        l,t = round(pos[0]),round(pos[1])
        lb = self.line_base
        fm.draw_simple(text, xyz=(l, t - lb, 0))


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
        if not self.r3d: return None
        w,h = self.rgn.width,self.rgn.height
        if not hasattr(self, '_get_pixel_matrix_cache'):
            self._get_pixel_matrix_cache = {'w':-1, 'h':-1, 'm':None}
        cache = self._get_pixel_matrix_cache
        if cache['w'] != w or cache['h'] != h:
            cache['w'],cache['h'] = w,h
            cache['m'] = Matrix([[2/w,0,0,-1], [0,2/h,0,-1], [0,0,1,0], [0,0,0,1]])
        return cache['m']

    def get_pixel_matrix_buffer(self):
        if not self.r3d: return None
        return bgl.Buffer(bgl.GL_FLOAT, [4,4], self.get_pixel_matrix_list())

    def get_view_matrix_list(self):
        return list(self.get_view_matrix()) if self.r3d else None

    def get_view_matrix(self):
        return self.r3d.perspective_matrix if self.r3d else None

    def get_view_version(self):
        if not self.r3d: return None
        return Hasher(self.r3d.view_matrix, self.space.lens)

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

    @blender_version_wrapper('<', '2.80')
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
    @blender_version_wrapper('>=', '2.80')
    def glCheckError(self, title):
        err = bgl.glGetError()
        if err == bgl.GL_NO_ERROR: return

        derrs = {
            bgl.GL_INVALID_ENUM: 'invalid enum',
            bgl.GL_INVALID_VALUE: 'invalid value',
            bgl.GL_INVALID_OPERATION: 'invalid operation',
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

    # draw line segment in screen space
    @blender_version_wrapper('<', '2.80')
    def draw2D_line(self, p0:Point2D, p1:Point2D, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        # TODO: better test this!
        print('THIS IS NOT TESTED!')
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        if not hasattr(Drawing, '_line_data'):
            sizeOfFloat, sizeOfInt = 4, 4
            vbos = bgl.Buffer(bgl.GL_INT, 1)
            bgl.glGenBuffers(1, vbos)
            vbo_weights = vbos[0]
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vbo_weights)
            weights = [[0,0], [1,0], [1,1], [0,0], [1,1], [0,1]]
            weightsSize = [len(weights), len(weights[0])]
            buf_weights = bgl.Buffer(bgl.GL_FLOAT, weightsSize, weights)
            bgl.glBufferData(bgl.GL_ARRAY_BUFFER, weightsSize[0] * weightsSize[1] * sizeOfFloat, buf_weights, bgl.GL_STATIC_DRAW)
            del buf_weights
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)
            shader = Shader.load_from_file('linesegment', 'linesegment.glsl')
            Drawing._line_data = {
                'vbos': vbos,
                'vbo_weights': vbo_weights,
                'gltype': bgl.GL_TRIANGLES,
                'shader': shader,
                'size_weights': weightsSize,
            }
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        d = Drawing._line_data
        shader = d['shader']

        shader.enable()
        shader.assign('uScreenSize', (self.area.width, self.area.height))
        shader.assign('uPos0', p0)
        shader.assign('uPos1', p1)
        shader.assign('uColor0', color0)
        shader.assign('uColor1', color1)
        shader.assign('uWidth', width)
        shader.assign('uStipple', stipple)
        shader.assign('uStippleOffset', offset)
        mvpmatrix_buffer = bgl.Buffer(bgl.GL_FLOAT, [4,4], self.get_pixel_matrix())
        shader.assign('uMVPMatrix', mvpmatrix_buffer)
        shader.vertexAttribPointer(d['vbo_weights'], 'aWeight', d['size_weights'][1], bgl.GL_FLOAT)
        bgl.glDrawArrays(d['gltype'], 0, d['size_weights'][0])
        shader.disableVertexAttribArray('aWeight')
        shader.disable()

    @blender_version_wrapper('>=', '2.80')
    def draw2D_point(self, pt:Point2D, color:Color, *, radius=1, border=0, borderColor=None):
        radius = self.scale(radius)
        border = self.scale(border)
        if borderColor is None: borderColor = (0,0,0,0)
        shader_2D_point.bind()
        shader_2D_point.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_point.uniform_float('MVPMatrix', self.get_pixel_matrix())
        shader_2D_point.uniform_float('radius', radius)
        shader_2D_point.uniform_float('border', border)
        shader_2D_point.uniform_float('border', border)
        shader_2D_point.uniform_float('color', color)
        shader_2D_point.uniform_float('colorBorder', borderColor)
        shader_2D_point.uniform_float('center', pt)
        batch_2D_point.draw(shader_2D_point)
        gpu.shader.unbind()

    @blender_version_wrapper('>=', '2.80')
    def draw2D_points(self, pts:[Point2D], color:Color, *, radius=1, border=0, borderColor=None):
        radius = self.scale(radius)
        border = self.scale(border)
        if borderColor is None: borderColor = (0,0,0,0)
        shader_2D_point.bind()
        shader_2D_point.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_point.uniform_float('MVPMatrix', self.get_pixel_matrix())
        shader_2D_point.uniform_float('radius', radius)
        shader_2D_point.uniform_float('border', border)
        shader_2D_point.uniform_float('border', border)
        shader_2D_point.uniform_float('color', color)
        shader_2D_point.uniform_float('colorBorder', borderColor)
        for pt in pts:
            shader_2D_point.uniform_float('center', pt)
            batch_2D_point.draw(shader_2D_point)
        gpu.shader.unbind()

    # draw line segment in screen space
    @blender_version_wrapper('>=', '2.80')
    def draw2D_line(self, p0:Point2D, p1:Point2D, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        shader_2D_lineseg.bind()
        shader_2D_lineseg.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_lineseg.uniform_float('pos0', p0)
        shader_2D_lineseg.uniform_float('pos1', p1)
        shader_2D_lineseg.uniform_float('color0', color0)
        shader_2D_lineseg.uniform_float('color1', color1)
        shader_2D_lineseg.uniform_float('width', width)
        shader_2D_lineseg.uniform_float('stipple', stipple)
        shader_2D_lineseg.uniform_float('stippleOffset', offset)
        shader_2D_lineseg.uniform_float('MVPMatrix', self.get_pixel_matrix())
        batch_2D_lineseg.draw(shader_2D_lineseg)
        gpu.shader.unbind()

    @blender_version_wrapper('>=', '2.80')
    def draw2D_lines(self, points, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        self.glCheckError('starting draw2D_lines')
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        shader_2D_lineseg.bind()
        shader_2D_lineseg.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_lineseg.uniform_float('color0', color0)
        shader_2D_lineseg.uniform_float('color1', color1)
        shader_2D_lineseg.uniform_float('width', width)
        shader_2D_lineseg.uniform_float('stipple', stipple)
        shader_2D_lineseg.uniform_float('stippleOffset', offset)    # TODO: should offset be a list?
        shader_2D_lineseg.uniform_float('MVPMatrix', self.get_pixel_matrix())
        for i in range(len(points)//2):
            p0,p1 = points[i*2:i*2+2]
            if p0 is None or p1 is None: continue
            shader_2D_lineseg.uniform_float('pos0', p0)
            shader_2D_lineseg.uniform_float('pos1', p1)
            batch_2D_lineseg.draw(shader_2D_lineseg)
        gpu.shader.unbind()
        self.glCheckError('done with draw2D_lines')

    @blender_version_wrapper('>=', '2.80')
    def draw3D_lines(self, points, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        self.glCheckError('starting draw3D_lines')
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        shader_2D_lineseg.bind()
        shader_2D_lineseg.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_lineseg.uniform_float('color0', color0)
        shader_2D_lineseg.uniform_float('color1', color1)
        shader_2D_lineseg.uniform_float('width', width)
        shader_2D_lineseg.uniform_float('stipple', stipple)
        shader_2D_lineseg.uniform_float('stippleOffset', offset)    # TODO: should offset be a list?
        shader_2D_lineseg.uniform_float('MVPMatrix', self.get_view_matrix())
        for i in range(len(points)//2):
            p0,p1 = points[i*2:i*2+2]
            if p0 is None or p1 is None: continue
            shader_2D_lineseg.uniform_float('pos0', p0)
            shader_2D_lineseg.uniform_float('pos1', p1)
            batch_2D_lineseg.draw(shader_2D_lineseg)
        gpu.shader.unbind()
        self.glCheckError('done with draw3D_lines')

    @blender_version_wrapper('>=', '2.80')
    def draw2D_linestrip(self, points, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        shader_2D_lineseg.bind()
        shader_2D_lineseg.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_lineseg.uniform_float('color0', color0)
        shader_2D_lineseg.uniform_float('color1', color1)
        shader_2D_lineseg.uniform_float('width', width)
        shader_2D_lineseg.uniform_float('stipple', stipple)
        shader_2D_lineseg.uniform_float('MVPMatrix', self.get_pixel_matrix())
        for p0,p1 in iter_pairs(points, False):
            shader_2D_lineseg.uniform_float('pos0', p0)
            shader_2D_lineseg.uniform_float('pos1', p1)
            shader_2D_lineseg.uniform_float('stippleOffset', offset)
            offset += (p1 - p0).length
            batch_2D_lineseg.draw(shader_2D_lineseg)
        gpu.shader.unbind()

    # draw circle in screen space
    @blender_version_wrapper('>=', '2.80')
    def draw2D_circle(self, center:Point2D, radius:float, color0:Color, *, color1=None, width=1, stipple=None, offset=0):
        if color1 is None: color1 = (color0[0],color0[1],color0[2],0)
        radius = self.scale(radius)
        width = self.scale(width)
        stipple = [self.scale(v) for v in stipple] if stipple else [1,0]
        offset = self.scale(offset)
        shader_2D_circle.bind()
        shader_2D_circle.uniform_float('screensize', (self.area.width, self.area.height))
        shader_2D_circle.uniform_float('center', center)
        shader_2D_circle.uniform_float('radius', radius)
        shader_2D_circle.uniform_float('color0', color0)
        shader_2D_circle.uniform_float('color1', color1)
        shader_2D_circle.uniform_float('width', width)
        shader_2D_circle.uniform_float('stipple', stipple)
        shader_2D_circle.uniform_float('stippleOffset', offset)
        shader_2D_circle.uniform_float('MVPMatrix', self.get_pixel_matrix())
        batch_2D_circle.draw(shader_2D_circle)
        gpu.shader.unbind()

    @blender_version_wrapper('>=', '2.80')
    def draw3D_circle(self, center:Point, radius:float, color:Color, *, width=1, n:Normal=None, x:Direction=None, y:Direction=None):
        assert n is not None or x is not None or y is not None, 'Must specify at least one of n,x,y'
        f = Frame(o=center, x=x, y=y, z=n)
        radius = self.scale(radius)
        width = self.scale(width)
        shader_3D_circle.bind()
        shader_3D_circle.uniform_float('center', f.o)
        shader_3D_circle.uniform_float('radius', radius)
        shader_3D_circle.uniform_float('color',  color)
        shader_3D_circle.uniform_float('width',  width)
        shader_3D_circle.uniform_float('plane_x', f.x)
        shader_3D_circle.uniform_float('plane_y', f.y)
        shader_3D_circle.uniform_float('MVPMatrix', self.get_view_matrix())
        batch_3D_circle.draw(shader_3D_circle)
        gpu.shader.unbind()

    @blender_version_wrapper('>=', '2.80')
    def draw3D_triangles(self, points:[Point], colors:[Color]):
        self.glCheckError('starting draw3D_triangles')
        shader_3D_triangle.bind()
        shader_3D_triangle.uniform_float('MVPMatrix', self.get_view_matrix())
        for i in range(0, len(points), 3):
            p0,p1,p2 = points[i:i+3]
            c0,c1,c2 = colors[i:i+3]
            if p0 is None or p1 is None or p2 is None: continue
            if c0 is None or c1 is None or c2 is None: continue
            shader_3D_triangle.uniform_float('pos0', p0)
            shader_3D_triangle.uniform_float('color0', c0)
            shader_3D_triangle.uniform_float('pos1', p1)
            shader_3D_triangle.uniform_float('color1', c1)
            shader_3D_triangle.uniform_float('pos2', p2)
            shader_3D_triangle.uniform_float('color2', c2)
            batch_3D_triangle.draw(shader_3D_triangle)
        gpu.shader.unbind()
        self.glCheckError('done with draw3D_triangles')

    @contextlib.contextmanager
    def draw(self, draw_type:"CC_DRAW"):
        assert getattr(self, '_draw', None) is None, 'Cannot nest Drawing.draw calls'
        self._draw = draw_type
        self.glCheckError('starting draw')
        try:
            draw_type.begin()
            yield draw_type
            draw_type.end()
        except Exception as e:
            print('Exception caught while in Drawing.draw with %s' % str(draw_type))
            debugger.print_exception()
        self.glCheckError('done with draw')
        self._draw = None


Drawing.initialize()


######################################################################################################
# The following classes mimic the immediate mode for (old-school way of) drawing geometry
#   glBegin(GL_TRIANGLES)
#   glColor3f(p)
#   glVertex3f(p)
#   glEnd()

class CC_DRAW:
    _point_size:float = 1
    _line_width:float = 1
    _border_width:float = 0
    _border_color:Color = Color((0, 0, 0, 0))
    _stipple_pattern:List[float] = [1,0]
    _stipple_offset:float = 0
    _stipple_color:Color = Color((0, 0, 0, 0))

    _default_color = Color((1, 1, 1, 1))
    _default_point_size = 1
    _default_line_width = 1
    _default_border_width = 0
    _default_border_color = Color((0, 0, 0, 0))
    _default_stipple_pattern = [1,0]
    _default_stipple_color = Color((0, 0, 0, 0))

    @classmethod
    def reset(cls):
        s = Drawing._instance.scale
        CC_DRAW._point_size = s(CC_DRAW._default_point_size)
        CC_DRAW._line_width = s(CC_DRAW._default_line_width)
        CC_DRAW._border_width = s(CC_DRAW._default_border_width)
        CC_DRAW._border_color = CC_DRAW._default_border_color
        CC_DRAW._stipple_offset = 0
        CC_DRAW._stipple_pattern = [s(v) for v in CC_DRAW._default_stipple_pattern]
        CC_DRAW._stipple_color = CC_DRAW._default_stipple_color
        cls.update()

    @classmethod
    def update(cls): pass

    @classmethod
    def point_size(cls, size):
        s = Drawing._instance.scale
        CC_DRAW._point_size = s(size)
        cls.update()

    @classmethod
    def line_width(cls, width):
        s = Drawing._instance.scale
        CC_DRAW._line_width = s(width)
        cls.update()

    @classmethod
    def border(cls, *, width=None, color=None):
        s = Drawing._instance.scale
        if width is not None:
            CC_DRAW._border_width = s(width)
        if color is not None:
            CC_DRAW._border_color = color
        cls.update()

    @classmethod
    def stipple(cls, *, pattern=None, offset=None, color=None):
        s = Drawing._instance.scale
        if pattern is not None:
            CC_DRAW._stipple_pattern = [s(v) for v in pattern]
        if offset is not None:
            CC_DRAW._stipple_offset = s(offset)
        if color is not None:
            CC_DRAW._stipple_color = color
        cls.update()

    @classmethod
    def end(cls):
        gpu.shader.unbind()
CC_DRAW.reset()


class CC_2D_POINTS(CC_DRAW):
    @classmethod
    def begin(cls):
        shader_2D_point.bind()
        shader_2D_point.uniform_float('MVPMatrix', Drawing._instance.get_pixel_matrix())
        shader_2D_point.uniform_float('screensize', (Drawing._instance.area.width, Drawing._instance.area.height))
        shader_2D_point.uniform_float('color', cls._default_color)
        cls.update()

    @classmethod
    def update(cls):
        shader_2D_point.uniform_float('radius', cls._point_size)
        shader_2D_point.uniform_float('border', cls._border_width)
        shader_2D_point.uniform_float('colorBorder', cls._border_color)

    @classmethod
    def color(cls, c:Color):
        shader_2D_point.uniform_float('color', c)

    @classmethod
    def vertex(cls, p:Point2D):
        if p:
            shader_2D_point.uniform_float('center', p)
            batch_2D_point.draw(shader_2D_point)


class CC_2D_LINES(CC_DRAW):
    @classmethod
    def begin(cls):
        shader_2D_lineseg.bind()
        shader_2D_lineseg.uniform_float('MVPMatrix', Drawing._instance.get_pixel_matrix())
        shader_2D_lineseg.uniform_float('screensize', (Drawing._instance.area.width, Drawing._instance.area.height))
        shader_2D_lineseg.uniform_float('color0', cls._default_color)
        cls.stipple(offset=0)
        cls._c = 0
        cls._last_p = None

    @classmethod
    def update(cls):
        shader_2D_lineseg.uniform_float('color1', cls._stipple_color)
        shader_2D_lineseg.uniform_float('width', cls._line_width)
        shader_2D_lineseg.uniform_float('stipple', cls._stipple_pattern)
        shader_2D_lineseg.uniform_float('stippleOffset', cls._stipple_offset)

    @classmethod
    def color(cls, c:Color):
        shader_2D_lineseg.uniform_float('color0', c)

    @classmethod
    def vertex(cls, p:Point2D):
        if p: shader_2D_lineseg.uniform_float('pos%d' % cls._c, p)
        cls._c = (cls._c + 1) % 2
        if cls._c == 0 and cls._last_p and p: batch_2D_lineseg.draw(shader_2D_lineseg)
        cls._last_p = p

class CC_2D_LINE_STRIP(CC_2D_LINES):
    @classmethod
    def begin(cls):
        super().begin()
        cls._last_p = None

    @classmethod
    def vertex(cls, p:Point2D):
        if cls._last_p is None:
            cls._last_p = p
        else:
            if cls._last_p and p:
                shader_2D_lineseg.uniform_float('pos0', cls._last_p)
                shader_2D_lineseg.uniform_float('pos1', p)
                batch_2D_lineseg.draw(shader_2D_lineseg)
            cls._last_p = p

class CC_2D_LINE_LOOP(CC_2D_LINES):
    @classmethod
    def begin(cls):
        super().begin()
        cls._first_p = None
        cls._last_p = None

    @classmethod
    def vertex(cls, p:Point2D):
        if cls._first_p is None:
            cls._first_p = cls._last_p = p
        else:
            if cls._last_p and p:
                shader_2D_lineseg.uniform_float('pos0', cls._last_p)
                shader_2D_lineseg.uniform_float('pos1', p)
                batch_2D_lineseg.draw(shader_2D_lineseg)
            cls._last_p = p

    @classmethod
    def end(cls):
        if cls._last_p and cls._first_p:
            shader_2D_lineseg.uniform_float('pos0', cls._last_p)
            shader_2D_lineseg.uniform_float('pos1', cls._first_p)
            batch_2D_lineseg.draw(shader_2D_lineseg)
        super().end()


class CC_2D_TRIANGLES(CC_DRAW):
    @classmethod
    def begin(cls):
        shader_2D_triangle.bind()
        #shader_2D_triangle.uniform_float('screensize', (Drawing._instance.area.width, Drawing._instance.area.height))
        shader_2D_triangle.uniform_float('MVPMatrix', Drawing._instance.get_pixel_matrix())
        cls._c = 0
        cls._last_color = None
        cls._last_p0 = None
        cls._last_p1 = None

    @classmethod
    def color(cls, c:Color):
        if c is None: return
        shader_2D_triangle.uniform_float('color%d' % cls._c, c)
        cls._last_color = c

    @classmethod
    def vertex(cls, p:Point2D):
        if p: shader_2D_triangle.uniform_float('pos%d' % cls._c, p)
        cls._c = (cls._c + 1) % 3
        if cls._c == 0 and p and cls._last_p0 and cls._last_p1: batch_2D_triangle.draw(shader_2D_triangle)
        cls.color(cls._last_color)
        cls._last_p1 = cls._last_p0
        cls._last_p0 = p

class CC_2D_TRIANGLE_FAN(CC_DRAW):
    @classmethod
    def begin(cls):
        shader_2D_triangle.bind()
        shader_2D_triangle.uniform_float('MVPMatrix', Drawing._instance.get_pixel_matrix())
        cls._c = 0
        cls._last_color = None
        cls._first_p = None
        cls._last_p = None
        cls._is_first = True

    @classmethod
    def color(cls, c:Color):
        if c is None: return
        shader_2D_triangle.uniform_float('color%d' % cls._c, c)
        cls._last_color = c

    @classmethod
    def vertex(cls, p:Point2D):
        if p: shader_2D_triangle.uniform_float('pos%d' % cls._c, p)
        cls._c += 1
        if cls._c == 3:
            if p and cls._first_p and cls._last_p: batch_2D_triangle.draw(shader_2D_triangle)
            cls._c = 1
        cls.color(cls._last_color)
        if cls._is_first:
            cls._first_p = p
            cls._is_first = False
        else: cls._last_p = p

class CC_3D_TRIANGLES(CC_DRAW):
    @classmethod
    def begin(cls):
        shader_3D_triangle.bind()
        shader_3D_triangle.uniform_float('MVPMatrix', Drawing._instance.get_view_matrix())
        cls._c = 0
        cls._last_color = None
        cls._last_p0 = None
        cls._last_p1 = None

    @classmethod
    def color(cls, c:Color):
        if c is None: return
        shader_3D_triangle.uniform_float('color%d' % cls._c, c)
        cls._last_color = c

    @classmethod
    def vertex(cls, p:Point):
        if p: shader_3D_triangle.uniform_float('pos%d' % cls._c, p)
        cls._c = (cls._c + 1) % 3
        if cls._c == 0 and p and cls._last_p0 and cls._last_p1: batch_3D_triangle.draw(shader_3D_triangle)
        cls.color(cls._last_color)
        cls._last_p1 = cls._last_p0
        cls._last_p0 = p

######################################################################################################


class ScissorStack:
    buf = bgl.Buffer(bgl.GL_INT, 4)
    is_started = False
    scissor_test_was_enabled = False
    stack = None                        # stack of (l,t,w,h) in region-coordinates, because viewport is set to region
    msg_stack = None

    @staticmethod
    def start(context):
        assert not ScissorStack.is_started, 'Attempting to start a started ScissorStack'

        # region pos and size are window-coordinates
        rgn = context.region
        rl,rb,rw,rh = rgn.x, rgn.y, rgn.width, rgn.height
        rt = rb + rh - 1

        # remember the current scissor box settings so we can return to them when done
        ScissorStack.scissor_test_was_enabled = (bgl.glIsEnabled(bgl.GL_SCISSOR_TEST) == bgl.GL_TRUE)
        if ScissorStack.scissor_test_was_enabled:
            bgl.glGetIntegerv(bgl.GL_SCISSOR_BOX, ScissorStack.buf)
            pl, pb, pw, ph = ScissorStack.buf
            pt = pb + ph - 1
            ScissorStack.stack = [(pl, pt, pw, ph)]
            ScissorStack.msg_stack = ['init']
            # don't need to enable, because we are already scissoring!
            # TODO: this is not tested!
        else:
            ScissorStack.stack = [(0, rh - 1, rw, rh)]
            ScissorStack.msg_stack = ['init']
            bgl.glEnable(bgl.GL_SCISSOR_TEST)

        # we're ready to go!
        ScissorStack.is_started = True

    @staticmethod
    def end(force=False):
        if not force:
            assert ScissorStack.is_started, 'Attempting to end a non-started ScissorStack'
            assert len(ScissorStack.stack) == 1, 'Attempting to end a non-empty ScissorStack (size: %d)' % (len(ScissorStack.stack)-1)
        else:
            ScissorStack.stack = ScissorStack.stack[:1]
        if not ScissorStack.scissor_test_was_enabled: bgl.glDisable(bgl.GL_SCISSOR_TEST)
        ScissorStack.is_started = False

    @staticmethod
    def _set_scissor():
        assert ScissorStack.is_started, 'Attempting to set scissor settings with non-started ScissorStack'
        l,t,w,h = ScissorStack.stack[-1]
        b = t - (h - 1)
        bgl.glScissor(l, b, w, h)

    @staticmethod
    def push(nl, nt, nw, nh, msg='', clamp=True):
        # note: pos and size are already in region-coordinates, but it is specified from top-left corner

        assert ScissorStack.is_started, 'Attempting to push to a non-started ScissorStack!'

        # compute right and bottom of new scissor box
        nr = nl + (nw - 1)
        nb = nt - (nh - 1) - 1      # sub 1 (not certain why this needs to be)

        if clamp:
            # get previous scissor box
            pl, pt, pw, ph = ScissorStack.stack[-1]
            pr = pl + (pw - 1)
            pb = pt - (ph - 1)
            # clamp new box to previous (extra +1/-1 is to handle 0-sized width/height if boxes do not intersect)
            #cl, cr, ct, cb = mid(nl,pl,pr), mid(nr+1,pl,pr)-1, mid(nt+1,pt,pb)-1, mid(nb,pt,pb)
            cl, cr, ct, cb = mid(nl,pl,pr), mid(nr,pl,pr), mid(nt,pt,pb), mid(nb,pt,pb)
            cw, ch = max(0, cr - cl + 1), max(0, ct - cb + 1)
            ScissorStack.stack.append((int(cl), int(ct), int(cw), int(ch)))
            ScissorStack.msg_stack.append(msg)
        else:
            ScissorStack.stack.append((int(nl), int(nt), int(nw), int(nh)))
            ScissorStack.msg_stack.append(msg)

        ScissorStack._set_scissor()

    @staticmethod
    def pop():
        assert len(ScissorStack.stack) > 1, 'Attempting to pop from empty ScissorStack!'
        ScissorStack.stack.pop()
        ScissorStack.msg_stack.pop()
        ScissorStack._set_scissor()

    @staticmethod
    @contextlib.contextmanager
    def wrap(*args, disabled=False, **kwargs):
        if disabled:
            yield None
            return
        try:
            ScissorStack.push(*args, **kwargs)
            yield None
            ScissorStack.pop()
        except Exception as e:
            ScissorStack.pop()
            print('Caught exception while scissoring:', args, kwargs)
            Globals.debugger.print_exception()
            raise e

    @staticmethod
    def get_current_view():
        assert ScissorStack.is_started
        assert ScissorStack.stack
        l, t, w, h = ScissorStack.stack[-1]
        #r, b = l + (w - 1), t - (h - 1)
        return (l, t, w, h)

    @staticmethod
    def print_view_stack():
        for i,st in enumerate(ScissorStack.stack):
            l, t, w, h = st
            #r, b = l + (w - 1), t - (h - 1)
            print(('  '*i) + str((l,t,w,h)) + ' ' + ScissorStack.msg_stack[i])

    @staticmethod
    def is_visible():
        vl,vt,vw,vh = ScissorStack.get_current_view()
        return vw > 0 and vh > 0

    @staticmethod
    @profiler.function
    def is_box_visible(l, t, w, h):
        vl, vt, vw, vh = ScissorStack.get_current_view()
        if vw <= 0 or vh <= 0: return False
        vr, vb = vl + (vw - 1), vt - (vh - 1)
        r, b = l + (w - 1), t - (h - 1)
        return not (l > vr or r < vl or t < vb or b > vt)


class DrawCallbacks:
    def __init__(self):
        self.wrapper = self._create_wrapper()
        self.wrapper_pre = self._wrapper_pre
        self._called_pre = False

    def _wrapper_pre(self, fn):
        fn.drawmode = 'pre'
        return fn

    def _create_wrapper(self):
        drawcb = self
        class DrawWrapper:
            def __init__(self, mode):
                assert mode in {'pre3d','post3d','post2d'}
                self.mode = mode
            def __call__(self, fn):
                self.fn = fn
                self.fnname = fn.__name__
                def run(*args, **kwargs):
                    try:
                        return fn(*args, **kwargs)
                    except Exception as e:
                        print('Caught exception in drawing "%s", calling "%s"' % (self.mode, self.fnname))
                        debugger.print_exception()
                        print(e)
                        return None
                run.fnname = self.fnname
                run.drawmode = self.mode
                return run
        return DrawWrapper

    def init(self, obj):
        self.obj = obj
        self._fns = {
            'pre3d':  [],
            'post3d': [],
            'post2d': [],
            'pre':    [],
        }
        for (m,fn) in find_fns(self.obj, 'drawmode'):
            self._fns[m] += [fn]

    def _call(self, n):
        for fn in self._fns[n]: fn(self.obj)
    def reset_pre(self):
        self._called_pre = False
    def _pre(self):
        if self._called_pre: return
        self._call('pre')
        self._called_pre = True
    def pre3d(self):
        self._pre()
        self._call('pre3d')
    def post3d(self):
        self._pre()
        self._call('post3d')
    def post2d(self):
        self._pre()
        self._call('post2d')


