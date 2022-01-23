# pylance: disable=import-error
import hassapi as hass

class PrioritySwitch(hass.Hass):
  def onoff2bool(self,value):
    if str(value).lower()=='on':
      return True
    elif str(value).lower()=='off':
      return False
    else:
      return None

  def debug(self,text,*args):
    if self.debuging:
        if len(args)>0:
            self.log(text,*args)
        else:
            self.log(text)

  def initialize(self):
    #if "loglevel" in self.args and self.args["loglevel"].upper() in ["INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG", "NOTSET"]:
    if "debug" in self.args and self.args["debug"]:
        #self.set_log_level(self.args["loglevel"].upper())
        #self.log("Set Loglevel to %s", self.args["loglevel"].upper())
        self.log("Debuging enabled!")
        self.debuging=True
    else:
        #self.log("No custom Log level defined, set to INFO")
        #self.set_log_level("INFO")
        self.debuging=False
    self.debug(self.args)
#    self.log("Test INFO", level="INFO")
#    self.log("Test WARNING", level="WARNING")
#    self.log("Test ERROR", level="ERROR")
#    self.log("Test DEBUG", level="DEBUG")
    self.control=[]
    self.control_static=[]
    self.value=[]
    self.value_static=[]
    self.priorityName=[]
    self.auto_off=[]
    self.auto_off_running=[]
    self.auto_on=[]
    self.auto_on_running=[]
    self.lastValue=None
    priority=0
    if self.args["enabled"]:
      self.log("Priority Switch enabled", level="INFO")
      if not self.entity_exists(self.args["output"]):
        self.debug("No valid output defined: %s",self.args["output"])
        return
      for entity in self.args["inputs"]:
          #Add Control
          self.priorityName.append(entity)
          if not self.onoff2bool(self.args["inputs"][entity]["control"]) is None:
              self.debug("Input '" + entity + "' is static " + str(self.args["inputs"][entity]["control"]))
              self.control_static.append(self.onoff2bool(self.args["inputs"][entity]["control"]))
              self.control.append(True)
          else:
              if self.entity_exists(self.args["inputs"][entity]["control"]):
                  self.listen_state(self.callback, entity_id=self.args["inputs"][entity]["control"],priority=priority,control=True)
                  self.control_static.append(self.args["inputs"][entity]["control"])
                  self.control.append(False)
              else:
                  self.debug("'" + self.args["inputs"][entity]["control"] + "' is an invalid entity")
                  self.control_static.append(False)
                  self.control.append(True)
          #add Value
          if isinstance(self.args["inputs"][entity]["value"],int) or isinstance(self.args["inputs"][entity]["value"],float) or not self.entity_exists(self.args["inputs"][entity]["value"]):
              if self.args["inputs"][entity]["value"]==None or str(self.args["inputs"][entity]["value"]).lower()=='none':
                self.debug("None Value found")
                self.value.append(None)
                self.value_static.append(True)          
              else:
                self.debug("Input '" + entity + "' is using static value: " + str(self.args["inputs"][entity]["value"]))
                self.value.append(self.args["inputs"][entity]["value"])
                self.value_static.append(True)          
          else:
              self.listen_state(self.callback, entity_id=self.args["inputs"][entity]["value"],priority=priority,control=False)
              self.value.append(self.args["inputs"][entity]["value"])
              self.value_static.append(False)
          #add auto off
          if "auto_off" in self.args["inputs"][entity] and isinstance(self.args["inputs"][entity]["auto_off"],int):
              self.auto_off.append(self.args["inputs"][entity]["auto_off"])
              self.debug("Auto off in %s s", self.args["inputs"][entity]["auto_off"])
          else:
              self.auto_off.append(None)
          self.auto_off_running.append(None)
          #add auto on
          if "auto_on" in self.args["inputs"][entity] and isinstance(self.args["inputs"][entity]["auto_on"],int):
              self.auto_on.append(self.args["inputs"][entity]["auto_on"])
              self.debug("Auto on in %s s", self.args["inputs"][entity]["auto_on"])
          else:
              self.auto_on.append(None)
          self.auto_on_running.append(None)
          priority=priority+1
              
      self.debug("Control : %s", self.control)
      self.debug("Control Static: %s", self.control_static)
      self.debug("Value: %s", self.value)
      self.debug("Value Static: %s", self.value_static)
      self.debug("Priority names: %s", self.priorityName)
      self.maxPriority=len(self.priorityName)-1
      self.debug("Max Priority: %s", self.maxPriority)
    self.debug("End Init")


  def findHighestActivPriority(self):
    x=self.maxPriority
    found=False
    while x >= 0:
        self.debug("x: " + str(x))
        self.debug("Static: " + str(self.control[x]))
        if self.control[x]:
          self.debug("Control Static Value: " + self.priorityName[x] + " = " + str(self.control_static[x]))
          if self.control_static[x]:
            self.debug("true")
            found=True
            break
        else:
          self.debug("Dynamic Value: "  + self.priorityName[x] + " = " + self.get_state(entity_id=self.control_static[x]))
          if self.onoff2bool(self.get_state(entity_id=self.control_static[x])):
            self.debug("True")
            found=True
            break
        x -=1
    if found:
      self.debug("Highest Active Priority: %s", x)
      return x
    else:
      self.debug("All Controls are off!")
      return None
  def getValueFromPriority(self,priority):
    #use Static Value
    if self.value_static[priority]:
      self.debug("Static Value: %s", self.value[priority])
      return self.value[priority]
    else:
      self.debug("Dynamic Value: %s", self.get_state(entity_id=self.value[priority]))
      return self.get_state(entity_id=self.value[priority])

  def sendValue(self, value):
    self.debug("Value to send: %s", value)
    device, entity = self.split_entity(self.args["output"])
    self.debug("Old Value: %s", self.lastValue)
    self.debug("New Value: %s", value)
    self.debug("Device: %s, Entity: %s", device,entity)
    if self.lastValue==value:
      self.debug("Old and new value are the same, no update needed!")
      return
    if device=="input_number":
      self.debug("Use set_number service")
      self.set_value(self.args["output"], value)
    elif device=="input_text":
      self.debug("Use set_textvalue service")
      #self.set_textvalue("input_text.text1", "hello world")
    elif device=="input_select":
      self.debug("Use select_option service")
      self.select_option(self.args["output"], value)
    elif device=="select":
      self.debug("Use select service")
      #self.set_state(self.args["output"],state=value)
      self.call_service("select/select_option", entity_id = self.args["output"], option = value)
    elif device=="switch" or device=="scene" or device=="light":
      self.debug("Use turn_on service")
      #self.turn_on("light.office_1", color_name = "green")
    elif device=="fan":
      self.debug("Use fan.set_preset_mode")
      if value.lower()=="off":
        self.debug("Call fan.turn_off")
        self.call_service("fan/turn_off", entity_id = self.args["output"])
      else:
        self.debug("Call fan.set_preset_mode with %s",value)
        self.call_service("fan/set_preset_mode", entity_id = self.args["output"], preset_mode = value)
    else:
      self.log("Unknown device: %s", device, level="INFO")
    self.lastValue=value

  def callback(self, entity, attribute, old, new, kwargs):
    self.debug("Callback Priority:" + entity)
    self.debug("Priority: " + str(kwargs["priority"]))
    self.debug("Attribute:" + attribute)
    self.debug("Old:" + old)
    self.debug("New:" + new)
    self.debug("Control: %s", kwargs["control"])
    targetPriority = self.findHighestActivPriority()
    self.debug("Target Priority: %s", targetPriority)
    value=self.getValueFromPriority(targetPriority)
    if value==None:
      self.debug("Static None Value found, not sending a value!")
      return
    priority=kwargs["priority"]
    self.sendValue(value)
    if new == "on" and not self.auto_off[priority] is None:
        self.debug("Trigger auto off")
        if not self.auto_off_running[priority] is None and self.timer_running(self.auto_off_running[priority]):
            self.cancel_timer(self.auto_off_running[priority])
            self.auto_off_running[priority]=None
            self.debug("Cancel previous auto off timer")
        self.auto_off_running[priority]=self.run_in(self.auto_callback,self.auto_off[priority],priority=priority,switch="off")
        self.debug("Timer handle: %s", self.auto_off_running[priority])
    if new == "off" and not self.auto_on[priority] is None:
        if not self.auto_on_running[priority] is None and self.timer_running(self.auto_on_running[priority]):
            self.cancel_timer(self.auto_on_running[priority])
            self.auto_on_running[priority]=None
            self.debug("Cancel previous auto on timer")
        self.debug("Trigger auto on")
        self.auto_on_running[priority]=self.run_in(self.auto_callback,self.auto_on[priority],priority=priority,switch="on")
        self.debug("Timer handle: %s", self.auto_on_running[priority])
#    else:
#        self.debug("No auto reset")
    if new == "off" and not self.auto_off_running[priority] is None:
        self.cancel_timer(self.auto_off_running[priority])
        self.auto_off_running[priority]=None
        self.debug("Cancel previous auto off timer")
    if new == "on" and not self.auto_on_running[priority] is None:
        self.cancel_timer(self.auto_on_running[priority])
        self.auto_on_running[priority]=None
        self.debug("Cancel previous auto on timer")

  def auto_callback(self,kwargs):
      self.debug("Auto Callback triggered for Priority %s",kwargs["priority"])
      if kwargs["switch"]=="off":
          self.debug("Switching %s off!",self.control_static[kwargs["priority"]])
          self.turn_off(self.control_static[kwargs["priority"]])
          self.auto_off_running[kwargs["priority"]]=None
      elif kwargs["switch"]=="on":
          self.debug("Switching %s on!",self.control_static[kwargs["priority"]])
          self.turn_on(self.control_static[kwargs["priority"]])
          self.auto_on_running[kwargs["priority"]]=None
