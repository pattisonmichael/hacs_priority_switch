# [![hacs_priority_switch](https://socialify.git.ci/pattisonmichael/hacs_priority_switch/image?description=1&font=Source%20Code%20Pro&forks=1&language=1&name=1&owner=1&pattern=Plus&stargazers=1&theme=Light)](https://github.com/pattisonmichael/hacs_priority_switch)
# hacs_priority_switch
Priority switching of entities according to different inputs
 as [AppDaemon](https://github.com/home-assistant/appdaemon) app.  

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

unlimited **priorities** per entity
different entity **types**
each priority can be **switched**
values can be **dynamic** from entities or **static** from configuration
Auto reset for input **on/off** with timer
**templating output** ToDo
**init run** ToDo

## Getting Started

## Installation

Use [HACS](https://github.com/hacs/integration) or [download](https://github.com/pattisonmichael/hacs_priority_switch) the `priority_switch` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `priorityswitch` module.

### Example App Configuration

Add your configuration to appdaemon/apps/apps.yaml, an example with two rooms is below.

```yaml

venting:
  module: priority_switch
  class: PrioritySwitch
  inputs:
  # Any amount of inputs can be configured, names are not important, only order
    default:
      # This will be static on with a static value of 'Medium'
      # It is the lowest Priority
      control: 'On'
      value: 'Medium'
    priority1:
      # This will be static on with a dynamic value from the entity in the 'value' section
      control: 'On'
      value: input_select.venting_auto_mode
    priority2:
      # This will be dynamically controlled by the entitiy in 'control' and the value from the entity 'value' will be used
      # This will automatically switch off after 600s when switched on
      # This is the highest priority
      control: input_boolean.venting_manual
      value: input_select.venting_manual_mode
      auto_off: 600
      #auto_on: 100
      # Entity to send output values to
  output: select.select_fan_mode
  # Enable this automation
  enabled: True
  # Enable debug logging
  debug: True
  
bedroom_shutter:
  module: priority_switch
  class: PrioritySwitch
  inputs:
    open:
      control: 'On'
      value: '100'
      
    shade:
      control: input_boolean.cover_shade_bedroom
      value:
      auto_shade: True
      azimut: 78
      elevation: 25
      buildingDeviation: 290
      offset_entry: -60
      offset_exit: 50
      updateInterval: 5
      sun_entity: sun.sun
      setIfInShadow: False
      shadow: 0
      elevation_lt10: 0
      elevation_10to20: 0
      elevation_20to30: 20
      elevation_30to40: 40
      elevation_40to50: 60
      elevation_50to60: 80
      elevation_gt60: 80
    rain:
      control: input_boolean.cover_alert_rain
      value: '20'
    storm:
      control: input_boolean.cover_alert_storm
      value: '0'
    night:
      control: input_boolean.shutters_closed_for_night
      value: 0
    frost:
      control: input_boolean.cover_alert_frost
      value: '10'
    sleepmode:
      control: switch.sleepmode_bedroom
      value: '0'
     window_open:
       control: binary_sensor.window_tilt_bed
       value: '50'
    manual:
      control: input_boolean.manual
      value: input_number.manual_value
      auto_off: 120
    alarm:
      control: input_boolean.cover_alert_alarm
      value: '100'

  output: cover.bed
  output_sequence: '{"cover/set_cover_position": {"entity_id": "cover.bed", "position": "%VALUE%"}}'
  status_entity: input_text.cover_status_bed
  enabled: True
  deadtime: 30
  detect_manual: True
  automation_pause: 120
  initial_run: True
  debug: False
```

## Configuration Options
### General
key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | priority_switch | The module name of the app.
`class` | False | string | PrioritySwitch | The name of the Class.
`inputs` | False | list | | The "inputs" used for this automation. See below for details.
`output` | False | string | | entity that will receive the value.
`output_sequence` | True | string || Use an Apdaemon sequence to output the switch result. `%VALUE%` can be used as a placeholder and will be replaced with the calculated output value.  `'{"cover/set_cover_position": {"entity_id": "cover.bed", "position": "%VALUE%"}}'`
`status_entity` | True | entity || The name of an entity that will receive additional status attributes like current active input
`detect_manual` | True | boolean | false | Try to detect manual override of the entity we are managing. Useful for cover controls.
`deadtime` | True | int || Deadtime in seconds when output is triggered. The purpose is to disable Manual override detection for a few seconds while the automation is changing the setting. Sample would be a cover that changes values a few time while moving and should be ignored. But if the user is manually moving the cover any other time we want to detect that.
`automation_pause` | True | int | 120 | How long we will pause all automations for in minutes once we detect an outside change
`initial_run` | True | boolean | True | Should we do a run when the app is loaded (`True`) or wait for the first trigger event (`False`).
`enabled` | False | bool | | `True` to enable this switch.
`debug` | True | bool | False | `True` to enable debug logging

#### Inputs
Each swtich can have multiple "Inputs" to determin the output.
Priority of the different inputs is determined by the order where the first Input has the lowest priority and the last one the highest.
In the above shutter example the Alarm Input would always override everything.

key | options | type | default | description
-- | -- | -- | -- | --
`priority_label` | False | list | | Not important for the functionality, only order matters. Top has lowest priority. This is just a name and not a parameter. The name will also be used for the Status Entity to track the current mode.
`control` | False | string | | Either `'on'`, `'off'` or a boolean switch entity name
`value` | False | string | | Either a valid HA Entity or a static value to be send to the output.
`auto_off` | True | int | | Amount of seconds after a control entity is switched off again after it was switched on.
`auto_on` | True | int | | Amount of seconds after a control entity is switched on again after it was switched off.
 | Special case to calculate cover position for shade | 

 key | type | default | description
-- | -- | -- | --
`value` | string | | Should be empty in case of auto shade
`auto_shade` | boolean | False | Set to `True` to enable shadow calculations
`azimut` | int | | The Azimut when the cover will be in sun
`elevation` | int | | The Elevation when the cover will be in sun
`buildingDeviation` | int | | The deviation of the building (you can think of it like which side of the building)
`offset_entry` | int | | An offset for when we conside the need to have shadow (-90 to 0) and the sun is entering the window.
`offset_exit` | int | | An offset for when we conside the need to have shadow (0 to 90) and the sun is leaving the window.
`updateInterval` | int | | How often should we recalculate in minutes. Have this too small will make the cover move constantly!
`sun_entity` | string | | The entity we use to track the sun. Usually `sun.sun`
`setIfInShadow` | boolean | `False` | Inverts the function, only triggers if we consider the window to be in the shadow
`shadow` | int | | Position to send when in Shadow (0)
`elevation_lt10` | int | | Position to send when elevation < 10 (0)
`elevation_10to20` | int | | Position to send when in elevation between 10 and 20 (0)
`elevation_20to30` | int | | Position to send when in elevation between 20 and 30 (0)
`elevation_30to40` | int | | Position to send when in elevation between 30 and 40 (0)
`elevation_40to50` | int | | Position to send when in elevation between 40 and 50 (0)
`elevation_50to60` | int | | Position to send when in elevation between 50 and 60 (0)
`elevation_gt60` | int | | Position to send when in elevation > 60 (0)

## Meta


This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
