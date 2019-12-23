'''
Copyright (C) 2016 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson, and Patrick Moore

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


'''
notes: something is really wrong here to have such poor performance

Below are some related, interesting links

- https://machinesdontcare.wordpress.com/2008/02/02/glsl-discard-z-fighting-supersampling/
- https://developer.apple.com/library/archive/documentation/3DDrawing/Conceptual/OpenGLES_ProgrammingGuide/BestPracticesforShaders/BestPracticesforShaders.html
- https://stackoverflow.com/questions/16415037/opengl-core-profile-incredible-slowdown-on-os-x
'''


import os
import re
import math
import ctypes
import traceback

import bmesh
import bgl
import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d, region_2d_to_vector_3d
)
from bpy_extras.view3d_utils import (
    region_2d_to_location_3d, region_2d_to_origin_3d
)
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

from .debug import dprint
from .shaders import Shader, buf_zero
from .utils import shorten_floats
from .maths import Point, Direction, Frame, XForm
from .maths import invert_matrix, matrix_normal
from .profiler import profiler
from .decorators import blender_version_wrapper



# note: not all supported by user system, but we don't need full functionality
# https://en.wikipedia.org/wiki/OpenGL_Shading_Language#Versions
#     OpenGL  GLSL    OpenGL  GLSL
#      2.0    110      4.0    400
#      2.1    120      4.1    410
#      3.0    130      4.2    420
#      3.1    140      4.3    430
#      3.2    150      4.4    440
#      3.3    330      4.5    450
#                      4.6    460
print('(bmesh_render) GLSL Version:', bgl.glGetString(bgl.GL_SHADING_LANGUAGE_VERSION))


def setupBMeshShader(shader):
    ctx = bpy.context
    area, spc, r3d = ctx.area, ctx.space_data, ctx.space_data.region_3d
    shader.assign('perspective', 1.0 if r3d.view_perspective !=
                  'ORTHO' else 0.0)
    shader.assign('clip_start', spc.clip_start)
    shader.assign('clip_end', spc.clip_end)
    shader.assign('view_distance', r3d.view_distance)
    shader.assign('vert_scale', Vector((1, 1, 1)))
    shader.assign('screen_size', Vector((area.width, area.height)))

bmeshShader = Shader.load_from_file('bmeshShader', 'bmesh_render.glsl', funcStart=setupBMeshShader)



def glCheckError(title):
    if not glCheckError.CHECK_ERROR: return
    err = bgl.glGetError()
    if err == bgl.GL_NO_ERROR: return
    print('ERROR (%s): %s' % (title, glCheckError.ERROR_MAP.get(err, 'code %d' % err)))
    traceback.print_stack()
glCheckError.CHECK_ERROR = True
glCheckError.ERROR_MAP = {
    getattr(bgl, k): s
    for (k,s) in [
        # https://www.khronos.org/opengl/wiki/OpenGL_Error#Meaning_of_errors
        ('GL_INVALID_ENUM', 'invalid enum'),
        ('GL_INVALID_VALUE', 'invalid value'),
        ('GL_INVALID_OPERATION', 'invalid operation'),
        ('GL_STACK_OVERFLOW', 'stack overflow'),    # does not exist in b3d 2.8x for OSX??
        ('GL_STACK_UNDERFLOW', 'stack underflow'),  # does not exist in b3d 2.8x for OSX??
        ('GL_OUT_OF_MEMORY', 'out of memory'),
        ('GL_INVALID_FRAMEBUFFER_OPERATION', 'invalid framebuffer operation'),
        ('GL_CONTEXT_LOST', 'context lost'),
        ('GL_TABLE_TOO_LARGE', 'table too large'),  # deprecated in OpenGL 3.0, removed in 3.1 core and above
    ]
    if hasattr(bgl, k)
}


@blender_version_wrapper('<', '2.80')
def glSetDefaultOptions():
    bgl.glDisable(bgl.GL_LIGHTING)
    bgl.glEnable(bgl.GL_MULTISAMPLE)
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_DEPTH_TEST)
    bgl.glEnable(bgl.GL_POINT_SMOOTH)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)
@blender_version_wrapper('>=', '2.80')
def glSetDefaultOptions():
    bgl.glEnable(bgl.GL_MULTISAMPLE)
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_DEPTH_TEST)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)

@blender_version_wrapper('<', '2.80')
def glEnableStipple(enable=True):
    if enable:
        bgl.glLineStipple(4, 0x5555)
        bgl.glEnable(bgl.GL_LINE_STIPPLE)
    else:
        bgl.glDisable(bgl.GL_LINE_STIPPLE)
@blender_version_wrapper('>=', '2.80')
def glEnableStipple(enable=True):
    pass
    # if enable:
    #     bgl.glLineStipple(4, 0x5555)
    #     bgl.glEnable(bgl.GL_LINE_STIPPLE)
    # else:
    #     bgl.glDisable(bgl.GL_LINE_STIPPLE)


# def glEnableBackfaceCulling(enable=True):
#     if enable:
#         bgl.glDisable(bgl.GL_CULL_FACE)
#         bgl.glDepthFunc(bgl.GL_GEQUAL)
#     else:
#         bgl.glDepthFunc(bgl.GL_LEQUAL)
#         bgl.glEnable(bgl.GL_CULL_FACE)


def glSetOptions(prefix, opts):
    if not opts: return

    prefix = '%s ' % prefix if prefix else ''

    def set_if_set(opt, cb):
        opt = '%s%s' % (prefix, opt)
        if opt not in opts: return
        cb(opts[opt])
        glCheckError('setting %s to %s' % (str(opt), str(opts[opt])))
    def set_linewidth(v):
        dpi_mult = opts.get('dpi mult', 1.0)
        #bgl.glLineWidth(v*dpi_mult)
        glCheckError('setting line width to %s' % (str(v*dpi_mult)))
    def set_pointsize(v):
        dpi_mult = opts.get('dpi mult', 1.0)
        bgl.glPointSize(v*dpi_mult)
        glCheckError('setting point size to %s' % (str(v*dpi_mult)))
    def set_stipple(v):
        glEnableStipple(v)
        glCheckError('setting stipple to %s' % (str(v)))
    set_if_set('offset',         lambda v: bmeshShader.assign('offset', v))
    set_if_set('dotoffset',      lambda v: bmeshShader.assign('dotoffset', v))
    set_if_set('color',          lambda v: bmeshShader.assign('color', v))
    set_if_set('color selected', lambda v: bmeshShader.assign('color_selected', v))
    set_if_set('hidden',         lambda v: bmeshShader.assign('hidden', v))
    set_if_set('width',          set_linewidth)
    set_if_set('size',           set_pointsize)
    set_if_set('stipple',        set_stipple)


def glSetMirror(symmetry=None, view=None, effect=0.0, frame: Frame=None):
    mirroring = (0, 0, 0)
    if symmetry and frame:
        mx = 1.0 if 'x' in symmetry else 0.0
        my = 1.0 if 'y' in symmetry else 0.0
        mz = 1.0 if 'z' in symmetry else 0.0
        mirroring = (mx, my, mz)
        bmeshShader.assign('mirror_o', frame.o)
        bmeshShader.assign('mirror_x', frame.x)
        bmeshShader.assign('mirror_y', frame.y)
        bmeshShader.assign('mirror_z', frame.z)
    bmeshShader.assign('mirror_view', {'Edge': 1, 'Face': 2}.get(view, 0))
    bmeshShader.assign('mirror_effect', effect)
    bmeshShader.assign('mirroring', mirroring)

def triangulateFace(verts):
    l = len(verts)
    if l < 3: return
    if l == 3:
        yield verts
        return
    if l == 4:
        v0,v1,v2,v3 = verts
        yield (v0,v1,v2)
        yield (v0,v2,v3)
        return
    iv = iter(verts)
    v0, v2 = next(iv), next(iv)
    for v3 in iv:
        v1, v2 = v2, v3
        yield (v0, v1, v2)


#############################################################################################################
#############################################################################################################
#############################################################################################################

import gpu
from gpu_extras.batch import batch_for_shader
from .shaders import Shader

tri_vs, tri_fs = Shader.parse_file('bmesh_render_tris.glsl', includeVersion=True)
tri_shader = gpu.types.GPUShader(tri_vs, tri_fs)
edge_shader = None
point_shader = None


class BufferedRender_Batch:
    def __init__(self, gltype):
        global tri_shader, edge_shader, point_shader
        self.count = 0
        self.gltype = gltype
        self.shader, self.shader_type, self.gltype_name, self.gl_count, self.options_prefix = {
            bgl.GL_POINTS:    (point_shader, 'POINTS', 'points',    1, 'point'),
            bgl.GL_LINES:     (edge_shader,  'LINES',  'lines',     2, 'line'),
            bgl.GL_TRIANGLES: (tri_shader,   'TRIS',   'triangles', 3, 'poly'),
        }[self.gltype]
        self.batch = None

    def buffer(self, pos, norm, sel):
        if self.shader == None: return
        self.batch = batch_for_shader(self.shader, self.shader_type, {'vert_pos':pos, 'vert_norm':norm, 'selected':sel})
        self.count = len(pos)

    def set_options(self, prefix, opts):
        if not opts: return
        shader = self.shader

        prefix = '%s ' % prefix if prefix else ''

        def set_if_set(opt, cb):
            opt = '%s%s' % (prefix, opt)
            if opt not in opts: return
            cb(opts[opt])
            glCheckError('setting %s to %s' % (str(opt), str(opts[opt])))
        # def set_linewidth(v):
        #     dpi_mult = opts.get('dpi mult', 1.0)
        #     #bgl.glLineWidth(v*dpi_mult)
        #     glCheckError('setting line width to %s' % (str(v*dpi_mult)))
        # def set_pointsize(v):
        #     dpi_mult = opts.get('dpi mult', 1.0)
        #     bgl.glPointSize(v*dpi_mult)
        #     glCheckError('setting point size to %s' % (str(v*dpi_mult)))
        # def set_stipple(v):
        #     glEnableStipple(v)
        #     glCheckError('setting stipple to %s' % (str(v)))

        set_if_set('color',          lambda v: shader.uniform_float('color', v))
        set_if_set('color selected', lambda v: shader.uniform_float('color_selected', v))
        set_if_set('hidden',         lambda v: shader.uniform_float('hidden', v))
        set_if_set('offset',         lambda v: shader.uniform_float('offset', v))
        set_if_set('dotoffset',      lambda v: shader.uniform_float('dotoffset', v))
        # set_if_set('width',          set_linewidth)
        # set_if_set('size',           set_pointsize)
        # set_if_set('stipple',        set_stipple)

    def _draw(self, sx, sy, sz):
        self.shader.uniform_float('vert_scale', (sx, sy, sz))
        self.batch.draw(self.shader)
        #glCheckError('_draw: glDrawArrays (%d)' % self.count)

    def draw(self, opts):
        if self.shader == None or self.count == 0: return
        if self.gltype == bgl.GL_LINES and opts.get('line width', 1.0) <= 0: return
        if self.gltype == bgl.GL_POINTS and opts.get('point size', 1.0) <= 0: return

        shader = self.shader

        shader.bind()

        nosel = opts.get('no selection', False)
        shader.uniform_bool('use_selection', [not nosel]) # must be a sequence!?
        shader.uniform_bool('use_rounding',  [self.gltype == bgl.GL_POINTS]) # must be a sequence!?

        shader.uniform_float('matrix_m',    opts['matrix model'])
        shader.uniform_float('matrix_mn',   opts['matrix normal'])
        shader.uniform_float('matrix_t',    opts['matrix target'])
        shader.uniform_float('matrix_ti',   opts['matrix target inverse'])
        shader.uniform_float('matrix_v',    opts['matrix view'])
        shader.uniform_float('matrix_vn',   opts['matrix view normal'])
        shader.uniform_float('matrix_p',    opts['matrix projection'])
        #shader.uniform_float('dir_forward', opts['forward direction'])

        mx, my, mz = opts.get('mirror x', False), opts.get('mirror y', False), opts.get('mirror z', False)
        symmetry = opts.get('symmetry', None)
        symmetry_frame = opts.get('symmetry frame', None)
        symmetry_view = opts.get('symmetry view', None)
        symmetry_effect = opts.get('symmetry effect', 0.0)
        mirroring = (False, False, False)
        if symmetry and symmetry_frame:
            mx = 'x' in symmetry
            my = 'y' in symmetry
            mz = 'z' in symmetry
            mirroring = (mx, my, mz)
            # shader.uniform_float('mirror_o', symmetry_frame.o)
            #shader.uniform_float('mirror_x', symmetry_frame.x)
            #shader.uniform_float('mirror_y', symmetry_frame.y)
            #shader.uniform_float('mirror_z', symmetry_frame.z)
        shader.uniform_int('mirror_view', [{'Edge': 1, 'Face': 2}.get(symmetry_view, 0)])
        shader.uniform_float('mirror_effect', symmetry_effect)
        shader.uniform_bool('mirroring', mirroring)

        shader.uniform_float('normal_offset',    opts.get('normal offset', 0.0))
        shader.uniform_bool('constrain_offset', [opts.get('constrain offset', True)]) # must be a sequence!?

        ctx = bpy.context
        area, spc, r3d = ctx.area, ctx.space_data, ctx.space_data.region_3d
        shader.uniform_bool('perspective', [r3d.view_perspective != 'ORTHO']) # must be a sequence!?
        shader.uniform_float('clip_start', spc.clip_start)
        shader.uniform_float('clip_end', spc.clip_end)
        shader.uniform_float('view_distance', r3d.view_distance)
        shader.uniform_float('vert_scale', Vector((1, 1, 1)))
        shader.uniform_float('screen_size', Vector((area.width, area.height)))

        focus = opts.get('focus mult', 1.0)
        shader.uniform_float('focus_mult',       focus)
        shader.uniform_bool('cull_backfaces',   [opts.get('cull backfaces', False)])
        shader.uniform_float('alpha_backface',   opts.get('alpha backface', 0.5))

        self.set_options(self.options_prefix, opts)
        self._draw(1, 1, 1)

        if mx or my or mz:
            self.set_options('%s mirror' % self.options_prefix, opts)
            if mx:               self._draw(-1,  1,  1)
            if        my:        self._draw( 1, -1,  1)
            if               mz: self._draw( 1,  1, -1)
            if mx and my:        self._draw(-1, -1,  1)
            if mx        and mz: self._draw(-1,  1, -1)
            if        my and mz: self._draw( 1, -1, -1)
            if mx and my and mz: self._draw(-1, -1, -1)

        gpu.shader.unbind()



#############################################################################################################
#############################################################################################################
#############################################################################################################


class BGLBufferedRender:
    DEBUG_PRINT = False

    def __init__(self, gltype):
        self.count = 0
        self.gltype = gltype
        self.gltype_name, self.gl_count, self.options_prefix = {
            bgl.GL_POINTS:    ('points',    1, 'point'),
            bgl.GL_LINES:     ('lines',     2, 'line'),
            bgl.GL_TRIANGLES: ('triangles', 3, 'poly'),
        }[self.gltype]

        # self.vao = bgl.Buffer(bgl.GL_INT, 1)
        # bgl.glGenVertexArrays(1, self.vao)
        # bgl.glBindVertexArray(self.vao[0])

        self.vbos = bgl.Buffer(bgl.GL_INT, 4)
        bgl.glGenBuffers(4, self.vbos)
        self.vbo_pos = self.vbos[0]
        self.vbo_norm = self.vbos[1]
        self.vbo_sel = self.vbos[2]
        self.vbo_idx = self.vbos[3]

        self.render_indices = False

    def __del__(self):
        bgl.glDeleteBuffers(4, self.vbos)
        del self.vbos

    @profiler.function
    def buffer(self, pos, norm, sel, idx):
        sizeOfFloat, sizeOfInt = 4, 4
        self.count = 0
        count = len(pos)
        counts = list(map(len, [pos, norm, sel]))

        goodcounts = all(c == count for c in counts)
        assert goodcounts, ('All arrays must contain '
                            'the same number of elements %s' % str(counts))

        if count == 0:
            return

        try:
            buf_pos = bgl.Buffer(bgl.GL_FLOAT, [count, 3], pos)
            buf_norm = bgl.Buffer(bgl.GL_FLOAT, [count, 3], norm)
            buf_sel = bgl.Buffer(bgl.GL_FLOAT, count, sel)
            if idx:
                # WHY NO GL_UNSIGNED_INT?????
                buf_idx = bgl.Buffer(bgl.GL_INT, count, idx)
            if self.DEBUG_PRINT:
                print('buf_pos  = ' + shorten_floats(str(buf_pos)))
                print('buf_norm = ' + shorten_floats(str(buf_norm)))
        except Exception as e:
            print(
                'ERROR (buffer): caught exception while '
                'buffering to Buffer ' + str(e))
            raise e
        try:
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, self.vbo_pos)
            bgl.glBufferData(bgl.GL_ARRAY_BUFFER, count * 3 *
                             sizeOfFloat, buf_pos,
                             bgl.GL_STATIC_DRAW)
            glCheckError('buffer: vbo_pos')
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, self.vbo_norm)
            bgl.glBufferData(bgl.GL_ARRAY_BUFFER, count * 3 *
                             sizeOfFloat, buf_norm,
                             bgl.GL_STATIC_DRAW)
            glCheckError('buffer: vbo_norm')
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, self.vbo_sel)
            bgl.glBufferData(bgl.GL_ARRAY_BUFFER, count * 1 *
                             sizeOfFloat, buf_sel,
                             bgl.GL_STATIC_DRAW)
            glCheckError('buffer: vbo_sel')
            if idx:
                bgl.glBindBuffer(bgl.GL_ELEMENT_ARRAY_BUFFER, self.vbo_idx)
                bgl.glBufferData(bgl.GL_ELEMENT_ARRAY_BUFFER,
                                 count * sizeOfInt, buf_idx,
                                 bgl.GL_STATIC_DRAW)
                glCheckError('buffer: vbo_idx')
        except Exception as e:
            print(
                'ERROR (buffer): caught exception while '
                'buffering from Buffer ' + str(e))
            raise e
        finally:
            bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)
            bgl.glBindBuffer(bgl.GL_ELEMENT_ARRAY_BUFFER, 0)
        del buf_pos, buf_norm, buf_sel
        if idx:
            del buf_idx

        if idx:
            self.count = len(idx)
            self.render_indices = True
        else:
            self.count = len(pos)
            self.render_indices = False

    @profiler.function
    def _draw(self, sx, sy, sz):
        bmeshShader.assign('vert_scale', (sx, sy, sz))
        if self.DEBUG_PRINT:
            print('==> drawing %d %s (%d)  (%d verts)' % (
                self.count / self.gl_count,
                self.gltype_name, self.gltype, self.count))
        if self.render_indices:
            bgl.glDrawElements(self.gltype, self.count,
                               bgl.GL_UNSIGNED_INT, buf_zero)
            glCheckError('_draw: glDrawElements (%d, %d, %d)' % (
                self.gltype, self.count, bgl.GL_UNSIGNED_INT))
        else:
            bgl.glDrawArrays(self.gltype, 0, self.count)
            glCheckError('_draw: glDrawArrays (%d)' % self.count)

    @profiler.function
    def draw(self, opts):
        if self.count == 0:
            return

        if self.gltype == bgl.GL_LINES:
            if opts.get('line width', 1.0) <= 0:
                return
        elif self.gltype == bgl.GL_POINTS:
            if opts.get('point size', 1.0) <= 0:
                return
        nosel = opts.get('no selection', False)
        mx, my, mz = opts.get('mirror x', False), opts.get(
            'mirror y', False), opts.get('mirror z', False)
        focus = opts.get('focus mult', 1.0)

        bmeshShader.assign('focus_mult', focus)
        bmeshShader.assign('use_selection', 0.0 if nosel else 1.0)
        bmeshShader.assign('cull_backfaces', 1.0 if opts.get('cull backfaces', False) else 0.0)
        bmeshShader.assign('alpha_backface', opts.get('alpha backface', 0.5))
        bmeshShader.assign('normal_offset', opts.get('normal offset', 0.0))
        bmeshShader.assign('constrain_offset', 1.0 if opts.get('constrain offset', True) else 0.0)
        bmeshShader.assign('use_rounding', 1.0 if self.gltype == bgl.GL_POINTS else 0.0)

        bmeshShader.vertexAttribPointer(self.vbo_pos,  'vert_pos',  3, bgl.GL_FLOAT)
        glCheckError('draw: vertex attrib array pos')
        bmeshShader.vertexAttribPointer(self.vbo_norm, 'vert_norm', 3, bgl.GL_FLOAT)
        glCheckError('draw: vertex attrib array norm')
        bmeshShader.vertexAttribPointer(self.vbo_sel,  'selected',  1, bgl.GL_FLOAT)
        glCheckError('draw: vertex attrib array sel')
        bgl.glBindBuffer(bgl.GL_ELEMENT_ARRAY_BUFFER, self.vbo_idx)
        glCheckError('draw: element array buffer idx')

        glSetOptions(self.options_prefix, opts)
        self._draw(1, 1, 1)

        if mx or my or mz:
            glSetOptions('%s mirror' % self.options_prefix, opts)
            if mx:
                self._draw(-1,  1,  1)
            if my:
                self._draw(1, -1,  1)
            if mz:
                self._draw(1,  1, -1)
            if mx and my:
                self._draw(-1, -1,  1)
            if mx and mz:
                self._draw(-1,  1, -1)
            if my and mz:
                self._draw(1, -1, -1)
            if mx and my and mz:
                self._draw(-1, -1, -1)

        bmeshShader.disableVertexAttribArray('vert_pos')
        bmeshShader.disableVertexAttribArray('vert_norm')
        bmeshShader.disableVertexAttribArray('selected')
        bgl.glBindBuffer(bgl.GL_ELEMENT_ARRAY_BUFFER, 0)
        bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, 0)

