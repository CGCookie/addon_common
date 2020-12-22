'''
Copyright (C) 2020 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson, and Patrick Moore

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

import bpy

bl_info = {
    "name": "CookieCutter Examples",
    "description": "Contains a set of examples for using CookieCutter",
    "author": "Jonathan Denning, Jonathan Williamson, Patrick Moore",
    "version": (0, 0, 0),
    "blender": (2, 83, 0),
    "location": "View 3D",
    "category": "3D View",
}

RF_classes = []


from .examples.basic import CookieCutter_Basic
RF_classes += [CookieCutter_Basic]


def register():
    for cls in RF_classes: bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(RF_classes): bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
