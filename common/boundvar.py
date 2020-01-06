'''
Copyright (C) 2020 CG Cookie
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

import re
import inspect

class IgnoreChange(Exception): pass

class BoundVar:
    def __init__(self, value_str, *, on_change=None, frame_depth=1):
        assert type(value_str) is str, 'BoundVar: constructor needs value as string!'
        frame = inspect.currentframe()
        for i in range(frame_depth): frame = frame.f_back
        self._f_globals = frame.f_globals
        self._f_locals = dict(frame.f_locals)
        try:
            exec(value_str, self._f_globals, self._f_locals)
        except Exception as e:
            print('Caught exception when trying to bind to variable')
            print(e)
            assert False, 'BoundVar: value string ("%s") must be a valid variable!' % (value_str)
        self._f_locals.update({'boundvar_interface': self._boundvar_interface})
        self._value_str = value_str
        self._callbacks = []
        self._validators = []
        self._disabled = False
        if on_change: self.on_change(on_change)

    def _boundvar_interface(self, v): self._v = v
    def _call_callbacks(self):
        for cb in self._callbacks: cb()

    def __str__(self): return str(self.value)

    def get(self):
        return self.value
    def set(self, value):
        self.value = value

    @property
    def disabled(self):
        return self._disabled
    @disabled.setter
    def disabled(self, v):
        self._disabled = bool(v)
        self._call_callbacks()

    @property
    def value(self):
        exec('boundvar_interface(' + self._value_str + ')', self._f_globals, self._f_locals)
        return self._v
    @value.setter
    def value(self, value):
        try:
            for validator in self._validators: value = validator(value)
        except IgnoreChange:
            return
        if self.value == value: return
        exec(self._value_str + ' = ' + str(value), self._f_globals, self._f_locals)
        self._call_callbacks()
    @property
    def value_as_str(self): return str(self)

    def on_change(self, fn):
        self._callbacks.append(fn)

    def add_validator(self, fn):
        self._validators.append(fn)


class BoundBool(BoundVar):
    def __init__(self, value_str, **kwargs):
        super().__init__(value_str, frame_depth=2, **kwargs)
    @property
    def checked(self): return self.value
    @checked.setter
    def checked(self,v): self.value = v


class BoundInt(BoundVar):
    def __init__(self, value_str, *, min_value=None, max_value=None, **kwargs):
        super().__init__(value_str, frame_depth=2, **kwargs)
        self._min_value = min_value
        self._max_value = max_value
        self.add_validator(self.int_validator)

    def int_validator(self, value):
        try:
            t = type(value)
            if t is str:     nv = int(re.sub(r'\D', '', value))
            elif t is int:   nv = value
            elif t is float: nv = int(value)
            else: assert False, 'Unhandled type of value: %s (%s)' % (str(value), str(t))
            if self._min_value is not None: nv = max(nv, self._min_value)
            if self._max_value is not None: nv = min(nv, self._max_value)
            return nv
        except ValueError as e:
            raise IgnoreChange()
        except Exception:
            # ignoring all exceptions?
            raise IgnoreChange()


class BoundFloat(BoundVar):
    def __init__(self, value_str, *, min_value=None, max_value=None, **kwargs):
        super().__init__(value_str, frame_depth=2, **kwargs)
        self._min_value = min_value
        self._max_value = max_value
        self.add_validator(self.float_validator)

    def float_validator(self, value):
        try:
            t = type(value)
            if t is str:     nv = float(re.sub(r'[^\d.]', '', value))
            elif t is int:   nv = float(value)
            elif t is float: nv = value
            else: assert False, 'Unhandled type of value: %s (%s)' % (str(value), str(t))
            if self._min_value is not None: nv = max(nv, self._min_value)
            if self._max_value is not None: nv = min(nv, self._max_value)
            return nv
        except ValueError as e:
            raise IgnoreChange()
        except Exception:
            # ignoring all exceptions?
            raise IgnoreChange()

