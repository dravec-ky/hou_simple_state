from . import core
from stateutils import ancestorObject
import hou

class FFDrawable(hou.SimpleDrawable):
    """
    Drawables for tools

    """
    def __init__(self, state, geo = hou.drawablePrimitive.Sphere, name = "tool"):
        self.state = state
        self.scene_viewer = state.scene_viewer

        self.name = "%s_%s" % (self.state.state_name, name)

        super().__init__(self.scene_viewer, geo, self.name)

        self.setDisplayMode(hou.drawableDisplayMode.CurrentViewportMode)
        self.setXray(True)

        #Editable Attributes
        self.scale = hou.Vector3(1,1,1)
        self.uniform_scale = 1.0
        self.rotation = hou.Vector3()

        self.normal = hou.Vector3(0,0,1)
        self.normal_axis = hou.Vector3(0,0,-1)
        self.up = hou.Vector3(0,1,0)

        self.xform = hou.Matrix4(1)
        self.position = hou.Vector3()

    def update(self):
        parent = ancestorObject(self.state.node)
        parent_xform = parent.worldTransform()
        
        xform_scale = hou.hmath.buildScale(self.scale*self.uniform_scale)
        xform_rotate = hou.hmath.buildRotate(self.rotation)

        xform_normal_axis = hou.hmath.buildRotateZToAxis(self.normal_axis)
        xform_normal = xform_normal_axis * hou.hmath.buildRotateLookAt(hou.Vector3(0,0,0),self.normal, self.up)

        xform = self.xform
        xform_translate = hou.hmath.buildTranslate(self.position)

        # All attributes are applied to final transform from top to bottom
        self._xform = xform_scale * xform_rotate * xform_normal * xform_translate  * xform * parent_xform

        self.setTransform(self._xform)

    def getTransform(self):
        self.update()
        return self._xform

class BrushDrawable:
 
    def __init__(self, drawable_action, name = "brush"):
        self._radius = 1.0
        self._softness = .5
        self._color = hou.Color()
        self._position = hou.Vector3()

        circle_verb = box_verb = hou.sopNodeTypeCategory().nodeVerb("circle")
        circle_verb.setParms({
            "type": 2,
            "arc": 1,
        })
        circle_geo = hou.Geometry()
        circle_verb.execute(circle_geo, [])

        self.cursor_outer = drawable_action.bindDrawable(geo = circle_geo, name = "cursor_outer")
        self.cursor_inner = drawable_action.bindDrawable(geo = circle_geo, name = "cursor_inner")

        self.drawables = (self.cursor_outer, self.cursor_inner)

        for d in self.drawables:
            d.normal = hou.Vector3(0,1,0)
            d.setDisplayMode(hou.drawableDisplayMode.WireframeMode)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        for d in self.drawables:
            d.position = value
        self._position = value

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        for d in self.drawables:
            d.scale = hou.Vector3(value,value,value)
        self._radius = value

    @property
    def softness(self):
        return self._softness

    @radius.setter
    def softness(self, value):
        self.drawables[1].uniform_scale = 1-value
        self._softness = value


    