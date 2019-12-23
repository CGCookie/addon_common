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



def glColor(color):
    if len(color) == 3:
        bgl.glColor3f(*color)
    else:
        bgl.glColor4f(*color)




def glDrawBMFace(bmf, opts=None, enableShader=True):
    glDrawBMFaces([bmf], opts=opts, enableShader=enableShader)

@profiler.function
def glDrawBMFaces(lbmf, opts=None, enableShader=True):
    opts_ = opts or {}
    nosel = opts_.get('no selection', False)
    mx = opts_.get('mirror x', False)
    my = opts_.get('mirror y', False)
    mz = opts_.get('mirror z', False)
    dn = opts_.get('normal', 0.0)
    vdict = opts_.get('vertex dict', {})

    bmeshShader.assign('focus_mult', opts_.get('focus mult', 1.0))
    bmeshShader.assign('use_selection', 0.0 if nosel else 1.0)

    @profiler.function
    def render_general(sx, sy, sz):
        bmeshShader.assign('vert_scale', (sx, sy, sz))
        bmeshShader.assign('selected', 0.0)
        for bmf in lbmf:
            bmeshShader.assign('selected', 1.0 if bmf.select else 0.0)
            if bmf.smooth:
                for v0, v1, v2 in triangulateFace(bmf.verts):
                    if v0 not in vdict:
                        vdict[v0] = (v0.co, v0.normal)
                    if v1 not in vdict:
                        vdict[v1] = (v1.co, v1.normal)
                    if v2 not in vdict:
                        vdict[v2] = (v2.co, v2.normal)
                    (c0, n0), (c1, n1), (c2,
                                         n2) = vdict[v0], vdict[v1], vdict[v2]
                    bmeshShader.assign('vert_norm', n0)
                    bmeshShader.assign('vert_pos',  c0)
                    bmeshShader.assign('vert_norm', n1)
                    bmeshShader.assign('vert_pos',  c1)
                    bmeshShader.assign('vert_norm', n2)
                    bmeshShader.assign('vert_pos',  c2)
            else:
                bgl.glNormal3f(*bmf.normal)
                bmeshShader.assign('vert_norm', bmf.normal)
                for v0, v1, v2 in triangulateFace(bmf.verts):
                    if v0 not in vdict:
                        vdict[v0] = (v0.co, v0.normal)
                    if v1 not in vdict:
                        vdict[v1] = (v1.co, v1.normal)
                    if v2 not in vdict:
                        vdict[v2] = (v2.co, v2.normal)
                    (c0, n0), (c1, n1), (c2,
                                         n2) = vdict[v0], vdict[v1], vdict[v2]
                    bmeshShader.assign('vert_pos', c0)
                    bmeshShader.assign('vert_pos', c1)
                    bmeshShader.assign('vert_pos', c2)

    @profiler.function
    def render_triangles(sx, sy, sz):
        # optimized for triangle-only meshes
        # (source meshes that have been triangulated)
        bmeshShader.assign('vert_scale', (sx, sy, sz))
        bmeshShader.assign('selected', 0.0)
        for bmf in lbmf:
            bmeshShader.assign('selected', 1.0 if bmf.select else 0.0)
            if bmf.smooth:
                v0, v1, v2 = bmf.verts
                if v0 not in vdict:
                    vdict[v0] = (v0.co, v0.normal)
                if v1 not in vdict:
                    vdict[v1] = (v1.co, v1.normal)
                if v2 not in vdict:
                    vdict[v2] = (v2.co, v2.normal)
                (c0, n0), (c1, n1), (c2, n2) = vdict[v0], vdict[v1], vdict[v2]
                bmeshShader.assign('vert_norm', n0)
                bmeshShader.assign('vert_pos',  c0)
                # bgl.glNormal3f(*n0)
                # bgl.glVertex3f(*c0)
                bmeshShader.assign('vert_norm', n1)
                bmeshShader.assign('vert_pos',  c1)
                # bgl.glNormal3f(*n1)
                # bgl.glVertex3f(*c1)
                bmeshShader.assign('vert_norm', n2)
                bmeshShader.assign('vert_pos',  c2)
                # bgl.glNormal3f(*n2)
                # bgl.glVertex3f(*c2)
            else:
                bgl.glNormal3f(*bmf.normal)
                v0, v1, v2 = bmf.verts
                if v0 not in vdict:
                    vdict[v0] = (v0.co, v0.normal)
                if v1 not in vdict:
                    vdict[v1] = (v1.co, v1.normal)
                if v2 not in vdict:
                    vdict[v2] = (v2.co, v2.normal)
                (c0, n0), (c1, n1), (c2, n2) = vdict[v0], vdict[v1], vdict[v2]
                bmeshShader.assign('vert_pos',  c0)
                # bgl.glVertex3f(*c0)
                bmeshShader.assign('vert_pos',  c1)
                # bgl.glVertex3f(*c1)
                bmeshShader.assign('vert_pos',  c2)
                # bgl.glVertex3f(*c2)

    render = render_triangles if opts_.get(
        'triangles only', False) else render_general

    if enableShader:
        bmeshShader.enable()

    glSetOptions('poly', opts)
    bgl.glBegin(bgl.GL_TRIANGLES)
    render(1, 1, 1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if mx or my or mz:
        glSetOptions('poly mirror', opts)
        bgl.glBegin(bgl.GL_TRIANGLES)
        if mx:
            render(-1,  1,  1)
        if my:
            render(1, -1,  1)
        if mz:
            render(1,  1, -1)
        if mx and my:
            render(-1, -1,  1)
        if mx and mz:
            render(-1,  1, -1)
        if my and mz:
            render(1, -1, -1)
        if mx and my and mz:
            render(-1, -1, -1)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if enableShader:
        bmeshShader.disable()




@profiler.function
def glDrawSimpleFaces(lsf, opts=None, enableShader=True):
    opts_ = opts or {}
    nosel = opts_.get('no selection', False)
    mx = opts_.get('mirror x', False)
    my = opts_.get('mirror y', False)
    mz = opts_.get('mirror z', False)
    dn = opts_.get('normal', 0.0)

    bmeshShader.assign('focus_mult', opts_.get('focus mult', 1.0))
    bmeshShader.assign('use_selection', 0.0 if nosel else 1.0)
    bmeshShader.assign('selected', 0.0)

    @profiler.function
    def render(sx, sy, sz):
        bmeshShader.assign('vert_scale', (sx, sy, sz))
        for sf in lsf:
            for v0, v1, v2 in triangulateFace(sf):
                (c0, n0), (c1, n1), (c2, n2) = v0, v1, v2
                bgl.glNormal3f(*n0)
                bgl.glVertex3f(*c0)
                bgl.glNormal3f(*n1)
                bgl.glVertex3f(*c1)
                bgl.glNormal3f(*n2)
                bgl.glVertex3f(*c2)

    if enableShader:
        bmeshShader.enable()

    glSetOptions('poly', opts)
    bgl.glBegin(bgl.GL_TRIANGLES)
    render(1, 1, 1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if mx or my or mz:
        glSetOptions('poly mirror', opts)
        bgl.glBegin(bgl.GL_TRIANGLES)
        if mx:
            render(-1,  1,  1)
        if my:
            render(1, -1,  1)
        if mz:
            render(1,  1, -1)
        if mx and my:
            render(-1, -1,  1)
        if mx and mz:
            render(-1,  1, -1)
        if my and mz:
            render(1, -1, -1)
        if mx and my and mz:
            render(-1, -1, -1)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if enableShader:
        bmeshShader.disable()


def glDrawBMFaceEdges(bmf, opts=None, enableShader=True):
    glDrawBMEdges(bmf.edges, opts=opts, enableShader=enableShader)


def glDrawBMFaceVerts(bmf, opts=None, enableShader=True):
    glDrawBMVerts(bmf.verts, opts=opts, enableShader=enableShader)


def glDrawBMEdge(bme, opts=None, enableShader=True):
    glDrawBMEdges([bme], opts=opts, enableShader=enableShader)


@profiler.function
def glDrawBMEdges(lbme, opts=None, enableShader=True):
    opts_ = opts or {}
    if opts_.get('line width', 1.0) <= 0.0:
        return
    nosel = opts_.get('no selection', False)
    mx = opts_.get('mirror x', False)
    my = opts_.get('mirror y', False)
    mz = opts_.get('mirror z', False)
    dn = opts_.get('normal', 0.0)
    vdict = opts_.get('vertex dict', {})

    bmeshShader.assign('use_selection', 0.0 if nosel else 1.0)

    @profiler.function
    def render(sx, sy, sz):
        bmeshShader.assign('vert_scale', (sx, sy, sz))
        for bme in lbme:
            bmeshShader.assign('selected', 1.0 if bme.select else 0.0)
            v0, v1 = bme.verts
            if v0 not in vdict:
                vdict[v0] = (v0.co, v0.normal)
            if v1 not in vdict:
                vdict[v1] = (v1.co, v1.normal)
            (c0, n0), (c1, n1) = vdict[v0], vdict[v1]
            c0, c1 = c0+n0*dn, c1+n1*dn
            bmeshShader.assign('vert_norm', n0)
            bmeshShader.assign('vert_pos',  c0)
            # bgl.glVertex3f(0,0,0)
            bmeshShader.assign('vert_norm', n1)
            bmeshShader.assign('vert_pos',  c1)
            # bgl.glVertex3f(0,0,0)

    if enableShader:
        bmeshShader.enable()

    glSetOptions('line', opts)
    bgl.glBegin(bgl.GL_LINES)
    render(1, 1, 1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if mx or my or mz:
        glSetOptions('line mirror', opts)
        bgl.glBegin(bgl.GL_LINES)
        if mx:
            render(-1,  1,  1)
        if my:
            render(1, -1,  1)
        if mz:
            render(1,  1, -1)
        if mx and my:
            render(-1, -1,  1)
        if mx and mz:
            render(-1,  1, -1)
        if my and mz:
            render(1, -1, -1)
        if mx and my and mz:
            render(-1, -1, -1)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if enableShader:
        bmeshShader.disable()


def glDrawBMEdgeVerts(bme, opts=None, enableShader=True):
    glDrawBMVerts(bme.verts, opts=opts, enableShader=enableShader)


def glDrawBMVert(bmv, opts=None, enableShader=True):
    glDrawBMVerts([bmv], opts=opts, enableShader=enableShader)


@profiler.function
def glDrawBMVerts(lbmv, opts=None, enableShader=True):
    opts_ = opts or {}
    if opts_.get('point size', 1.0) <= 0.0:
        return
    nosel = opts_.get('no selection', False)
    mx = opts_.get('mirror x', False)
    my = opts_.get('mirror y', False)
    mz = opts_.get('mirror z', False)
    dn = opts_.get('normal', 0.0)
    vdict = opts_.get('vertex dict', {})

    if enableShader:
        bmeshShader.enable()
    bmeshShader.assign('use_selection', 0.0 if nosel else 1.0)

    @profiler.function
    def render(sx, sy, sz):
        bmeshShader.assign('vert_scale', Vector((sx, sy, sz)))
        for bmv in lbmv:
            bmeshShader.assign('selected', 1.0 if bmv.select else 0.0)
            if bmv not in vdict:
                vdict[bmv] = (bmv.co, bmv.normal)
            c, n = vdict[bmv]
            c = c + dn * n
            bmeshShader.assign('vert_norm', n)
            bmeshShader.assign('vert_pos',  c)
            # bgl.glNormal3f(*n)
            # bgl.glVertex3f(*c)

    glSetOptions('point', opts)
    bgl.glBegin(bgl.GL_POINTS)
    glCheckError('something broke before rendering bmverts')
    render(1, 1, 1)
    glCheckError('something broke after rendering bmverts')
    bgl.glEnd()
    glCheckError('something broke after glEnd')
    bgl.glDisable(bgl.GL_LINE_STIPPLE)
    glCheckError('something broke after glDisable(bgl.GL_LINE_STIPPLE')

    if mx or my or mz:
        glSetOptions('point mirror', opts)
        bgl.glBegin(bgl.GL_POINTS)
        if mx:
            render(-1,  1,  1)
        if my:
            render(1, -1,  1)
        if mz:
            render(1,  1, -1)
        if mx and my:
            render(-1, -1,  1)
        if mx and mz:
            render(-1,  1, -1)
        if my and mz:
            render(1, -1, -1)
        if mx and my and mz:
            render(-1, -1, -1)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_LINE_STIPPLE)

    if enableShader:
        glCheckError('before disabling shader')
        bmeshShader.disable()


class BMeshRender():
    @profiler.function
    def __init__(self, obj, xform=None):
        self.calllist = None
        if type(obj) is bpy.types.Object:
            print('Creating BMeshRender for ' + obj.name)
            self.bme = bmesh.new()
            self.bme.from_object(obj, bpy.context.scene, deform=True)
            self.xform = xform or XForm(obj.matrix_world)
        elif type(obj) is bmesh.types.BMesh:
            self.bme = obj
            self.xform = xform or XForm()
        else:
            assert False, 'Unhandled type: ' + str(type(obj))

        self.buf_matrix_model = self.xform.to_bglMatrix_Model()
        self.buf_matrix_normal = self.xform.to_bglMatrix_Normal()

        self.is_dirty = True
        self.calllist = bgl.glGenLists(1)

    def replace_bmesh(self, bme):
        self.bme = bme
        self.is_dirty = True

    def __del__(self):
        if not self.calllist: return
        bgl.glDeleteLists(self.calllist, 1)
        self.calllist = None

    def dirty(self):
        self.is_dirty = True

    @profiler.function
    def clean(self, opts=None):
        if not self.is_dirty: return

        # make not dirty first in case bad things happen while drawing
        self.is_dirty = False

        bgl.glNewList(self.calllist, bgl.GL_COMPILE)
        # do not change attribs if they're not set
        glSetDefaultOptions(opts=opts)
        glDrawBMFaces(self.bme.faces, opts=opts, enableShader=False)
        glDrawBMEdges(self.bme.edges, opts=opts, enableShader=False)
        glDrawBMVerts(self.bme.verts, opts=opts, enableShader=False)
        bgl.glDepthRange(0, 1)
        bgl.glEndList()

    @profiler.function
    def draw(self, opts=None):
        try:
            self.clean(opts=opts)
            bmeshShader.enable()
            #bmeshShader.assign('matrix_m',  self.buf_matrix_model)
            #bmeshShader.assign('matrix_mn', self.buf_matrix_normal)
            #bmeshShader.assign('matrix_t', buf_matrix_target)
            #bmeshShader.assign('matrix_ti', buf_matrix_target_inv)
            #bmeshShader.assign('matrix_v', buf_matrix_view)
            #bmeshShader.assign('matrix_vn', buf_matrix_view_invtrans)
            #bmeshShader.assign('matrix_p', buf_matrix_proj)
            #bmeshShader.assign('dir_forward', view_forward)
            bgl.glCallList(self.calllist)
        except:
            pass
        finally:
            bmeshShader.disable()
