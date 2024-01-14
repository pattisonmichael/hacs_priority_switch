"""Main Priority Switch Entity Class file."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

# from homeassistant.core import HomeAssistant
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HomeAssistant,
    State,
    callback,
    validate_state,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_call_later,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

from .const import DOMAIN, DOMAIN_FRIENDLY, ControlType, InputType, ATTR_CONTROL_STATE

_LOGGER = logging.getLogger(__name__)


class InputClass:
    """Main Input Class."""

    def __init__(
        self,
        priority_switch,
        name,
        priority,
        control_type,
        control_state=None,
        control_value=None,
        control_entity=None,
        control_template=None,
        value_type=None,
        value=None,
        value_template=None,
        value_entity=None,
        auto_on=None,
        auto_off=None,
        hass: HomeAssistant = None,
        # callback=None,
    ):
        """Init Class for Input."""
        self.priority_switch = (
            priority_switch  # Reference to the PrioritySwitch instance
        )
        self.name = name
        self.priority = priority
        self.control_type = ControlType(control_type)
        self.control_state = control_state
        self.control_value = control_value
        self.control_entity = control_entity
        self.control_template = control_template
        self.control_sensor_source_id = None
        self.control_unregister_callback = None
        self.value_type = InputType(value_type)
        self.value = value
        self.value_template = value_template
        self.value_entity = value_entity
        self.auto_on = auto_on
        self.auto_off = auto_off
        self.hass = hass
        # self.parent_callback = callback

        self.register_callbacks()

    def register_callbacks(self):
        """Register callback functions for entity and template updates.

        This is where you would connect to Home Assistant's event system
        """

        @callback
        def process_entity_change(event: EventType[EventStateChangedData]) -> None:
            """Handle the sensor state changes."""
            if (
                (old_state := event.data["old_state"]) is None
                or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                or (new_state := event.data["new_state"]) is None
                or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return

            self.control_state = new_state.state
            self.priority_switch.recalculate_value()

        if (ctype := self.control_type) in [ControlType.TRUE, ControlType.FALSE]:
            self.control_state = cv.boolean(self.control_type)
        elif ctype == ControlType.ENTITY:
            registry = er.async_get(self.hass)
            # Validate + resolve entity registry id to entity_id
            self.control_sensor_source_id = er.async_validate_entity_id(
                registry, self.control_entity
            )
            # self.async_on_remove(
            self.control_unregister_callback = async_track_state_change_event(
                self.hass, self.control_sensor_source_id, process_entity_change
            )
            try:
                self.control_state = self.hass.states.get(
                    self.control_sensor_source_id
                ).state
            finally:
                pass
            # )
        elif ctype == ControlType.TEMPLATE:
            pass
        ###

    ###
    def remove_callbacks(self):
        """Deregister callback functions for entity and template updates.

        This is where you would disconnect from Home Assistant's event system
        """
        if self.control_unregister_callback is not None:
            self.control_unregister_callback()

    def control_entity_callback_old(self, new_state):
        """Callback for the control entity."""  # noqa: D401
        self.priority_switch.recalculate_state()

    def control_template_callback(self, new_state):
        """Callback for the control template."""  # noqa: D401
        self.priority_switch.recalculate_state()

    def input_entity_callback(self, new_state):
        """Callback for the input entity."""  # noqa: D401
        self.priority_switch.recalculate_state()

    def input_template_callback(self, new_state):
        """Callback for the input template."""  # noqa: D401
        self.priority_switch.recalculate_state()


class PrioritySwitch(SensorEntity):
    """Main PrioritySwitch class."""

    _highest_active_priority = None
    _control_state = None
    _unrecorded_attributes: frozenset({"active_input", "inputs"})
    _attr_has_entity_name = True
    # init_complete = True

    def __init__(self, hass, config, device):  # noqa: D107
        self._name = config["switch_name"]
        self._friendly_name = config["switch_name_friendly"]
        self._config = config
        self._state = None
        # self._attr_is_on = config["enabled"]
        self._inputs = {}  # Using a dictionary to store inputs
        self.hass = hass
        self._value = None
        # self._sensor = sensor  # Reference to the PrioritySensor instance
        # self._attr_device_info = device.dict_repr

    @property
    def name(self):  # noqa: D102
        return self._name

    @property
    def friendly_name(self):  # noqa: D102
        return self._friendly_name

    # @property
    # def is_on(self):  # noqa: D102
    #     return self._state

    @property
    def native_value(self):  # noqa: D102
        return self._value

    def add_input(self, input_data):
        """Add a new input to the switch."""
        if len(self._inputs) < 20:
            input_data.update({"hass": self.hass})
            input_obj = InputClass(self, **input_data)
            self._inputs[input_obj.priority] = input_obj
            self.recalculate_value()
        else:
            raise ValueError("Cannot add more than 20 inputs")

    def remove_input(self, input_name):
        """Remove an input from the switch."""
        if input_name in self._inputs:
            input_obj = self._inputs[input_name]
            input_obj.remove_callbacks()
            del self._inputs[input_name]
            self.recalculate_value()

    def _get_highest_active_input(self) -> int | None:
        """Find the highest priority input which is active."""
        highest_priority_input = max(
            (
                obj
                for obj in self._inputs.values()
                if (
                    cv.boolean(
                        obj.control_state if obj.control_state is not None else False
                    )
                )
            ),
            key=lambda obj: obj.priority,
            default=None,  # This avoids a ValueError if no object meets the criteria
        )
        return (
            highest_priority_input.priority
            if highest_priority_input is not None
            else None
        )

    def recalculate_value(self):  # noqa: D102
        # Implement the logic to recalculate the state of the switch
        # After recalculating, update the state of the switch
        # if not self._state:
        #    return

        # self.set_state(new_state)
        self._highest_active_priority = self._get_highest_active_input()
        if self._highest_active_priority is None:
            # new_state = False
            self._value = None
        else:
            # new_state = cv.boolean(
            #     self._inputs[self._highest_active_priority].control_state
            # )
            self._value = self._inputs[self._highest_active_priority].value

        # self._attr_is_on = new_state
        # self._control_state=new_state
        # self._state = new_state
        # Update the sensor state based on the switch state or other criteria
        # if (
        #     self._state != new_state
        #     and self._highest_active_priority is not None
        # ):
        #     self._control_state = new_state
        #     self._sensor.set_state(self._inputs[self._highest_active_priority].value)
        #     if self.init_complete:
        #         self.schedule_update_ha_state()
        if self.entity_id is None:
            _LOGGER.debug("No Entity ID set in recalculate_value")
        else:
            self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Automatically called by Home Assistant when this entity is about to be removed."""
        for input_obj in self._inputs.values():
            input_obj.remove_callbacks()
        await super().async_will_remove_from_hass()

    # async def async_turn_on(self, **kwargs):
    #     """Turn the switch on."""
    #     self._state = True
    #     self._attr_is_on = True
    #     self.recalculate_state()

    # async def async_turn_off(self, **kwargs):
    #     """Turn the switch off."""
    #     self._state = False
    #     self._attr_is_on = False
    #     self.recalculate_state()

    async def async_update(self):
        """Update the switch state."""
        self.recalculate_value()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        # def extra_state_attributes(self):
        """Return additional attributes."""
        states = {
            "active_input": self._highest_active_priority
            if self._highest_active_priority is not None
            else "None",
        }
        inputs = {}
        for item in self._inputs.values():
            inputs.update(
                {cv.slugify(item.name): {ATTR_CONTROL_STATE: item.control_state}}
            )
        states.update({"inputs": inputs})
        return states


class PrioritySensor(SensorEntity):
    def __init__(self, name, friendly_name, device):
        self._name = name
        self._friendly_name = friendly_name
        self._state = None
        # self._attr_device_info = device.dict_repr
        self._value = None

    @property
    def name(self):
        return self._name

    @property
    def friendly_name(self):
        return self._friendly_name

    @property
    def state(self):
        return self._state

    def set_state(self, value):
        self._state = value
        # self.schedule_update_ha_state()

    @property
    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.schedule_update_ha_state()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create an instance of the PrioritySwitch."""

    _LOGGER.debug("Switch async_setup_entry")
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={},
        identifiers={(DOMAIN, config_entry.data["switch_name"])},
        manufacturer=DOMAIN_FRIENDLY,
        # suggested_area="Kitchen",
        name=config_entry.data.get("switch_name_friendly"),
        # model=entry.data.get('switch_name_friendly'),
        # sw_version="config.swversion",
        # hw_version="config.hwversion",
    )

    # Create an instance of the PrioritySensor
    # priority_sensor = PrioritySensor(
    #     name=config_entry.data["switch_name"] + "_out",
    #     friendly_name=config_entry.data["switch_name_friendly"] + " out",
    #     device=device,
    # )

    # Create an instance of the PrioritySwitch and pass the sensor to it
    priority_switch = PrioritySwitch(
        hass=hass,
        # name=config_entry.data["switch_name"],
        # friendly_name=config_entry.data["switch_name_friendly"],
        # sensor=priority_sensor,
        device=device,
        config=config_entry.data,
    )

    # Add inputs to the switch based on configuration or other criteria
    # This is just a placeholder for how you might add inputs

    # Add the switch entity to Home Assistant
    async_add_entities(
        [
            # priority_sensor,
            priority_switch
        ]
    )

    for input_data in config_entry.data.get("inputs", []).values():
        input_data["control_type"] = getattr(
            ControlType, input_data["control_type"].upper()
        )
        input_data["value_type"] = getattr(InputType, input_data["value_type"].upper())
        priority_switch.add_input(input_data)

    # async_add_entities(
    #     [
    #         PrioritySwitch(
    #             device,
    #             hass=hass,
    #             name=f"{DOMAIN_FRIENDLY} {device.name}",
    #             data=entry,
    #             async_add_entities=async_add_entities,
    #         )
    #     ]
    # )
    # for inp in self._inputs:
    #     print(inp)
    _LOGGER.debug("Finished adding priority switch:\n%s", config_entry)
    # Return True if setup was successful
    return True
