# pyright: reportMissingImports=false
import hassapi as hass # type: ignore
import adbase as ad
import json
from datetime import datetime,timedelta
#from types import SimpleNamespace as Namespace
VER = "2"

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

  def updateStatus(self,status,attributes):
    if not self.status_entity is None:
      self.status_entity.set_state(state=status,attributes = attributes)
  
  #Get a item from an array or returns a default value
  def getConfigValue(self, array, item, default=None):
    if item in array:
      return array[item]
    else:
      return default

  def getInputByIndex(self, index):
    n=len(self.args["inputs"])
    for i, key in enumerate(self.args["inputs"].keys()):
      if i == index:
        return self.args["inputs"][key]
    raise IndexError("input index not found")

  def listen_sun(self,input,priority):
    self.debug("Listen Sun - Input: %s, Priority: %s",input,priority)
    self.args["inputs"][input]["sun_handle"]=self.listen_state(self.sun_callback, entity_id="sun.sun", attribute="all",priority=priority,input=input)
    self.debug("Register listen sun for input: %s, Priority: %s, Handle: %s",input,priority,self.args["inputs"][input]["sun_handle"])
    self.debug("Current Azimut: %s",self.entities.sun.sun.attributes.azimuth)
    value,active=self.calc_shade_position(input,self.entities.sun.sun.attributes.azimuth,self.entities.sun.sun.attributes.elevation)
    self.args["inputs"][input]["value"]=value
    self.args["inputs"][input]["active"]=active
    #self.debug("Current shade height: %s",self.value[priority])

  def cancel_listen_sun(self,input):
    self.debug("Cancel listen Sun - Input: %s",input)
    self.cancel_listen_state(self.args["inputs"][input]["sun_handle"])
    self.debug("Unregister listen sun for input: %s, Handle: %s",input,self.args["inputs"][input]["sun_handle"])
    self.args["inputs"][input]["sun_handle"]=None

  ### get auto_on
  def isAutoOn(self,input):
    self.debug("isAutoOn: %s", input)
    if "auto_on" in self.args["inputs"][input] and isinstance(self.args["inputs"][input]["auto_on"],int):
        return self.args["inputs"][input]["auto_on"]
        self.debug("Auto on in %s s", self.args["inputs"][input]["auto_on"])
    else:
        return False
    
  ### get auto_off
  def isAutoOff(self,input):
    self.debug("isAutoOff: %s", input)
    if "auto_off" in self.args["inputs"][input] and isinstance(self.args["inputs"][input]["auto_off"],int):
        return self.args["inputs"][input]["auto_off"]
        self.debug("Auto off in %s s", self.args["inputs"][input]["auto_off"])
    else:
        return False
    

  def initialize(self):
    self.log("HACS_Priority_Switch v" + VER)
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
    self.lastValue=None
    priority=0
    self.deadtime = datetime.now()
    self.automation_block = datetime.now()
    
    if self.args["enabled"]:
      self.log("Priority Switch enabled", level="INFO")
      if not self.entity_exists(self.args["output"]) and not self.args["output_sequence"]:
        self.debug("No valid output defined: %s",self.args["output"])
        return
      if "output_sequence" in self.args and self.args["output_sequence"]:
        self.output_sequence = self.args["output_sequence"]
      for entity in self.args["inputs"]:
          # save entity name
          self.args["inputs"][entity]["name"]=entity
          # Save priority
          self.args["inputs"][entity]["priority"]=priority
          #self.debug(entity)
          #Add Control
          #self.priorityName.append(entity)
          self.debug("Input: %s",entity)
          ### Check if Control is using templating
          if "control_use_template" in self.args["inputs"][entity] and bool(self.args["inputs"][entity]["control_use_template"]) is True:
              self.debug("Input '" + entity + "' is using Control template")
              self.debug("Input '" + entity + "' is using Control Entities: " + str(self.args["inputs"][entity]["control_template_entities"]))
              self.debug("Input '" + entity + "' is using Control Template: " + str(self.args["inputs"][entity]["control_template"]))
              res=self.render_template(str(self.args["inputs"][entity]["control_template"]))
              self.debug("Input '" + entity + "' is Control Template renders to: " + str(res))
              self.args["inputs"][entity]["active"]=res
              for ent in self.args["inputs"][entity]["control_template_entities"]:
                #self.debug(ent)
                self.listen_state(self.callback, entity_id=ent,priority=priority,input=entity,control=True)
          ### If control is  a static value save the entity
          elif not self.onoff2bool(self.args["inputs"][entity]["control"]) is None:
              self.debug("Input '" + entity + "' is static " + str(self.args["inputs"][entity]["control"]))
              self.args["inputs"][entity]["active"]=self.onoff2bool(self.args["inputs"][entity]["control"])
              self.args["inputs"][entity]["control_static"]=True
          ### Control is  not a static value
          else:
              ### If entity exists register callback and get current value
              if self.entity_exists(self.args["inputs"][entity]["control"]):
                  self.listen_state(self.callback, entity_id=self.args["inputs"][entity]["control"],priority=priority,input=entity,control=True)
                  self.args["inputs"][entity]["active"]=self.onoff2bool(self.get_state(entity_id=self.args["inputs"][entity]["control"]))
                  self.args["inputs"][entity]["control_static"]=False
              else:
                  self.debug("'" + self.args["inputs"][entity]["control"] + "' is an invalid entity")
                  self.args["inputs"][entity]["active"]=False

          ### Check if Shade mode
          #self.debug("auto_shade: %s","auto_shade" in self.args["inputs"][entity])
          if "auto_shade" in self.args["inputs"][entity] and self.args["inputs"][entity]["auto_shade"]: # auto shade
            self.args["inputs"][entity]["facadeentry"]=self.args["inputs"][entity]["buildingDeviation"] + self.args["inputs"][entity]["offset_entry"] if int(self.args["inputs"][entity]["offset_entry"]) else -90
            self.args["inputs"][entity]["facadeexit"]=self.args["inputs"][entity]["buildingDeviation"] + self.args["inputs"][entity]["offset_exit"] if int(self.args["inputs"][entity]["offset_entry"]) else 90
            # in Shade mode value is considered static
            self.args["inputs"][entity]["dynamic"]=False
            if self.args["inputs"][entity]["active"]:
              self.listen_sun(entity,priority)
            #self.listen_state(self.callback, entity_id=self.args["inputs"][entity]["control"],priority=priority,control=True)
            #self.debug("Args: %s", self.args["inputs"][entity])
          ### add Value, check if is numeric or not an existing entity
          elif isinstance(self.args["inputs"][entity]["value"],int) or isinstance(self.args["inputs"][entity]["value"],float) or not self.entity_exists(self.args["inputs"][entity]["value"]):
              if self.args["inputs"][entity]["value"]==None or str(self.args["inputs"][entity]["value"]).lower()=='none':
                self.debug("None Value found")
                self.args["inputs"][entity]["value"]=None
                self.args["inputs"][entity]["dynamic"]=False
              else:
                self.debug("Input '" + entity + "' is using static value: " + str(self.args["inputs"][entity]["value"]))
                self.args["inputs"][entity]["value"]=self.args["inputs"][entity]["value"]
                self.args["inputs"][entity]["dynamic"]=False
          else:
              self.listen_state(self.callback, entity_id=self.args["inputs"][entity]["value"],priority=priority,input=entity,control=False)
              self.args["inputs"][entity]["value"]=self.args["inputs"][entity]["value"]
              self.args["inputs"][entity]["dynamic"]=True
          self.args["inputs"][entity]["auto_on_running"]=None
          self.args["inputs"][entity]["auto_off_running"]=None
          priority=priority+1
          self.debug("Input data: %s",self.args["inputs"][entity])
          
              
      # self.debug("Control : %s", self.control)
      # self.debug("Control Static: %s", self.control_static)
      # self.debug("Value: %s", self.value)
      # self.debug("Value Static: %s", self.value_static)
      # self.debug("Priority names: %s", self.priorityName)
      # self.maxPriority=len(self.priorityName)-1
      # self.debug("Max Priority: %s", self.maxPriority)
      # self.debug("Output Squence: %s", self.output_sequence)
      # self.debug("Auto On: %s", self.auto_on)
      # self.debug("Auto Off: %s", self.auto_off)
      
    if "status_entity" in self.args and self.args["status_entity"]:
      self.status_entity=self.get_entity(self.args["status_entity"])
      self.updateStatus("init",{"current":"init","value": None,"device":None,"timestamp":None})
    else:
      self.status_entity = None
    if "initial_run" in self.args and self.args["initial_run"]:
      self.debug("Initial run requested")
      self.run('on',0)
      self.debug(self.name)
#      self.status_entity = self.add("priorityswitch." + self.name,state="init", attributes={"last_run": datetime.now().time})
    if "detect_manual" in self.args and self.args["detect_manual"]:
      self.ad = self.get_ad_api()
      #self.status_entity = self.add("priorityswitch." + self.name,state="init", attributes={"last_run": "1234"})
      self.ad.listen_event(self.event_callback,"state_changed",entity_id = self.args["output"])

    self.debug("End Init")    

  def event_callback(self, event_name, data, kwargs):
    self.debug("Deadtime: %s", self.deadtime)
    self.debug("Current Time: %s", datetime.now())
    self.debug("Event Name: %s, Data: %s, kwargs: %s",event_name, data, kwargs)
    #self.debug("Event Data: %s", data)
    #self.debug("Event Args: %s", kwargs)
    if datetime.now() < self.deadtime:
      self.debug("Event Mode: Automation")
    else:
      self.debug("Event Mode: External")
      self.automation_block =  datetime.now() + timedelta(minutes=self.args["automation_pause"])
      self.debug("All Automations paused till: %s", self.automation_block)
      self.updateStatus("manual override",{"blocked till":self.automation_block})
      self.run_in(self.unblock_callback, timedelta(minutes=self.args["automation_pause"]).total_seconds(), event_name=event_name, data=data, kwargs=kwargs)


  def unblock_callback(self, kwargs):
    self.debug("Unblock Callback, Now: %s, Deadtime: %s, Event Name: %s, Data: %s, kwargs: %s",datetime.now(),self.deadtime,kwargs["event_name"],kwargs["data"],kwargs)
    #if datetime.now()>= self.deadtime:
    self.updateStatus("unblocking",{"blocked till":""})
    self.run("on",0)
    


  def findHighestActivPriority(self):
    found=False
    priority=None
    #self.debug("Inputs: %s",self.args["inputs"])
    for input in self.args["inputs"]:
          # save entity name
    #      self.args["inputs"][entity]["name"]=entity
      #self.debug("Input: %s", input)
      if self.args["inputs"][input]["active"]:
        found=True
        priority=input

    if found:
      self.debug("Highest Active Priority: %s", priority)
      return priority
    else:
      self.debug("All Controls are off!")
      return None


  def sendValue(self, value, priority):
    self.debug("Value to send: %s, Priority: %s", value, priority)
    device, entity = self.split_entity(self.args["output"])
    self.debug("Old Value: %s, New Value: %s, Device: %s, Entity: %s", self.lastValue, value, device, entity)
    #self.debug("New Value: %s", value)
    #self.debug("Device: %s, Entity: %s", device,entity)
    if "detect_manual" in self.args and self.args["detect_manual"]:
    #if self.args["detect_manual"]:
      self.debug("Set Deadtime: %s",datetime.now() + timedelta(seconds=self.args["deadtime"]))
      self.deadtime = datetime.now() + timedelta(seconds=self.args["deadtime"])

    if self.lastValue==value:
      if self.get_state(entity_id=self.args["output"]) == value:
        self.debug("Old and new value are the same, no update needed!")
        return
      self.debug("External value does not match desired state. Sending update!")
    #if self.output_sequence:
    if hasattr(self, "output_sequence"):
      #value = 30
      #teststr = '{"light/turn_on": {"entity_id": "light.office", "brightness": "%VALUE%"}}'
      #teststr=self.args["output_sequence"]
      #teststr2 = teststr.replace("%VALUE%",str(value))
      #testobj = json.loads(teststr2, object_hook=lambda d: Namespace(**d))
      sequence_str = self.output_sequence.replace("%VALUE%",str(value))
      sequence = json.loads(sequence_str)
      #self.log(teststr)
      #self.log(teststr2)
      #self.log(testobj)
      handle = self.run_sequence([sequence])
      self.debug("Use Sequence")

    elif device=="input_number":
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
    self.updateStatus(priority,{"value":value,"timestamp":datetime.now(),"device":device, "current":value})

  def callback(self, entity, attribute, old, new, kwargs):
    self.debug("Callback Priority: %s, Priority: %s, Attributes: %s, Old: %s, New: %s, kwargs: %s",entity,kwargs["priority"], attribute, old, new, kwargs)
    input=self.args["inputs"][kwargs["input"]]
    if "control_use_template" in self.args["inputs"][kwargs["input"]] and bool(self.args["inputs"][kwargs["input"]]["control_use_template"]) is True:
      input["active"]=self.render_template(self.args["inputs"][kwargs["input"]]["control_template"])
      self.debug("Template Control, Rendering Template: " + str(new))
    elif input["control_static"] == False:
      self.debug("Dynamic Control: " + str(self.get_state(entity_id=self.args["inputs"][kwargs["input"]]["control"])))
      input["active"]=self.onoff2bool(self.get_state(entity_id=self.args["inputs"][kwargs["input"]]["control"]))
    #else:
    #  input["active"]=self.onoff2bool(new)
    self.debug("Input data: %s", input)
    if "auto_shade" in input:
      if new=="on":
        self.debug("register sun")
        self.listen_sun(kwargs["input"],kwargs["priority"])
      else:
        self.debug("unregister sun")
        self.cancel_listen_sun(kwargs["input"])
    if datetime.now() < self.automation_block:
      self.debug("Automation blocked till: %s", self.automation_block)
    else:
      self.run(new,kwargs["priority"])



  def run(self,new,priority):
    targetPriority = self.findHighestActivPriority()
    self.debug("Run: Target Priority: %s, New: %s, Priority %s", targetPriority,new,priority)
    #value=self.getValueFromPriority(targetPriority)
    if self.args["inputs"][targetPriority]["dynamic"]:
      value=self.get_state(self.args["inputs"][targetPriority]["value"])
      self.debug("using dynamic value: %s from %s",value,self.args["inputs"][targetPriority]["value"])
    else:
      value=self.args["inputs"][targetPriority]["value"]
      if value==None:
        self.debug("Static None Value found, not sending a value!")
        return
      self.debug("Send static value: %s",value)
      #priority=kwargs["priority"]
    
    self.debug("Send Value: %s", str(value))
    self.sendValue(value, targetPriority)
    ### if new == on and autooff
    #if new == "on" and not self.auto_off[priority] is None:
    input=self.getInputByIndex(priority)
    inputname=input["name"]
    if new == "on" and not self.isAutoOff(input["name"]) is False:
        self.debug("Trigger auto off")
        #if not self.auto_off_running[priority] is None and self.timer_running(self.auto_off_running[priority]):
        if not self.args["inputs"][input["name"]]["auto_off_running"] is None and self.timer_running(self.args["inputs"][input["name"]]["auto_off_running"]):
            self.cancel_timer(self.args["inputs"][input["name"]]["auto_off_running"])
            self.args["inputs"][input["name"]]["auto_off_running"]=None
            self.debug("Cancel previous auto off timer")
        self.args["inputs"][input["name"]]["auto_off_running"]=self.run_in(self.auto_callback,self.isAutoOff(input["name"]),priority=priority,switch="off")
        self.debug("Timer handle: %s", self.args["inputs"][input["name"]]["auto_off_running"])
        self.updateStatus(input["name"],{"auto_off":True,"auto_timer":datetime.now() + timedelta(seconds=self.isAutoOff(input["name"]))})
    if new == "off" and not self.isAutoOn(input["name"]) is False:
        if not self.args["inputs"][input["name"]]["auto_on_running"] is None and self.timer_running(self.args["inputs"][input["name"]]["auto_on_running"]):
            self.cancel_timer(self.args["inputs"][input["name"]]["auto_on_running"])
            self.args["inputs"][input["name"]]["auto_on_running"]=None
            self.debug("Cancel previous auto on timer")
        self.debug("Trigger auto on")
        self.args["inputs"][input["name"]]["auto_on_running"]=self.run_in(self.auto_callback,self.isAutoOn(input["name"]),priority=priority,switch="on")
        self.debug("Timer handle: %s", self.args["inputs"][input["name"]]["auto_on_running"])
        self.updateStatus(input["name"],{"auto_on":True,"auto_timer":datetime.now() + timedelta(seconds=self.isAutoOn(input["name"]))})
#    else:
#        self.debug("No auto reset")
    if new == "off" and not self.args["inputs"][input["name"]]["auto_off_running"] is None:
        self.cancel_timer(self.args["inputs"][input["name"]]["auto_off_running"])
        self.args["inputs"][input["name"]]["auto_off_running"]=None
        self.debug("Cancel previous auto off timer")
        self.updateStatus(input["name"],{"auto_off":False,"auto_timer":""})
    if new == "on" and not self.args["inputs"][input["name"]]["auto_on_running"] is None:
        self.cancel_timer(self.args["inputs"][input["name"]]["auto_on_running"])
        self.args["inputs"][input["name"]]["auto_on_running"]=None
        self.debug("Cancel previous auto on timer")
        self.updateStatus(input["name"],{"auto_on":False,"auto_timer":""})


  def auto_callback(self,kwargs):
      self.debug("Auto Callback triggered for Priority %s",kwargs["priority"])
      if kwargs["switch"]=="off":
          self.debug("Switching %s off!",self.control_static[kwargs["priority"]])
          self.turn_off(self.control_static[kwargs["priority"]])
          self.auto_off_running[kwargs["priority"]]=None
          self.updateStatus(self.priorityName[kwargs["priority"]],{"auto_off":False,"auto_timer":""})
      elif kwargs["switch"]=="on":
          self.debug("Switching %s on!",self.control_static[kwargs["priority"]])
          self.turn_on(self.control_static[kwargs["priority"]])
          self.auto_on_running[kwargs["priority"]]=None
          self.updateStatus(self.priorityName[kwargs["priority"]],{"auto_on":False,"auto_timer":""})

  def sun_callback(self, entity, attribute, old, new, kwargs):
    self.debug("Sun Callback - Input:" + kwargs["input"])
    self.debug("Entity: %s, Attributes: %s, Old: %s, New: %s, kwargs: %s", entity, attribute, old, new, kwargs)
    #self.debug("Attribute:" + attribute)
    #self.debug("Old:" + str(old))
    #self.debug("New:" + str(new))
    #self.debug("kwargs: %s", str(kwargs))
    value, active = self.calc_shade_position(kwargs["input"],new["attributes"]["azimuth"],new["attributes"]["elevation"])
    self.debug("Calculated Shade position: %s, Active: %s",value,active)
    #self.value[kwargs["priority"]]=value
    self.args["inputs"][kwargs["input"]]["value"]=value
    self.args["inputs"][kwargs["input"]]["active"]=active
    if datetime.now() < self.automation_block:
      self.debug("Automation blocked till: %s", self.automation_block)
    else:
      self.run(new,kwargs["priority"])

  def calc_shade_position(self,input,azimuth,elevation):
    #Azimuth needs to be larger than helper or smaller than facadeexit
    self.debug("Calc_shade_Position: Input: %s, Azimuth: %s, Elevation %s",input,azimuth,elevation)
    sun=False
    value=0
    if elevation<=0:
      sun=False
    elif self.args["inputs"][input]["facadeentry"] < 0:
      helper=self.args["inputs"][input]["facadeentry"]+360
      if azimuth>=helper or azimuth<=self.args["inputs"][input]["facadeexit"]:
        sun=True
      else:
        sun=False
    #Azimuth needs to be smaller than helper or larger than facadeentry
    elif self.args["inputs"][input]["facadeexit"]>360:
      helper=self.args["inputs"][input]["facadeexit"]-360
      if azimuth<=helper or azimuth >= self.args["inputs"][input]["facadeentry"]:
        sun=True
      else:
        sun=False
    #Check if Azimuth is between facadeentry and facadeexit
    else:
      if azimuth>=self.args["inputs"][input]["facadeentry"] and azimuth<=self.args["inputs"][input]["facadeexit"]:
        sun=True
      else:
        sun=False
    #self.debug("Sun: %s",sun)
    #in sun
    if sun:
      if elevation <= 10:
        value=self.args["inputs"][input]["elevation_lt10"] if int(self.args["inputs"][input]["elevation_lt10"]) else 100
      elif elevation <= 20:
        value=self.args["inputs"][input]["elevation_10to20"] if int(self.args["inputs"][input]["elevation_10to20"]) else 100
      elif elevation <= 30:
        value=self.args["inputs"][input]["elevation_20to30"] if int(self.args["inputs"][input]["elevation_20to30"]) else 100
      elif elevation <= 40:
        value=self.args["inputs"][input]["elevation_30to40"] if int(self.args["inputs"][input]["elevation_30to40"]) else 100
      elif elevation <= 50:
        value=self.args["inputs"][input]["elevation_40to50"] if int(self.args["inputs"][input]["elevation_40to50"]) else 100
      elif elevation <= 60:
        value=self.args["inputs"][input]["elevation_50to60"] if int(self.args["inputs"][input]["elevation_50to60"]) else 100
      else:
        value=self.args["inputs"][input]["elevation_gt60"] if int(self.args["inputs"][input]["elevation_gt60"]) else 100
    #in shadow
    elif self.getConfigValue(self.args["inputs"][input],"setIfInShadow",False):
      value = self.getConfigValue(self.args["inputs"][input],"shadow",0)
      self.debug("Set in Shadow: %s",value)
      sun=True
    self.debug("Set height to: %s",value)
    return value, sun

  def auto_shadow_callback (self,kwargs):
    self.debug("auto_shadow Callback Priority:" )
    self.debug("Priority: " + str(kwargs))
    self.debug("Attribute:" )