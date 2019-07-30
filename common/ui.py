'''
Copyright (C) 2019 CG Cookie
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

import os
import re
import math
import time
import struct
import random
import traceback
import functools
import urllib.request
from itertools import chain
from concurrent.futures import ThreadPoolExecutor

import bpy
import bgl

from .ui_core import UI_Element
from .ui_utilities import (
    UIRender_Block, UIRender_Inline,
    helper_argtranslate,
)
from .ui_styling import UI_Styling

from .globals import Globals
from .decorators import blender_version_wrapper
from .maths import Point2D, Vec2D, clamp, mid, Color, Box2D, Size2D
from .drawing import Drawing, ScissorStack
from .fontmanager import FontManager

from ..ext import png


'''
Notes about addon_common's UI system

- The system is designed similarly to how the Browser will render HTML+CSS
- All UI elements are containers
- All classes herein are simply "starter" UI elements
    - You can freely change all properties to make any element turn into another
- Styling
    - Styling specified here is base styling for UI elements of same type
    - Base styling specified here are overridden by stylesheet, which is overridden by custom styling
    - Note: changing tagname will not reset the base styling.  in other words, if the element starts off
            as a UI_Button, changing tagname to "flexbox" will not change base styling from what is
            specified in UI_Button.


Implementation details

- root element will be sized to entire 3D view region
- each element
    - is responsible for communicating with children
    - will estimate its size (min, max, preferred), but these are only suggestions for the parent
    - dictates size and position of its children
    - must submit to the sizing and position given by the parent

See top comment in `ui_utilities.py` for links to useful resources.
'''


# all html tags: https://www.w3schools.com/tags/


def button(**kwargs):
    helper_argtranslate('label', 'innerText', kwargs)
    return UI_Element(tagName='button', **kwargs)

def p(**kwargs):
    return UI_Element(tagName='p', **kwargs)

def textarea(**kwargs):
    return UI_Element(tagName='textarea', **kwargs)

def dialog(**kwargs):
    return UI_Element(tagName='dialog', **kwargs)

def framed_dialog(label=None, **kwargs):
    ui_dialog = UI_Element(tagName='dialog', classes='framed', **kwargs)
    if label is not None:
        ui_label = ui_dialog.append_child(UI_Element(tagName='div', classes='header', innerText=label))
        is_dragging = False
        mousedown_pos = None
        original_pos = None
        def mousedown(e):
            nonlocal is_dragging, mousedown_pos, original_pos
            is_dragging = True
            mousedown_pos = e.mouse

            l = ui_dialog.left
            if l is None or l == 'auto': l = 0
            if type(l) is tuple: l = l[0]
            t = ui_dialog.top
            if t is None or t == 'auto': t = 0
            if type(t) is tuple: t = t[0]
            original_pos = Point2D((float(l), float(t)))
        def mouseup(e):
            nonlocal is_dragging
            is_dragging = False
        def mousemove(e):
            nonlocal is_dragging, mousedown_pos, original_pos
            if not is_dragging: return
            delta = e.mouse - mousedown_pos
            new_pos = original_pos + delta
            ui_dialog.left = new_pos.x
            ui_dialog.top = new_pos.y
        ui_label.add_eventListener('on_mousedown', mousedown)
        ui_label.add_eventListener('on_mouseup', mouseup)
        ui_label.add_eventListener('on_mousemove', mousemove)
    ui_inside = ui_dialog.append_child(UI_Element(tagName='div', classes='inside', style='overflow-y:scroll'))
    return {'dialog':ui_dialog, 'inside':ui_inside}


# class UI_Flexbox(UI_Core):
#     '''
#     This container will resize the width/height of all children to fill the available space.
#     This element is useful for lists of children elements, growing along one dimension and filling along other dimension.
#     Children of row flexboxes will take up entire height; children of column flexboxes will take up entire width.

#     TODO: model off flexbox more closely?  https://css-tricks.com/snippets/css/a-guide-to-flexbox/
#     '''

#     style_default = '''
#         display: flexbox;
#         flex-direction: row;
#         flex-wrap: nowrap;
#         overflow: scroll;
#     '''

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#     def compute_content_size(self):
#         for child in self._children:
#             pass

#     def layout_children(self):
#         for child in self._children: child.recalculate()

#         # assuming all children are drawn on top on one another
#         w,h = self._min_width,self._min_height
#         W,H = self._max_width,self._max_height
#         for child in self.get_visible_children():
#             w = max(w, child._min_width)
#             h = max(h, child._min_height)
#             W = min(W, child._max_width)
#             H = min(H, child._max_height)
#         self._min_width,self.min_height = w,h
#         self._max_width,self.max_height = W,H

#         # do not clean self if any children are still dirty (ex: they are deferring recalculation)
#         self._is_dirty = any(child._is_dirty for child in self._children)

#     def position_children(self, left, top, width, height):
#         for child in self.get_visible_children():
#             child.position(left, top, width, height)

#     def draw_children(self):
#         for child in self.get_visible_children():
#             child.draw()



# class UI_Label(UI_Core):
#     def __init__(self, label=None, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._label = label or ''


# class UI_Button(UI_Core):
#     def __init__(self, label=None, click=None, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._label = label or ''
#         self._click = click




# class UI_Dialog(UI_Core):
#     '''
#     a dialog window, can be shown modal
#     '''

#     def __init__(self, *args, **kwargs):
#         super().__init__()



# class UI_Body(UI_Core):
#     def __init__(self, actions, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         self._actions = actions
#         self._active = None         # element that is currently active
#         self._active_last = None
#         self._focus = None          # either active element or element under the cursor
#         self._focus_last = None

#     def modal(self, actions):
#         if self.actions.mousemove:
#             # update the tooltip's position
#             # close windows that have focus
#             pass

#         if event.type == 'MOUSEMOVE':
#             mouse = Point2D((float(event.mouse_region_x), float(event.mouse_region_y)))
#             self.tooltip_window.fn_sticky.set(mouse + self.tooltip_offset)
#             self.tooltip_window.update_pos()
#             if self.focus and self.focus_close_on_leave:
#                 d = self.focus.distance(mouse)
#                 if d > self.focus_close_distance:
#                     self.delete_window(self.focus)

#         ret = {}

#         if self.active and self.active.state != 'main':
#             ret = self.active.modal(context, event)
#             if not ret: self.active = None
#         elif self.focus:
#             ret = self.focus.modal(context, event)
#         else:
#             self.active = None
#             for win in reversed(self.windows):
#                 ret = win.modal(context, event)
#                 if ret:
#                     self.active = win
#                     break

#         if self.active != self.active_last:
#             if self.active_last and self.active_last.fn_event_handler:
#                 self.active_last.fn_event_handler(context, UI_Event('HOVER', 'LEAVE'))
#             if self.active and self.active.fn_event_handler:
#                 self.active.fn_event_handler(context, UI_Event('HOVER', 'ENTER'))
#         self.active_last = self.active

#         if self.active:
#             if self.active.fn_event_handler:
#                 self.active.fn_event_handler(context, event)
#             if self.active:
#                 tooltip = self.active.get_tooltip()
#                 self.set_tooltip_label(tooltip)
#         else:
#             self.set_tooltip_label(None)

#         return ret



