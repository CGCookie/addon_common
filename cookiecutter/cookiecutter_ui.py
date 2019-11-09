'''
Copyright (C) 2018 CG Cookie

https://github.com/CGCookie/retopoflow

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

import math
import random

import bpy
import bgl
from bpy.types import SpaceView3D

from ..common.globals import Globals
from ..common.blender import bversion, tag_redraw_all
from ..common.decorators import blender_version_wrapper
from ..common.debug import debugger
from ..common.drawing import Drawing, DrawCallbacks
from ..common.ui_core import UI_Document


if bversion() >= "2.80":
    import gpu
    from gpu_extras.batch import batch_for_shader

    # https://docs.blender.org/api/blender2.8/gpu.html#triangle-with-custom-shader
    cover_vshader = '''
        in vec2 position;
        void main() {
            gl_Position = vec4(position, 0.0f, 1.0f);
        }
    '''
    cover_fshader = '''
        uniform float darken;
        out vec4 outColor;
        void main() {
            outColor = vec4(0.0f, 0.0f, 0.0f, darken);
        }
    '''
    shader = gpu.types.GPUShader(cover_vshader, cover_fshader)

    # create batch to draw large triangle that covers entire clip space (-1,-1)--(+1,+1)
    batch_full = batch_for_shader(shader, 'TRIS', {"position": [(-1, -1), (3, -1), (-1, 3)]})



class CookieCutter_UI:
    '''
    Assumes that direct subclass will have singleton instance (shared CookieCutter among all instances of that subclass and any subclasses)
    '''

    drawcallbacks = DrawCallbacks()
    Draw = drawcallbacks.wrapper

    def _cc_ui_init(self):
        self.document = Globals.ui_document # UI_Document(self.context)
        self.document.init(self.context)
        self.drawing = Globals.drawing
        self.drawing.set_region(bpy.context.area, bpy.context.space_data, bpy.context.region, bpy.context.space_data.region_3d, bpy.context.window)
        self._cc_blenderui_init()
        self.drawcallbacks.init(self)
        self._ignore_ui_events = False
        self._area.tag_redraw()

    @property
    def ignore_ui_events(self):
        return self._ignore_ui_events
    @ignore_ui_events.setter
    def ignore_ui_events(self, v):
        self._ignore_ui_events = bool(v)

    def _cc_ui_start(self):
        def preview():
            with self.catch_exception('draw pre3d'):
                self.drawcallbacks.pre3d()
        def postview():
            with self.catch_exception('draw post3d'):
                self.drawcallbacks.post3d()
        def postpixel():
            bgl.glEnable(bgl.GL_MULTISAMPLE)
            bgl.glEnable(bgl.GL_BLEND)
            with self.catch_exception('draw post2d()'):
                self.drawcallbacks.post2d()
            with self.catch_exception('draw window UI'):
                self.document.draw(self.context)

        self._handle_preview   = self._space.draw_handler_add(preview,   tuple(), 'WINDOW', 'PRE_VIEW')
        self._handle_postview  = self._space.draw_handler_add(postview,  tuple(), 'WINDOW', 'POST_VIEW')
        self._handle_postpixel = self._space.draw_handler_add(postpixel, tuple(), 'WINDOW', 'POST_PIXEL')
        self._area.tag_redraw()

    def _cc_ui_update(self):
        # print('\x1b[2J', end='')
        # print('\033c', end='')
        # print('\n' * 2, end='')
        # print('--------- ' + str(random.random()))
        self.drawing.update_dpi()
        if self._ignore_ui_events:
            return False
        ret = self.document.update(self.context, self.event)
        # ret = self.wm.modal(self.context, self.event)
        #if self.wm.has_focus(): return True
        if ret and 'hover' in ret: return True
        return False

    def _cc_ui_end(self):
        self._cc_blenderui_end()
        self._space.draw_handler_remove(self._handle_preview,   'WINDOW')
        self._space.draw_handler_remove(self._handle_postview,  'WINDOW')
        self._space.draw_handler_remove(self._handle_postpixel, 'WINDOW')
        self.region_restore()
        #self._area.tag_redraw()
        tag_redraw_all()


    #########################################
    # Region Darkening

    @blender_version_wrapper("<=", "2.79")
    def _cc_region_draw_cover(self):
        bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glColor4f(0,0,0,0.5)    # TODO: use window background color??
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
    @blender_version_wrapper(">=", "2.80")
    def _cc_region_draw_cover(self):
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        shader.bind()
        shader.uniform_float("darken", 0.50)
        batch_full.draw(shader)
        gpu.shader.unbind()

    def region_darken(self):
        if hasattr(self, '_region_darkened'): return    # already darkened!
        self._region_darkened = True

        # darken all spaces except SpaceView3D (handled separately)
        spaces = [getattr(bpy.types, s) for s in dir(bpy.types) if s.startswith('Space') and s != 'SpaceView3D']
        spaces = [s for s in spaces if hasattr(s, 'draw_handler_add')]

        # https://docs.blender.org/api/blender2.8/bpy.types.Region.html#bpy.types.Region.type
        #     ['WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW', 'NAVIGATION_BAR', 'EXECUTE']
        # NOTE: b280 has no TOOL_PROPS region for SpaceView3D!
        areas  = ['WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW', 'HUD', 'NAVIGATION_BAR', 'EXECUTE', 'FOOTER', 'TOOL_HEADER'] #['WINDOW', 'HEADER', 'UI', 'TOOLS', 'NAVIGATION_BAR']

        self._postpixel_callbacks = []
        s = SpaceView3D
        for a in ['TOOLS', 'UI', 'HEADER', 'TOOL_PROPS']:
            try:
                cb = s.draw_handler_add(self._cc_region_draw_cover, tuple(), a, 'POST_PIXEL')
                self._postpixel_callbacks += [(s, a, cb)]
            except:
                pass
        for s in spaces:
            for a in areas:
                try:
                    cb = s.draw_handler_add(self._cc_region_draw_cover, tuple(), a, 'POST_PIXEL')
                    self._postpixel_callbacks += [(s, a, cb)]
                except:
                    pass

        tag_redraw_all()

    def region_restore(self):
        # remove callback handlers
        if hasattr(self, '_postpixel_callbacks'):
            for (s,a,cb) in self._postpixel_callbacks: s.draw_handler_remove(cb, a)
            del self._postpixel_callbacks
        if hasattr(self, '_region_darkened'):
            del self._region_darkened
        tag_redraw_all()


