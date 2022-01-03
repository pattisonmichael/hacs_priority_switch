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
  
```

## Configuration Options

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | priority_switch | The module name of the app.
`class` | False | string | PrioritySwitch | The name of the Class.
`inputs` | False | list | | The "inputs" used for this automation
`priority_label` | False | list | | Not important for the functionality, only order matters. Top has lowest priority. One or more Home Assistant Entities as switch for AutoMoLi.
`control` | False | string | | Either `'on'`, `'off'` or a boolean switch entity name
`value` | False | string | | Either a valid HA Entity or a static value to be send to the output.
`auto_off` | True | int | | Amount of seconds after a control entity is switched off again after it was switched on.
`auto_on` | True | int | | Amount of seconds after a control entity is switched on again after it was switched off.
`output` | False | string | | entity that will receive the value.
`enabled` | False | bool | | `True` to enable this switch.
`debug` | True | bool | False | `True` to enable debug logging

## Meta


This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
