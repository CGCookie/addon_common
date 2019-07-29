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
from ..common.blender import bversion
from ..common.decorators import blender_version_wrapper
from ..common.debug import debugger
from ..common.drawing import Drawing
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
        void main() {
            gl_FragColor = vec4(0.0f, 0.0f, 0.0f, darken);
        }
    '''
    shader = gpu.types.GPUShader(cover_vshader, cover_fshader)

    # create batch to draw large triangle that covers entire clip space (-1,-1)--(+1,+1)
    batch_full = batch_for_shader(shader, 'TRIS', {"position": [(-1, -1), (3, -1), (-1, 3)]})



class CookieCutter_UI:
    class Draw:
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

    def ui_init(self):
        self.document = UI_Document(self.context)
        self.drawing = Globals.drawing
        self.drawing.set_region(bpy.context.space_data, bpy.context.region, bpy.context.space_data.region_3d, bpy.context.window)
        self.blenderui_init()
        fns = {'pre3d':[], 'post3d':[], 'post2d':[]}
        for m,fn in self.find_fns('drawmode'): fns[m].append(fn)
        def draw(fns):
            for fn in fns: fn(self)
        self._draw_pre3d  = lambda:draw(fns['pre3d'])
        self._draw_post3d = lambda:draw(fns['post3d'])
        self._draw_post2d = lambda:draw(fns['post2d'])
        self._area.tag_redraw()

    def ui_start(self):
        def preview():
            self._draw_pre3d()
        def postview():
            self._draw_post3d()
        def postpixel():
            bgl.glEnable(bgl.GL_MULTISAMPLE)
            bgl.glEnable(bgl.GL_BLEND)
            #bgl.glEnable(bgl.GL_POINT_SMOOTH)

            self._draw_post2d()

            try:
                self.document.draw(self.context)
                #self.wm.draw_postpixel(self.context)
                pass
            except Exception as e:
                print('Caught exception while trying to draw window UI')
                debugger.print_exception()
                print(e)

        self._handle_preview   = self._space.draw_handler_add(preview,   tuple(), 'WINDOW', 'PRE_VIEW')
        self._handle_postview  = self._space.draw_handler_add(postview,  tuple(), 'WINDOW', 'POST_VIEW')
        self._handle_postpixel = self._space.draw_handler_add(postpixel, tuple(), 'WINDOW', 'POST_PIXEL')
        self._area.tag_redraw()

    def ui_update(self):
        # print('\x1b[2J', end='')
        # print('\033c', end='')
        # print('\n' * 2, end='')
        # print('--------- ' + str(random.random()))
        self.drawing.update_dpi()
        self._area.tag_redraw()
        self.document.update(self.context, self.event)
        ret = None #self.wm.modal(self.context, self.event)
        #if self.wm.has_focus(): return True
        if ret and 'hover' in ret: return True
        return False

    def ui_end(self):
        self.blenderui_end()
        self._space.draw_handler_remove(self._handle_preview,   'WINDOW')
        self._space.draw_handler_remove(self._handle_postview,  'WINDOW')
        self._space.draw_handler_remove(self._handle_postpixel, 'WINDOW')
        self.region_restore()
        #self._area.tag_redraw()
        self.tag_redraw_all()


    #########################################
    # Region Darkening

    def tag_redraw_all(self):
        for wm in bpy.data.window_managers:
            for win in wm.windows:
                for ar in win.screen.areas:
                    ar.tag_redraw()

    @blender_version_wrapper("<=", "2.79")
    def region_draw_cover(self):
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
    def region_draw_cover(self):
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

        # ('WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW')
        # https://docs.blender.org/api/blender2.8/bpy.types.Region.html#bpy.types.Region.type
        #     ['WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW', 'NAVIGATION_BAR', 'EXECUTE']
        # NOTE: b280 has no TOOL_PROPS region for SpaceView3D!
        areas  = ['WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW', 'NAVIGATION_BAR', 'EXECUTE'] #['WINDOW', 'HEADER', 'UI', 'TOOLS', 'NAVIGATION_BAR']

        self._handle_pp_tools  = SpaceView3D.draw_handler_add(self.region_draw_cover, tuple(), 'TOOLS',      'POST_PIXEL')
        self._handle_pp_props  = SpaceView3D.draw_handler_add(self.region_draw_cover, tuple(), 'TOOL_PROPS', 'POST_PIXEL') if bversion() <= '2.79' else None
        self._handle_pp_ui     = SpaceView3D.draw_handler_add(self.region_draw_cover, tuple(), 'UI',         'POST_PIXEL')
        self._handle_pp_header = SpaceView3D.draw_handler_add(self.region_draw_cover, tuple(), 'HEADER',     'POST_PIXEL')
        self._handle_pp_other  = []

        for s in spaces:
            for a in areas:
                try:
                    cb = s.draw_handler_add(self.region_draw_cover, tuple(), a, 'POST_PIXEL')
                    self._handle_pp_other += [(s, a, cb)]
                except:
                    pass

        self.tag_redraw_all()

    def region_restore(self):
        # remove callback handlers
        if hasattr(self, '_handle_pp_tools'):
            SpaceView3D.draw_handler_remove(self._handle_pp_tools, "TOOLS")
            del self._handle_pp_tools
        if hasattr(self, '_handle_pp_props'):
            if self._handle_pp_props:
                SpaceView3D.draw_handler_remove(self._handle_pp_props, "TOOL_PROPS")
            del self._handle_pp_props
        if hasattr(self, '_handle_pp_ui'):
            SpaceView3D.draw_handler_remove(self._handle_pp_ui, "UI")
            del self._handle_pp_ui
        if hasattr(self, '_handle_pp_header'):
            SpaceView3D.draw_handler_remove(self._handle_pp_header, "HEADER")
            del self._handle_pp_header
        if hasattr(self, '_handle_pp_other'):
            for s,a,cb in self._handle_pp_other: s.draw_handler_remove(cb, a)
            del self._handle_pp_other
        if hasattr(self, '_darkened'):
            del self._region_darkened


