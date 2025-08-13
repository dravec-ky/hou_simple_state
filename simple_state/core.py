import hou
import viewerstate.utils as su
import traceback
import time
from . import *

class Debug:
    NORMAL = False
    BASEEVENTS = False
    EVENTLOOP = False
    VERBOSE = False
    TOGGLE = True
    PARMS = True
    KEYEVENTS = False
    DRAW = False
    MOUSEWHEEL = False

#Class for managing parameter sync between HUD, node and internal values
class FFParm:

    def __init__(self, state = None, name = None, parm = None, is_hud = False):
        self.state = state
        self.name = name
        self.parm = parm
        self.value = parm.eval()
        self.is_hud = is_hud
        self.just_set = False
        self.max = None

        template = self.parm.parmTemplate()
        if template.type() == hou.parmTemplateType.Float:
            self.max = template.maxValue()

    def eval(self):
        #self.state.log("Getting %s" % self.name)
        return self.value
    
    def set(self, val):
        #self.state.log("setting %s" % self.name)
        self.value = val
        if val != self.parm.eval():
            with hou.undos.disabler():
                self.state.debug("Parm %s set" % self.name, Debug.PARMS)
                self.just_set = True
                self.parm.set(val)
        if self.is_hud:
            self.state.setHUDValue(self.name, val, bar = self.max)

    def update(self):
        self.just_set = False
        val = self.parm.eval()
        self.value = val
        if self.is_hud:
            self.state.setHUDValue(self.name, val, bar = self.max)

#Template subclass for automatically adding handles/selectors/drawables from events
class FFStateTemplate(hou.ViewerStateTemplate):
    def __init__(self, state_name, state_label, node_type_category, contexts=None):
        #print("Testing")
        self.hotkey_list = []
        self.state_name = state_name
        super().__init__(state_name, state_label, node_type_category)

    def saveHotkeys(self, event, itr = 0):
        if itr<16:
            for e in event.actions_dict.values():
                if hasattr(e,"hotkey"):
                    self.hotkey_list.append(e)
                    self.saveHotkeys(e, itr = itr+1)

    def bindFactory(self, callable):
        super().bindFactory(callable)
        self.test_state = callable(None, None)

        for key in self.test_state.ui.keys:
                self.hotkey_list.append(key)

        for key in self.hotkey_list:
            su.hotkey(self.state_name, "hotkey_%s" % key, key, "hotkey_%s" % key)

#Main state class
class FFState(object):
    """
    Pre-filled state object to be used with Houdini viewer states,
    changes the structure of writig a viewer state form direct reaction to callbacks
    to a tree structure of Actions which pass callbacks between each other

    It is therefore not recommended to overload the State callback functions,
    if so call the overloaded function using 
    
    super().callbackFunction(self,parms)

    or handling them by defining a StateAction in onBuild()
    """

    #Simple dictionary for keeping all controls in one place
    #id : keybind
    CONTROLS = {
        "add": "a"
    }

    #https://www.sidefx.com/docs/houdini/hom/hud_info.html
    HUD_TEMPLATE = {
        "title": "Default FF State", "desc": "tool", "icon": "SOP_matchsize",
        "rows": [
            {"id": "modedev", "type": "divider"},
        ]
    }

    class UIInfo:
        """
        Holds all UI event changed information, similar to hou.UIInfo but also
        contains 
        """

        class MouseDevice:
            def __init__(self):
                self.device = None
                self.wheel = 0.0
        
        class RayDevice:
            def __init__(self):
                self.origin = hou.Vector3(0,0,0)
                self.dir = hou.Vector3(0,0,0)

        def __init__(self):
            self.ui_event = None
            self.event_type = None
            self.device = None

            self.keys = []
            self.key_pressed = {}
            self.key_down = {}
            self.key_up = {}
            self.key_held = {}
            self.key_down_time = {}
            self.key_hold_time = {}

            self.mouse = self.MouseDevice()
            self.ray = self.RayDevice()

            self.ray_origin = hou.Vector3(0,1,0)
            self.ray_dir = hou.Vector3(0,-1,0)

            self.parms_changed = []
            

        def addKey(self, key):
            self.keys.append(key)
            self.key_pressed[key] = False
            self.key_down[key] = False
            self.key_up[key] = False
            self.key_held[key] = False
            self.key_down_time[key] = 0.0
            self.key_hold_time[key] = 0.0

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = None
        self.ui = self.UIInfo()
        self.state_action = None
        self.is_active = False

        self.actions = {}
        self.parms = {}

        self.debug(" State '%s' Initialized" % self.state_name, Debug.BASEEVENTS)

        self.onBuild()

    """ CALLBACK FUNCTIONS """
    
    def onParmChanged(self, **kwargs):
        self.state_action.onParmChanged(kwargs)

        self.debug("onParmChanged", Debug.PARMS)
        parm_tuple = kwargs['parm_tuple']
        if parm_tuple is not None: 
            self.ui.parms_changed = list(set([x.tuple().name() for x in parm_tuple]))

            if len(parm_tuple) > 0:
                kwargs["event_type"] = 'onParmChanged'
                self.state_action.passEvent(**kwargs)
            
    def onEnter(self, kwargs):
        self.debug(" State '%s' onEnter" % self.state_name, Debug.BASEEVENTS)

        self.node = kwargs["node"]
        if self.state_action is None:
            self.state_action = actions.FFStateAction(self, self.state_name)


        self.debug("onParmChanged callback", Debug.PARMS)
        self.node.addEventCallback([hou.nodeEventType.ParmTupleChanged], self.onParmChanged)

        for e in self._actions:
            self.state_action.hookAction(e)

        self.is_active = True

        self.onStart()
        self.state_action.onEnter(kwargs)
        self.state_action.passEvent(event_type='onEnter',**kwargs)

    def onKeyTransitEvent(self, kwargs):
        self.state_action.onKeyTransitEvent(kwargs)

        ui_event = kwargs['ui_event']
        ui = self.ui

        ui.device = ui_event.device()
        
        key = ui_event.device().keyString()
        is_down = ui_event.device().isKeyDown()
        is_up = ui_event.device().isKeyUp()

        if key not in ui.key_pressed.keys():
            ui.addKey(key)

        # Log the key state
        ui.key = key
        ui.key_down[key] = is_down
        ui.key_up[key] = is_up

        if is_down:
            ui.key_pressed[key] = True
            ui.key_down_time[key] = time.time()
            ui.key_hold_time[key] = 0.0

            self.debug("%s down" % (key),Debug.KEYEVENTS)

            self.state_action.passEvent(event_type='onKeyDown', **kwargs)

        if is_up:
            hold_time = time.time() - ui.key_down_time[key]
            ui.key_hold_time[key] = hold_time

            self.debug("%s up after %f" % (key, hold_time),Debug.KEYEVENTS)

            self.state_action.passEvent(event_type='onKeyUp', **kwargs)
            ui.key_pressed[key] = False

        return False

    def onKey(self, kwargs):
        self.state_action.onKey(kwargs)
        self.state_action.passEvent(event_type='onKey')

    def onMouseEvent(self, kwargs):

        ui_event = kwargs['ui_event']
        self.ui.ray.origin, self.ui.ray.dir = ui_event.ray()

        self.state_action.onMouseEvent(kwargs)
        self.state_action.passEvent(event_type='onMouse')

    def onMouseWheelEvent(self, kwargs):

        ui_event = kwargs['ui_event']
        self.ui.mouse.wheel = ui_event.device().mouseWheel()

        self.debug("Mouse Wheel event: %d" % self.ui.mouse.wheel, Debug.MOUSEWHEEL)

        self.state_action.onMouseWheelEvent(kwargs)
        self.state_action.passEvent(event_type='onMouseWheel', **kwargs)

    def onDraw(self, kwargs):
        self.state_action.passEvent(event_type='onDraw', **kwargs)

    def onInterrupt(self, kwargs):
        self.debug(" State '%s' onInterrupt" % self.state_name, Debug.BASEEVENTS)

        self.is_active = False
        self.state_action.onInterrupt(kwargs)

    def onResume(self, kwargs):#
        self.debug(" State '%s' onResume" % self.state_name, Debug.BASEEVENTS)

        self.is_active = True
        self.state_action.onResume(kwargs)

    def onExit(self, kwargs):
        self.debug(" State '%s' onExit" % self.state_name, Debug.BASEEVENTS)

        if self.node is not None:
            self.debug("onParmChanged callback remove", Debug.PARMS)
            self.node.removeEventCallback([hou.nodeEventType.ParmTupleChanged], self.onParmChanged)

        self.state_action.onExit(kwargs)
        self.state_action.passEvent(event_type='onExit', **kwargs)

    """ PUBLIC FUNCTIONS """
    
    def setHUDValue(self,id_name, value, bar = None):
        updates = {}
        if isinstance(value,float):
            value = round(value,2)
            #if bar is not None:
                #self.log("Setting bargraph to %s" % str(value/bar))
                #updates[id_name+"_g"] = {"value":value/bar}

        updates[id_name] = value

        self.scene_viewer.hudInfo(hud_values=updates)

    def setHUDProperty(self,id_name, property_name, value):
        updates = { id_name : { property_name : value }}
        self.scene_viewer.hudInfo(hud_values=updates)

    def debug(self, msg, msg_type = True):
        if msg_type == True:
            if hasattr(self,'log'):
                self.log(msg)
            else:
                print("Log Error: %s" % msg)

    def hookActions(self, actions):
        self._actions = actions

    """ OVERLOAD FUNCTIONS """

    def onBuild(self):
        """
        Overload function for building the action structure, called during __init__
        should only contain self.hookActions() and a StateAction overload (optional)
        all other initializations should take place in onStart()

        Example:
        self.hookActions(
            (
                CustomAction( parms, events = 
                    (
                        CustomAction( parms ),
                        CustomAction( parms ),
                        CustomAction( parms )
                    )
                ),
                CustomAction( parms )
            )
        )

        self.state_action = CustomStateAction()
        """
        pass

    def onStart(self):
        """
        Function called on onEnter event callback
        """
        pass