'''
Copyright (C) 2019 CG Cookie
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

import contextlib

from ..common.fsm import FSM
from ..common.debug import debugger
from ..common.utils import find_fns

from .cookiecutter_fsm import CookieCutter_FSM

class CookieCutter_Exceptions:
    @staticmethod
    @contextlib.contextmanager
    def catch_exception(action, fatal=False):
        try:
            yield None
        except Exception as e:
            print('CookieCutter caught exception while trying to %s' % action)
            debugger.print_exception()
            if fatal: assert False
            self._callback_exception_callbacks(e)

    @staticmethod
    def _exception_callback_wrapper(fn):
        fn._cc_exception_callback = True
        return fn
    Exception_Callback = _exception_callback_wrapper

    def _handle_exception(self, e):
        self._callback_exception_callbacks(e)

    def _callback_exception_callbacks(self, e):
        for fn in self._exception_callbacks:
            try:
                fn(self, e)
            except Exception as e2:
                print('CookieCutter caught exception while calling back exception callbacks: %s' % fn.__name__)
                debugger.print_exception()

    def _cc_exception_init(self):
        self._exception_callbacks = [fn for (_,fn) in find_fns(self, '_cc_exception_callback')]
        self.fsm.add_exception_callback(self._handle_exception)