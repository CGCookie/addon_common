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

import time

import bpy
from bpy.types import Operator

from ..common.debug import debugger
from ..common.profiler import profiler
from ..common.useractions import Actions

from .cookiecutter_fsm import CookieCutter_FSM
from .cookiecutter_ui import CookieCutter_UI
from .cookiecutter_blender import CookieCutter_Blender
from .cookiecutter_exceptions import CookieCutter_Exceptions


class CookieCutter(Operator, CookieCutter_UI, CookieCutter_FSM, CookieCutter_Blender, CookieCutter_Exceptions):
    '''
    CookieCutter is used to create advanced operators very quickly!

    To use:

    - specify CookieCutter as a subclass
    - provide appropriate values for Blender class attributes: bl_idname, bl_label, etc.
    - provide appropriate dictionary that maps user action labels to keyboard and mouse actions
    - override the start function
    - register finite state machine state callbacks with the CookieCutter.FSM_State(state) function decorator
        - state can be any string that is a state in your FSM
        - Must provide at least a 'main' state
        - return values of each FSM_State decorated function tell FSM which state to switch into
            - None, '', or no return: stay in same state
    - register drawing callbacks with the CookieCutter.Draw(mode) function decorator
        - mode: 'pre3d', 'post3d', 'post2d'

    '''
    ############################################################################
    # override the following values and functions

    bl_idname = "view3d.cookiecutter_unnamed"
    bl_label = "CookieCutter Unnamed"
    default_keymap = {}

    @classmethod
    def can_start(cls, context): return True

    def start(self): pass
    def update(self): pass
    def end_commit(self): pass
    def end_cancel(self): pass
    def end(self): pass

    ############################################################################

    @classmethod
    def poll(cls, context):
        try: return cls.can_start(context)
        except Exception as e: cls._handle_exception(e, 'call can_start()')
        return False

    def invoke(self, context, event):
        self._nav = False
        self._nav_time = 0
        self._done = False
        self.context = context
        self.event = None

        try:
            self._cc_exception_init()
            self._cc_fsm_init()
            self._cc_ui_init()
            self._cc_actions_init()
        except Exception as e:
            self._handle_exception(e, 'initializing Exception Callbacks, FSM, UI, Actions')
        try: self.start()
        except Exception as e: self._handle_exception(e, 'call start()')
        try: self._cc_ui_start()
        except Exception as e: self._handle_exception(e, 'starting UI')

        self.context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def done(self, cancel=False):
        self._done = 'commit' if not cancel else 'cancel'

    def modal(self, context, event):
        self.context = context
        self.event = event
        self.drawcallbacks.reset_pre()

        profiler.printfile()

        if self._done:
            self._cc_actions_end()
            self._cc_ui_end()
            try:
                if self._done == 'commit':
                    self.end_commit()
                else:
                    self.end_cancel()
                self.end()
            except Exception as e:
                self._handle_exception(e, 'call end() with %s' % self._done)
            return {'FINISHED'} if self._done=='finish' else {'CANCELLED'}

        ret = None

        self._cc_actions_update()

        if self._cc_ui_update():
            ret = {'RUNNING_MODAL'}
        else:
            # allow window actions to pass through to Blender
            if self.actions.using('window actions'): ret = {'PASS_THROUGH'}

            # allow navigation actions to pass through to Blender
            if self.actions.navigating() or (self.actions.timer and self._nav):
                # let Blender handle navigation
                self.actions.unuse('navigate')  # pass-through commands do not receive a release event
                self._nav = True
                if not self.actions.trackpad: self.drawing.set_cursor('HAND')
                ret = {'PASS_THROUGH'}
            elif self._nav:
                self._nav = False
                self._nav_time = time.time()

        try: self.update()
        except Exception as e: self._handle_exception(e, 'call update')

        if ret: return ret

        self._cc_fsm_update()
        return {'RUNNING_MODAL'}

    def _cc_actions_init(self):
        self.actions = Actions(self.context, self.default_keymap)
        self._timer = self.context.window_manager.event_timer_add(1.0 / 120, window=self.context.window)

    def _cc_actions_update(self):
        self.actions.update(self.context, self.event, self._timer, print_actions=False)

    def _cc_actions_end(self):
        self.context.window_manager.event_timer_remove(self._timer)
        del self._timer



