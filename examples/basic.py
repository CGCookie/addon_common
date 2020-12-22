import bpy

from ..common.useractions import ActionHandler
from ..cookiecutter.cookiecutter import CookieCutter

class CookieCutter_Basic(CookieCutter):
    @classmethod
    def can_start(cls, context):
        # this fn is called to determine if the operator can be started (similar to poll)
        # return False if the operator cannot start
        # return anything else to allow operator to start
        return True

    def start(self):
        # this fn is automagically called when operator is started
        self.actions = ActionHandler(self.context)

    def end(self):
        # this fn is automagically called when operator is ending
        pass

    @CookieCutter.FSM_State('main')
    def main(self):
        if self.actions.pressed('ESC'):
            self.done()

