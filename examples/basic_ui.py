import bpy

from ..common import ui
from ..common.useractions import ActionHandler
from ..cookiecutter.cookiecutter import CookieCutter

class CookieCutter_BasicUI(CookieCutter):
    bl_idname = 'cgcookie.cookiecutter_basicui'
    bl_label = 'CookieCutter: Basic UI'
    bl_description = 'Basic UI CookieCutter Example'
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

        # set up basic ui
        ui.framed_dialog(
            label='CookieCutter: Basic UI',
            parent=self.document.body,
            children=[
                ui.button(
                    label='Quit',
                    title='Click button to quit',
                    on_mouseclick=self.done,
                ),
            ],
        )

    def end(self):
        # this fn is automagically called when operator is ending
        print('Ended')

    @CookieCutter.FSM_State('main')
    def main(self):
        if self.actions.pressed('ESC'):
            self.done()

