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
import types
import struct
import random
import traceback
import functools
import urllib.request
from itertools import chain
from concurrent.futures import ThreadPoolExecutor

import bpy
import bgl

from .ui_core import UI_Element, UI_Proxy
from .ui_utilities import (
    UIRender_Block, UIRender_Inline,
    helper_argtranslate, helper_argsplitter,
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

def div(**kwargs):
    return UI_Element(tagName='div', **kwargs)

def span(**kwargs):
    return UI_Element(tagName='span', **kwargs)

def br(**kwargs):
    return UI_Element(tagName='br', **kwargs)

def img(**kwargs):
    return UI_Element(tagName='img', **kwargs)

def textarea(**kwargs):
    return UI_Element(tagName='textarea', **kwargs)

def dialog(**kwargs):
    return UI_Element(tagName='dialog', **kwargs)

def label(**kwargs):
    ui_label = UI_Element(tagName='span', **kwargs)
    def mouseclick(e):
        element = ui_label.get_root().getElementById(ui_label.forId)
        if element is None: return
        element.dispatch_event('mouseclick', ui_event=e)
    return ui_label

def input_radio(**kwargs):
    pass

def input_checkbox(**kwargs):
    # TODO: "label" arg should create a label ui_element
    # TODO: strip input ui_element to only be checkmark!
    helper_argtranslate('label', 'innerText', kwargs)
    kw = helper_argsplitter({'innerText'}, kwargs)

    # https://www.w3schools.com/howto/howto_css_custom_checkbox.asp
    ui_input = UI_Element(tagName='input', type='checkbox', can_focus=True, **kwargs)
    ui_checkmark = UI_Element(tagName='img', classes='checkbox',  parent=ui_input)
    ui_label = UI_Element(tagName='label', parent=ui_input, innerText=kw.get('innerText',''))
    def mouseclick(e):
        ui_input.checked = True if ui_input.checked is None else None
    ui_input.add_eventListener('on_mouseclick', mouseclick)
    ui_proxy = UI_Proxy(ui_input)
    ui_proxy.translate('label', 'innerText')
    ui_proxy.map({'innerText','children','append_child','delete_child','clear_children'}, ui_label)
    return ui_proxy

def input_text(**kwargs):
    # TODO: find a better structure for input text boxes!
    #       can we get by with just input and inner span (cursor)?
    kwargs.setdefault('value', '')
    ui_container = UI_Element(tagName='span', classes='inputtext')
    ui_input  = UI_Element(tagName='input', type='text', can_focus=True, parent=ui_container, **kwargs)
    ui_cursor = UI_Element(tagName='span', classes='inputtextcursor',    parent=ui_input, innerText='|')

    data = {'orig': None, 'text': None, 'idx': 0, 'pos': None}
    def preclean():
        if data['text'] is None:
            ui_input.innerText = ui_input.value
        else:
            ui_input.innerText = data['text']
    def postflow():
        if data['text'] is None: return
        data['pos'] = ui_input.get_text_pos(data['idx'])
        ui_cursor.left = data['pos'].x - ui_input._mbp_left - ui_cursor._absolute_size.width / 2
        ui_cursor.top  = data['pos'].y + ui_input._mbp_top
    def cursor_postflow():
        if data['text'] is None: return
        ui_input._setup_ltwh()
        ui_cursor._setup_ltwh()
        # if ui_cursor._l < ui_input._l:
        #     ui_input._scroll_offset.x = min(0, ui_input._l - ui_cursor._l)
        vl = ui_input._l + ui_input._mbp_left
        vr = ui_input._r - ui_input._mbp_right
        vw = ui_input._w - ui_input._mbp_width
        if ui_cursor._r > vr:
            dx = ui_cursor._r - vr + 2
            ui_input.scrollLeft = ui_input.scrollLeft + dx
            ui_input._setup_ltwh()
        if ui_cursor._l < vl:
            dx = ui_cursor._l - vl - 2
            ui_input.scrollLeft = ui_input.scrollLeft + dx
            ui_input._setup_ltwh()
    def focus(e):
        data['orig'] = data['text'] = ui_input.value
        data['idx'] = 0 # len(data['text'])
        data['pos'] = None
    def blur(e):
        ui_input.value = data['text']
        data['text'] = None
    def keypress(e):
        if type(e.key) is int:
            # https://www.w3schools.com/jsref/tryit.asp?filename=tryjsref_event_key_keycode2
            # TODO: use enum rather than magic numbers!
            if e.key == 8:
                if data['idx'] == 0: return
                data['text'] = data['text'][0:data['idx']-1] + data['text'][data['idx']:]
                data['idx'] -= 1
            elif e.key == 13:
                ui_input.blur()
            elif e.key == 27:
                data['text'] = data['orig']
                ui_input.blur()
            elif e.key == 35:
                data['idx'] = len(data['text'])
                ui_input.dirty_flow()
            elif e.key == 36:
                data['idx'] = 0
                ui_input.dirty_flow()
            elif e.key == 37:
                data['idx'] = max(data['idx'] - 1, 0)
                ui_input.dirty_flow()
            elif e.key == 39:
                data['idx'] = min(data['idx'] + 1, len(data['text']))
                ui_input.dirty_flow()
            elif e.key == 46:
                if data['idx'] == len(data['text']): return
                data['text'] = data['text'][0:data['idx']] + data['text'][data['idx']+1:]
            else:
                changed = False
        else:
            data['text'] = data['text'][0:data['idx']] + e.key + data['text'][data['idx']:]
            data['idx'] += 1
        preclean()
    ui_input.preclean = preclean
    ui_input.postflow = postflow
    ui_cursor.postflow = cursor_postflow
    ui_input.add_eventListener('on_focus', focus)
    ui_input.add_eventListener('on_blur', blur)
    ui_input.add_eventListener('on_keypress', keypress)

    ui_proxy = UI_Proxy(ui_container)
    ui_proxy.map('value', ui_input)
    ui_proxy.map('innerText', ui_input)

    return ui_proxy

def framed_dialog(label=None, resizable=None, resizable_x=True, resizable_y=False, **kwargs):
    # TODO: always add header, and use UI_Proxy translate+map "label" to change header
    ui_document = Globals.ui_document
    ui_dialog = UI_Element(tagName='dialog', classes='framed', **kwargs)
    if label is not None:
        ui_label = ui_dialog.append_child(UI_Element(tagName='div', classes='header', innerText=label))
        is_dragging = False
        mousedown_pos = None
        original_pos = None
        def mousedown(e):
            nonlocal is_dragging, mousedown_pos, original_pos, ui_dialog
            ui_document.ignore_hover_change = True
            is_dragging = True
            mousedown_pos = e.mouse

            l = ui_dialog.left_pixels
            if l is None or l == 'auto': l = 0
            t = ui_dialog.top_pixels
            if t is None or t == 'auto': t = 0
            original_pos = Point2D((float(l), float(t)))
        def mouseup(e):
            nonlocal is_dragging
            is_dragging = False
            ui_document.ignore_hover_change = False
        def mousemove(e):
            nonlocal is_dragging, mousedown_pos, original_pos, ui_dialog
            if not is_dragging: return
            delta = e.mouse - mousedown_pos
            new_pos = original_pos + delta
            w,h = ui_dialog.width_pixels,ui_dialog.height_pixels
            rw,rh = ui_dialog._relative_element.width_pixels,ui_dialog._relative_element.height_pixels
            # ui_dialog.left = clamp(new_pos.x, 0, rw - w)
            # ui_dialog.top  = clamp(new_pos.y, -rh + h, 0)
            ui_dialog.reposition(left=clamp(new_pos.x, 0, rw - w), top=clamp(new_pos.y, -rh + h, 0))
        ui_label.add_eventListener('on_mousedown', mousedown)
        ui_label.add_eventListener('on_mouseup', mouseup)
        ui_label.add_eventListener('on_mousemove', mousemove)
    if resizable is not None: resizable_x = resizable_y = resizable
    if resizable_x or resizable_y:
        is_resizing = False
        mousedown_pos = None
        original_size = None
        def resizing(e):
            nonlocal ui_dialog
            dpi_mult = Globals.drawing.get_dpi_mult()
            l,t,w,h = ui_dialog.left_pixels, ui_dialog.top_pixels, ui_dialog.width_pixels, ui_dialog.height_pixels
            mt,mr,mb,ml = ui_dialog._get_style_trbl('margin', scale=dpi_mult)
            bw = ui_dialog._get_style_num('border-width', 0, scale=dpi_mult)
            ro = ui_dialog._relative_offset
            gl = l + ro.x + w - mr - bw
            gb = t - ro.y - h + mb + bw
            rx = resizable_x and gl <= e.mouse.x < gl + bw
            ry = resizable_y and gb >= e.mouse.y > gl - bw
            if rx and ry: return 'both'
            if rx: return 'width'
            if ry: return 'height'
            return False
        def mousedown(e):
            nonlocal is_resizing, mousedown_pos, original_size, ui_dialog
            if e.target != ui_dialog: return
            ui_document.ignore_hover_change = True
            l,t,w,h = ui_dialog.left_pixels, ui_dialog.top_pixels, ui_dialog.width_pixels, ui_dialog.height_pixels
            is_resizing = resizing(e)
            mousedown_pos = e.mouse
            original_size = (w,h)
        def mouseup(e):
            nonlocal is_resizing
            ui_document.ignore_hover_change = False
            is_resizing = False
        def mousemove(e):
            nonlocal is_resizing, mousedown_pos, original_size, ui_dialog
            if not is_resizing:
                r = resizing(e)
                if   r == 'width':  ui_dialog._computed_styles['cursor'] = 'ew-resize'
                elif r == 'height': ui_dialog._computed_styles['cursor'] = 'ns-resize'
                elif r == 'both':   ui_dialog._computed_styles['cursor'] = 'grab'
                else:               ui_dialog._computed_styles['cursor'] = 'default'
            else:
                delta = e.mouse - mousedown_pos
                minw,maxw = ui_dialog._computed_min_width,  ui_dialog._computed_max_width
                minh,maxh = ui_dialog._computed_min_height, ui_dialog._computed_max_height
                if minw == 'auto': minw = 0
                if maxw == 'auto': maxw = float('inf')
                if minh == 'auto': minh = 0
                if maxh == 'auto': maxh = float('inf')
                if is_resizing in {'width', 'both'}:
                    ui_dialog.width = clamp(original_size[0] + delta.x, minw, maxw)
                if is_resizing in {'height', 'both'}:
                    ui_dialog.height = clamp(original_size[1] - delta.y, minh, maxh)
                ui_dialog.dirty_flow()
        ui_dialog.add_eventListener('on_mousedown', mousedown)
        ui_dialog.add_eventListener('on_mouseup', mouseup)
        ui_dialog.add_eventListener('on_mousemove', mousemove)
    ui_inside = ui_dialog.append_child(UI_Element(tagName='div', classes='inside', style='overflow-y:scroll'))

    ui_proxy = UI_Proxy(ui_dialog)
    ui_proxy.map(['children','append_child','delete_child','clear_children'], ui_inside)
    return ui_proxy




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



