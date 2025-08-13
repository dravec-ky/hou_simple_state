from .core import *
from .drawable import *
KEY_HOLD_TIME = .2

"""

Event handling is abstracted to separate objects called Actions. 
These FFActions are built in a tree hierarchy - makes it easy
to program one tool with multiple subtools that you can switch between,
each with their various drawables.
Anytime Houdini sends an event callback it travels down this tree
ans allows each Action to react to it. These reactions are programmed
by the user in the exposed functions - start(), refresh(), finish(), etc.

"""

class FFAction:
    """
    Base class for executing different events during a state
    """
    def __init__(self, state = None, name = "op_default", events = (), label = "Default"):

        self.name = name
        self.label = label
        self.state = state
        self.parent_event = None

        self.actions = []
        self.actions_dict = {}
        self._callback_dict = {}

        self.addCallback('onEnter',self._onEnter)
        self.addCallback('onStart',self._startAction)
        self.addCallback('onExit',self._onExit)

        self.state.debug(" Event '%s' initialized" % self.name, Debug.NORMAL)

        for a in events:
            self.hookAction(a)

    def _executeEvent(self, event_type=None, **kwargs):
        if event_type in self._callback_dict:
            self.state.debug("%s in callback for %s" % (event_type, self.name), Debug.EVENTLOOP)
            
            callback_funcs = self._callback_dict[event_type]
            for func in callback_funcs:
                self.state.debug(str(func), Debug.EVENTLOOP)
                func.__func__(self, **kwargs)

    def _startAction(self,**kwargs):
        self.start()        

    def _onEnter(self,**kwargs):
        self.init()

    def _onExit(self,**kwargs):
        self.exit()

    """ OVERLOAD FUNCTIONS"""

    def init(self):
        pass
        
    def start(self):
        s = self.state
        s.debug("%s executed" % self.name, Debug.EVENTLOOP)

    def exit(self):
        pass

    """ PUBLIC FUNCTIONS"""

    def passEvent(self, event_type = None, pass_down = True, **kwargs):
        """
        Passes events from parent to child + executes events on current FFAction object
        """
        
        self.state.debug("%s passing through %s" % (event_type, self.name), Debug.EVENTLOOP)

        if pass_down:
            for a in self.actions:
                a.passEvent(event_type = event_type, **kwargs)

        self._executeEvent(event_type = event_type, **kwargs)

    def passEventToParent(self, event_type = None, **kwargs):
        self.state.debug("%s returning %s" % (event_type, self.name), Debug.EVENTLOOP)

        parent = self.parent_event
        if parent is not None:
            parent.passEvent(event_type, pass_down = False, origin = self, **kwargs)

    def hookAction(self, action):
        """
        Connects a new FFAction as a child of current FFAction
        """
        action.parent_event = self
        self.actions_dict[action.name] = action
        self.actions.append(action)
        self.state.debug("%s hooked to parent %s" % (action.name, self.name), Debug.EVENTLOOP)

    def addCallback(self, name, func):
        callback_funcs = self._callback_dict.get(name, [])
        if func not in callback_funcs:
            callback_funcs.append(func)
        self._callback_dict[name] = callback_funcs

    def getAction(self, action_id):
        if isinstance(action_id, str):
            return self.actions_dict.get(action_name,None)
        if isinstance(action_id, int):
            key = list(self.actions_dict)[action_id]
            return self.actions_dict.get(key,None)

    def getActionList(self):
        return list(self.actions_dict.values())

class FFStateAction(FFAction):
    """
    Passthrough FFAction from FFState that handles all 
    the event callbacks that are available from hou.State
    """
    def onEnter(self,kwargs):
        pass

    def onKeyTransitEvent(self,kwargs): 
        pass

    def onKey(self,kwargs):
        pass

    def onMouseEvent(self, kwargs):
        pass

    def onMouseWheelEvent(self, kwargs):
        pass
    
    def onInterrupt(self, kwargs):
        pass

    def onResume(self, kwargs):
        pass

    def onExit(self, kwargs):
        pass

    def onMouseDoubleClickEvent(self,kwargs):
        pass

    def onParmChanged(self,kwargs):
        pass

class ParmAction(FFAction):
    """
    Parameter changed callback
    """
    def __init__(self, **kwargs):
        self.parms_changed = {}
        self.parms = {}

        super().__init__(**kwargs)

        self.addCallback('onParmChanged', self._onParmChanged)

    def _onParmChanged(self,**kwargs):
        self.parms_changed = []
        parm_names = self.state.ui.parms_changed
        used_parms = []

        for ff_parm in self.parms.values():
            if ff_parm is not None:
                if ff_parm.name in parm_names:
                    just_set = ff_parm.just_set
                    ff_parm.update()
                    if just_set:
                        break
                    self.state.debug("%s changed" % ff_parm.name, Debug.PARMS)
                    used_parms.append(ff_parm.name)
        
        if len(used_parms) > 0:
            self.parms_changed = used_parms
            kwargs["parms_changed"] = used_parms
            self.onParmChanged(**kwargs)
        
    def onParmChanged(self,**kwargs):
        pass

    """ PUBLIC FUNCTIONS"""

    def hookParm(self, parm_path):
        node = self.state.node
        if node is not None:
            new_parm = FFParm(self.state, parm_path, node.parm(parm_path), is_hud = False)
            self.state.parms[parm_path] = new_parm
            self.parms[parm_path] = new_parm
            return new_parm
        else:
            self.state.parms[parm_path] = None
            self.parms[parm_path] = None
            return None

class ToggleAction(ParmAction):
    """
    Toggleable event = gets turned on when a keybind is pressed

    Access point functions are:
    start()
    refresh()
    finish()

    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.addCallback('onRefresh', self._refreshAction)
        self.addCallback('onFinish',self._finishAction)
        self.is_active = False
        self.toggle_manager = None

    def _startAction(self,**kwargs):
        if not self.is_active:
            self.is_active = True
            self.start()

    def _refreshAction(self,**kwargs):
        if self.is_active:
            self.refresh()

    def _finishAction(self,**kwargs):
        if self.is_active:
            self.finish()
            self.is_active = False

    def _toggleEvent(self,**kwargs):
        force = kwargs.get("force", None)
        
        if (self.is_active and force==None) or force==False:
            self.state.debug("Toggle %s off" % self.name, Debug.TOGGLE)
            self._finishAction()
        elif (not self.is_active and force==None) or force==True:
            self.state.debug("Toggle %s on" % self.name, Debug.TOGGLE)
            self._startAction()

        self.passEventToParent('onToggleChange')

    def _onExit(self,**kwargs):
        self._finishAction(**kwargs)
        super()._onExit(**kwargs)
        
    def passEvent(self, event_type = None, **kwargs):

        if not self.is_active:
            kwargs['pass_down'] = False
        super().passEvent(event_type, **kwargs)

    """ OVERLOAD FUNCTIONS"""

    def refresh(self):
        pass

    def finish(self):
        pass

    """ PUBLIC FUNCTIONS """

    def isActive(self):
        return self.is_active

class ToggleManager(FFAction):
    """
    Keeps track of child events and only allows one to be active at a time
    If use_default == True it uses 1st event in the list as the default
    """
    def __init__(self, use_default = False, **kwargs):
        super().__init__(**kwargs)
        self.use_default = use_default
        self.default_event = None
        self.addCallback('onToggleChange', self._onToggleChange)

        events = kwargs["events"]
        toggle_name = "toggle" + "_".join([x.name for x in events])

        for e in events:
            e.toggle_manager = self

    def _onEnter(self, **kwargs):
        super()._onEnter(**kwargs)
        if self.use_default:
            self.default_event = self.getAction(0)
            self.default_event.passEvent('onStart')

    def _onToggleChange(self,**kwargs):
        toggle_event = kwargs["origin"]
        
        is_active = toggle_event.isActive()
        if is_active:
            for a in self.getActionList():
                if a.name != toggle_event.name:
                    a.passEvent('onFinish')
        else:
            if self.default_event is not None:
                self.default_event.passEvent('onStart')

class KeyAction(ParmAction):
    """
    Base Key Event - onKeyDown calls start() if hotkey matches
    """
    def __init__(self, hotkey = None, **kwargs):

        super().__init__(**kwargs)
        self.hotkey = hotkey
        state.ui.addKey(hotkey)

        self.addCallback('onKeyDown',self._onKeyDown)

    def _onKeyDown(self,**kwargs):
        ui = self.state.ui
        if ui.key_pressed[self.hotkey]:
            self._startAction()

class KeyToggleAction(ToggleAction):
    """
    - Key toggle event - onKeyDown calls start() or finish()
    - allow_hold makes the onKeyUp call finish() if the user is holding the key

    """
    def __init__(self, hotkey = None, allow_hold = True, **kwargs):
        """
        Keyword Arguments:
            hotkey (str) - Keybind that toggles the action on/off
            allow_hold (bool) - If True, holding the keybind enables the tool temporarily
        """
        super().__init__(**kwargs)

        self.hotkey = hotkey
        self.allow_hold = allow_hold

        state = kwargs["state"]
        state.ui.addKey(hotkey)

        self.addCallback('onKeyDown', self._onKeyDown)

        if self.allow_hold:
            self.addCallback('onKeyUp', self._onKeyUp)

    def _onKeyDown(self,**kwargs):
        ui = self.state.ui
        if ui.key_pressed[self.hotkey]:
            self._toggleEvent()

    def _onKeyUp(self,**kwargs):
        ui = self.state.ui
        if self.is_active and ui.key_pressed[self.hotkey] and ( ui.key_hold_time[self.hotkey] > KEY_HOLD_TIME):
            self._toggleEvent()

class DrawableAction(ToggleAction):
    """
    Enables management of handles and drawables
    """
    def __init__(self, **kwargs):
        self.drawables = {}

        super().__init__(**kwargs)

        self.addCallback('onDraw', self._drawAction)
        self.addCallback('onParmChanged', self._drawAction)
    
    def _startAction(self,**kwargs):
        super()._startAction(**kwargs)
        for d in self.drawables.values():
            self.state.debug("%s enabled" % d.name, Debug.DRAW)
            d.enable(True)
            d.show(True)

    def _refreshAction(self,**kwargs):
        super()._refreshAction(**kwargs)
        if self.is_active:
            for d in self.drawables.values():
                d.update()
        
    def _finishAction(self,**kwargs):
        super()._finishAction(**kwargs)
        for d in self.drawables.values():
            self.state.debug("%s disabled" % d.name, Debug.DRAW)
            d.enable(False)
            d.show(False)

    def _drawAction(self,**kwargs):
        if self.is_active:
            self.draw()
            self.state.debug("Updating drawable xform", Debug.DRAW)
            for d in self.drawables.values():
                d.update()
            

    def _onExit(self,**kwargs):
        super()._onExit(**kwargs)
        self.state.log("Exiting")
        for d in self.drawables.values():
            del d

    """ PUBLIC FUNCTIONS"""

    def bindDrawable(self, geo = hou.drawablePrimitive.Sphere, name = "tool"):
        """
        Creates and binds a drawable object to the action.

        Keyword Arguments:
            geo (hou.Geometry) - Base Geometry for drawable
            name (str) - name id of the drawable - two drawables with the same name can't exist
        
        Returns:
            A FFDrawable object (subclass of hou.SimpleDrawable)
        """
        drawable = None
        if name not in self.drawables.keys():
            if self.state.scene_viewer is not None:
                drawable = FFDrawable(self.state, geo, name)
                self.drawables[name] = drawable
        else:
            drawable = self.drawables[name]
        
        return drawable

    """ OVERLOAD FUNCTIONS"""

    def draw(self):
        pass

class MenuParmAction(ToggleAction):
    def __init__(self, menu_parm = None, menu_id = 0, **kwargs):
        """
        Keyword Arguments:
            menu_parm (str) - name of the button strip/ ordered menu parameter on the node
            menu_id (int) - id of the menu tab used for the action
        """

        self.menu_parm = menu_parm
        self.menu_id = menu_id

        super().__init__(**kwargs)

    def _onEnter(self, **kwargs):
        super()._onEnter(**kwargs)
        parm = self.hookParm(self.menu_parm)

        if parm is not None:
            if parm.eval() == self.menu_id:
                self._startAction()

    def _onParmChanged(self,**kwargs):
        super()._onParmChanged(**kwargs)
        parms = self.parms_changed

        if self.menu_parm in parms:
            val = self.parms[self.menu_parm].eval()
            self.state.debug("%s button: %d" % (self.menu_parm,val), Debug.PARMS)
            if val == self.menu_id:
                self._toggleEvent(force=True)

    def _startAction(self, **kwargs):
        super()._startAction()
        self.state.debug("Menu %s action started" % self.name, Debug.PARMS)

        menu_parm = self.parms[self.menu_parm]
        if menu_parm is not None:
            menu_parm.set(self.menu_id)

class MouseWheelAction(ParmAction):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.addCallback('onMouseWheel', self._startAction)