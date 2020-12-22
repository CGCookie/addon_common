import bpy

from ..common.useractions import ActionHandler
from ..cookiecutter.cookiecutter import CookieCutter

class CookieCutter_Basic(CookieCutter):
    bl_idname = 'cgcookie.cookiecutter_basic'
    bl_label = 'CookieCutter: Basic'
    bl_description = 'Basic CookieCutter Example'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'

    @classmethod
    def can_start(cls, context):
        # this fn is called to determine if the operator can be started (similar to poll)
        # return False if the operator cannot start
        # return anything else to allow operator to start
        return True

    def start(self):
        # this fn is automagically called when operator is started
        self.actions = ActionHandler(self.context)
        print('Started')

    def end(self):
        # this fn is automagically called when operator is ending
        print('Ended')

    @CookieCutter.FSM_State('main')
    def main(self):
        if self.actions.pressed('ESC'):
            self.done()

