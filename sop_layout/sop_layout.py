"""
State:          Peter.dravecky::ff layout::3.0
State type:     peter.dravecky::ff_layout::3.0
Description:    Peter.dravecky::ff layout::3.0
Author:         peter.dravecky
Date Created:   March 20, 2025 - 09:56:46
"""

import hou
import viewerstate.utils as su
from imp import reload

import ..simple_state.core
import ..simple_state.actions
import ..simple_state.drawable

reload(..simple_state.core)z
reload(..simple_state.actions)
reload(..simple_state.drawable)

from ..simple_state.core import *
from ..simple_state.actions import *

class Select(KeyToggleAction, MenuParmAction):
    pass

class Add(KeyToggleAction, MenuParmAction):
    pass

class Brush(KeyToggleAction, MenuParmAction, DrawableAction):

    class Scale(MouseWheelAction):
        def init(self):
            pass

        def start(self):
            if self.parent_event is not None:
                radius = self.parent_event.radius.eval()
                softness = self.parent_event.softness
                density = self.parent_event.density

            scroll = self.state.ui.mouse.wheel
            cursor = self.parent_event.cursor

            radius *= 1+scroll*0.2

            self.state.debug("Brush Radius: %d" % radius, Debug.MOUSEWHEEL)
            self.parent_event.radius.set(radius)

    def init(self):
        self.cursor = BrushDrawable(self,"brush")

        self.radius = self.hookParm("brush_radius")
        self.softness = self.hookParm("brush_softness")
        self.density = self.hookParm("brush_density")
        
    def refresh(self):
        pass



    def draw(self):
        ray_origin = self.state.ui.ray.origin
        ray_dir = self.state.ui.ray.dir
        position, normal = self.state.getNodeCollision(ray_origin,ray_dir)

        self.cursor.position = position
        self.cursor.radius = self.radius.eval()
        self.cursor.softness = self.softness.eval()




class MyState(FFState):

    def onBuild(self):
        self.hookActions((
            ToggleManager(state = self, use_default = False, events = (
                Select(state = self, name = "op_select", label = "Select",
                    hotkey = "s", menu_parm = "optool", menu_id = 0 ),
                Add(state = self, name = "op_add", label = "Add",
                    hotkey = "a", menu_parm = "optool", menu_id = 1,
                    events = (
                    )),
                Brush(state = self, name = "op_brush", label = "Brush",
                    hotkey = "b", menu_parm = "optool", menu_id = 2, 
                    events = (
                        Brush.Scale(state = self, name = "brush_scroll"),
                    )),
            )),
            )
        )


    def onStart(self): 
        self.enable_collision = self.node.input(1) != None
        if self.enable_collision:
            self.collision_geo = self.node.node("OUT_Collision").geometry()

    def getNodeCollision(self, origin, direction, freeze = True, intersect_self = False):
        position = hou.Vector3()
        normal = hou.Vector3()
        uvw = hou.Vector3()

        hit = -1



        try:
            if intersect_self:
                self.instance_geo = self.node.geometry().freeze(True)
                hit = self.instance_geo.intersect(origin,direction,position,normal,uvw)

            if hit < 0:
                if self.enable_collision:
                    hit = self.collision_geo.intersect(origin,direction,position,normal,uvw)
            if hit < 0:
                position = su.cplaneIntersection(self.scene_viewer, origin, direction)
                normal = hou.Vector3(0,1,0)
        except:
            self.debug("Node Collision failed!")

        return position, normal



def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = kwargs["type"].definition().sections()["DefaultState"].contents()
    state_label = "Peter.dravecky::ff layout::3.0"
    state_cat = hou.sopNodeTypeCategory()

    template = FFStateTemplate(state_typename, state_label, state_cat)

    template.bindFactory(MyState)
    template.bindParameter( hou.parmTemplateType.Float, name="text_size", 
        label="Text Size", min_limit=0.5, max_limit=5, 
        default_value=0.75 )

    template.bindIcon(kwargs["type"].icon())

    return template
    







