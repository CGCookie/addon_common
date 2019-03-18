'''
Copyright (C) 2018 CG Cookie
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

'''
This code helps prevent circular importing.
Each of the main common objects are referenced here.
'''

debugger = None
dprint = None
profiler = None
logger = None
drawing = None
ui_draw = None

def set_global(o):
    global debugger, dprint
    global profiler, logger
    global drawing, ui_draw

    cn = type(o).__name__
    if cn == 'Debugger':   debugger, dprint = o, o.dprint
    elif cn == 'Profiler': profiler = o
    elif cn == 'Logger':   logger = o
    elif cn == 'Drawing':  drawing = o
    elif cn == 'UI_Draw':  ui_draw = o
    else: assert False

def is_global_set(s): return get_global(s) is not None

def get_global(s):
    global debuggor, dprint
    global profiler, logger
    global drawing, ui_draw
    if s == 'debugger': return debugger
    if s == 'dprint':   return dprint
    if s == 'profiler': return profiler
    if s == 'logger':   return logger
    if s == 'drawing':  return drawing
    if s == 'ui_draw':  return ui_draw
    assert False

