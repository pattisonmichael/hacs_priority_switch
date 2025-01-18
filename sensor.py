"""Main Priority Switch Entity Class file."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

from voluptuous import error as vol_err

from homeassistant.components.sensor import RestoreSensor, SensorEntity

# from homeassistant.components.switch import SwitchEntity
# from homeassistant.core import HomeAssistant
from homeassistant.core import Context, Event, EventStateChangedData, callback

# validate_state,
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    # EventStateChangedData,
    async_track_state_change_event,
)

# from homeassistant.helpers.typing import EventType  # ConfigType, DiscoveryInfoType,
from .const import (
    ATTR_CONTROL_ENTITY,
    ATTR_CONTROL_ENTITY_VALUE,
    ATTR_CONTROL_STATE,
    ATTR_CONTROL_TEMPLATE,
    ATTR_CONTROL_TEMPLATE_VALUE,
    ATTR_CONTROL_TYPE,
    ATTR_VALUE,
    ATTR_VALUE_ENTITY,
    ATTR_VALUE_TEMPLATE,
    ATTR_VALUE_TYPE,
    DOMAIN,
    DOMAIN_FRIENDLY,
)
from .data_types import ControlType, InputType
from .InputClass import InputClass

_LOGGER = logging.getLogger(__name__)


class PrioritySwitch(RestoreSensor, SensorEntity):
    """Main PrioritySwitch class."""

    _highest_active_priority = None
    _control_state = None
    _unrecorded_attributes: frozenset({"active_input", "inputs"})  # type: ignore[reportInvalidTypeForm ] pylint: disable=C0301
    _attr_has_entity_name = True
    _prev_value = None
    _last_command_time = None
    _command_grace_period = None  # Adjust based on the maximum expected operation time
    _is_paused = False
    _output_unregister_callback: list[Callable[[], None]] = []
    # init_complete = True

    def __init__(self, hass, config):  # noqa: D107
        self._name = config["switch_name"]
        self._friendly_name = config["switch_name_friendly"]
        self._only_send_on_change = config.get("only_send_on_change", True)
        self._deadtime = config.get("deadtime")
        self._command_grace_period = (
            timedelta(**self._deadtime) if self._deadtime is not None else None
        )
        self._detect_manual = config.get("detect_manual", False)
        self._automation_pause = (
            timedelta(**self._deadtime)
            if config.get("automation_pause") is not None
            else None
        )
        self._logger = _LOGGER
        self._config = config
        self._state = None
        # self._attr_is_on = config["enabled"]
        self._inputs = {}  # Using a dictionary to store inputs
        self.hass = hass
        self._attr_unique_id = f"{config['switch_name']}-test"
        self._value = None
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (DOMAIN, config["switch_name"]),
            },
            name=config["switch_name"],
            manufacturer=DOMAIN_FRIENDLY,
            # model="Nordic",
            # serial_number=coordinator.device.serial_number,
        )
        # model=entry.data.get('switch_name_friendly'),
        # sw_version="config.swversion",
        # hw_version="config.hwversion",
        # self._sensor = sensor  # Reference to the PrioritySensor instance
        # self._attr_device_info = device.dict_repr
        self.register_output_callback()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        restored_data = await self.async_get_last_sensor_data()
        if restored_data:
            self._attr_native_unit_of_measurement = (
                restored_data.native_unit_of_measurement
            )
            try:
                self._attr_native_value = restored_data.native_value
            except SyntaxError as err:
                _LOGGER.warning("Could not restore last state: %s", err)

    @property
    def name(self):  # noqa: D102
        return self._name

    @property
    def friendly_name(self):
        """Friendly Name."""
        return self._friendly_name

    # @property
    # def is_on(self):  # noqa: D102
    #     return self._state

    @property
    def native_value(self):
        """Native value."""
        return self._value

    async def add_input(self, input_data):
        """Add a new input to the switch."""
        if len(self._inputs) < 20:
            # input_data.update({"hass": self.hass})
            input_obj = InputClass(
                self,
                hass=self.hass,
                **input_data,
            )
            await input_obj.register_control_callbacks()
            self._inputs[input_obj.priority] = input_obj
            self.recalculate_value(caller="add_input")
        else:
            raise ValueError("Cannot add more than 20 inputs")

    def remove_input(self, input_name):
        """Remove an input from the switch."""
        if input_name in self._inputs:
            input_obj = self._inputs[input_name]
            input_obj.remove_callbacks()
            del self._inputs[input_name]
            self.recalculate_value(caller="remove_input")

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

    def recalculate_value(self, caller=None, trigger=None):
        """Recalculate current state and value of the sensor."""
        # Implement the logic to recalculate the state of the switch
        # After recalculating, update the state of the switch
        # if not self._state:
        #    return

        # self.set_state(new_state)
        # previousValue = self._value
        if self._is_paused:
            _LOGGER.debug("Paused, not recalculating.")
        else:
            self._highest_active_priority = self._get_highest_active_input()
            if self._highest_active_priority is None:
                # new_state = False
                self._value = None
            else:
                # new_state = cv.boolean(
                #     self._inputs[self._highest_active_priority].control_state
                # )
                self._value = self._inputs[self._highest_active_priority].value

        if self.entity_id is None:
            _LOGGER.debug("No Entity ID set in recalculate_value")
        else:
            _LOGGER.debug(
                "Updated value: %s, Called by: %s, Trigger: %s",
                self._value,
                caller,
                trigger,
            )
            if caller == "async_update":
                self.schedule_update_ha_state()
                return
        self.schedule_update_ha_state(force_refresh=True)

    async def async_will_remove_from_hass(self) -> None:
        """Automatically called by Home Assistant when this entity is about to be removed."""
        for input_obj in self._inputs.values():
            input_obj.remove_callbacks()
        await super().async_will_remove_from_hass()

    def register_output_callback(self):
        """Register callbacks for output ws."""

        @callback
        async def handle_output_entity_state_change(
            event: Event[EventStateChangedData],  # pylint: disable=unused-argument
        ) -> None:
            # Check if the state change is for the entity we're interested in
            # if event.data["entity_id"] != self._config.get(output_entity):
            #     return

            # If we're paused, ignore state changes
            if self._is_paused:
                return

            # now = datetime.now()

            # Check if we're within the grace period of an automated command
            if event.context.parent_id == "priorityswitch":
                # if self._last_command_time and now - self._last_command_time <= timedelta(
                #     **self._deadtime
                # ):
                # This change is considered part of the automated command; no action needed
                _LOGGER.debug(
                    "Change within grace period, considered as automated. Last Command Time: %s and dead time: %s",  # pylint: disable=line-too-long
                    self._last_command_time,
                    self._deadtime,
                )
            else:
                # Detected a change outside the grace period, likely manual
                _LOGGER.debug(
                    "Change detected outside grace period, likely manual. Pausing operations."
                )
                self._is_paused = True
                # self.recalculate_value(caller="handle_output_entity_state_change")
                # await self.async_update()  # Finally fixed ?

        if (x := self._config.get("output_entity")) is not None:
            registry = er.async_get(self.hass)
            # Validate + resolve entity registry id to entity_id
            for entity in x["entity_id"]:
                # try:
                output_entity = er.async_validate_entity_id(registry, entity)
                # self.async_on_remove(
                self._output_unregister_callback.append(
                    async_track_state_change_event(
                        self.hass, output_entity, handle_output_entity_state_change
                    )
                )
            # except:
            #    _LOGGER.debug("Error tracking output entity: %s", entity)

    def remove_callbacks_value(self):
        """Deregister callback functions for entity and template updates.

        This is where you would disconnect from Home Assistant's event system
        """
        while self._output_unregister_callback:
            self._output_unregister_callback.pop()()

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
        self.recalculate_value(caller="async_update")
        now = datetime.now()
        if (
            self._is_paused
            and self._deadtime is not None
            and (
                (now - (self._last_command_time or datetime.min))
                >= timedelta(**self._deadtime)
            )
        ):
            #####
            self._is_paused = False
            self._prev_value = None
            _LOGGER.debug(
                "Not Paused anymore: %s, isPaused: %s", self._name, self._is_paused
            )

        #####
        if (
            self.state == self._prev_value
            and self._only_send_on_change
            or self._is_paused
        ) and self.state is not None:
            _LOGGER.debug(
                "Same value or paused, not sending for: %s, Value: %s, Previous Value: %s",
                self._name,
                self.state,
                self._prev_value,
            )
            return
        self._last_command_time = datetime.now()
        self._prev_value = self.state
        context = Context()
        context.parent_id = "priorityswitch"
        if self._config.get("output_script") is not None:
            await self.hass.services.async_call(
                domain="script",
                service="turn_on",
                service_data={
                    "variables": {
                        "value": self.state if self.state is not None else "",
                        "sensor": self.name,
                    }
                },
                target=self._config["output_script"],
                blocking=False,
                context=context,
            )
        if (x := self._config.get("output_entity")) is not None:
            for entity_id in x["entity_id"]:
                entity = self.hass.states.get(entity_id)
                if entity.domain == "light":
                    _LOGGER.debug("Light entity: %s", entity)
                    await self.hass.services.async_call(
                        domain="light",
                        service="turn_on",
                        service_data={
                            "brightness_pct": int(self.state)
                            if self.state is not None
                            else 0
                        },
                        target=x,
                        blocking=False,
                        context=context,
                    )
                elif entity.domain in ["switch", "input_boolean"]:
                    _LOGGER.debug("Switch/Input_Boolean entity: %s", entity)
                    try:
                        state = float(self.state)
                    except (ValueError, TypeError):
                        state = self.state
                    try:
                        service = "turn_on" if cv.boolean(state) else "turn_off"
                    except vol_err.Invalid:
                        service = "turn_off"
                    await self.hass.services.async_call(
                        domain="switch"
                        if entity.domain == "switch"
                        else "input_boolean",
                        service=service,
                        target=x,
                        blocking=False,
                        context=context,
                    )
                elif entity.domain == "cover":
                    _LOGGER.debug("Cover entity: %s, set to: %s", entity, self.state)
                    await self.hass.services.async_call(
                        domain="cover",
                        service="set_cover_position",
                        service_data={
                            "position": int(self.state) if self.state is not None else 0
                        },
                        target=x,
                        blocking=False,
                        context=context,
                    )
                elif entity.domain == "input_number":
                    _LOGGER.debug(
                        "Input_Number entity: %s, set to: %s", entity, self.state
                    )

                    await self.hass.services.async_call(
                        domain="input_number",
                        service="set_value",
                        service_data={
                            "value": float(self.state) if self.state is not None else 0,
                        },
                        target=x,
                        blocking=True,
                        context=context,
                    )
        _LOGGER.debug("Updated entity: %s", self.state)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        # def extra_state_attributes(self):
        """Return additional attributes."""
        states = {
            "active_input": self._highest_active_priority
            if self._highest_active_priority is not None
            else "None",
            "active_input_friendly": (
                self._inputs[self._highest_active_priority].name
                if self._highest_active_priority is not None
                and self._highest_active_priority >= 0
                else "None"
                if self._highest_active_priority is None
                else "Paused"
            ),
            "paused": self._is_paused,
        }
        if self._config.get("output_entity"):
            states.update({"output_entity": self._config.get("output_entity")})
        elif self._config.get("output_script"):
            states.update({"output_script": self._config.get("output_script")})

        inputs = {}
        for item in self._inputs.values():
            x = item.name
            inputs[x] = {
                ATTR_CONTROL_STATE: item.control_state,
                ATTR_CONTROL_TYPE: str(item.control_type),
            }
            if item.control_type == ControlType.ENTITY:
                inputs[x][ATTR_CONTROL_ENTITY] = item.control_entity
                inputs[x][ATTR_CONTROL_ENTITY_VALUE] = item.control_state
            elif item.control_type == ControlType.TEMPLATE:
                inputs[x][ATTR_CONTROL_TEMPLATE] = item.control_template
                inputs[x][ATTR_CONTROL_TEMPLATE_VALUE] = item.control_state
            inputs[x][ATTR_VALUE_TYPE] = str(item.value_type)
            if item.value_type == InputType.FIXED:
                inputs[x][ATTR_VALUE_TYPE] = item.value_type
                inputs[x][ATTR_VALUE] = item.value
            elif item.value_type == InputType.ENTITY:
                inputs[x][ATTR_VALUE_TYPE] = item.value_type
                inputs[x][ATTR_VALUE_ENTITY] = item.value_entity
                inputs[x][ATTR_VALUE] = item.value
            elif item.value_type == InputType.TEMPLATE:
                inputs[x][ATTR_VALUE_TYPE] = item.value_type
                inputs[x][ATTR_VALUE_TEMPLATE] = item.value_template
                inputs[x][ATTR_VALUE] = item.value
            elif item.value_type == InputType.SUN:
                inputs[x][ATTR_VALUE_TYPE] = item.value_type
                inputs[x][ATTR_VALUE] = item.value
            # inputs.update(
            #     {cv.slugify(item.name): {
            #         ATTR_CONTROL_STATE: item.control_state,
            #         ATTR_CONTROL_TYPE:str(item.control_type),
            #         }
            #      }
            # )
        states.update({"inputs": inputs})
        return states


class PrioritySensor(RestoreSensor, SensorEntity):
    """Main PrioritySensor Class."""

    def __init__(self, name, friendly_name):
        """Init function."""
        self._name = name
        self._friendly_name = friendly_name
        self._state = None
        # self._attr_device_info = device.dict_repr
        self._value = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        restored_data = await self.async_get_last_sensor_data()
        if restored_data:
            self._attr_native_unit_of_measurement = (
                restored_data.native_unit_of_measurement
            )
            try:
                self._attr_native_value = restored_data.native_value
            except SyntaxError as err:
                _LOGGER.warning("Could not restore last state: %s", err)

    @property
    def name(self):
        """Entity Name."""
        return self._name

    @property
    def friendly_name(self):
        """Entity friendly Name."""
        return self._friendly_name

    @property
    def state(self):  # pylint: disable=overridden-final-method
        """Entity State."""
        return self._state

    def set_state(self, value):
        """Set Entity State. Use from external."""
        self._state = value
        # self.schedule_update_ha_state()

    @property
    def value(self):
        """Value."""
        # TODO check if still called or required
        _LOGGER.debug("PrioritySensor get value property still used")
        return self._value

    def set_value(self, value):
        """Set Value."""
        # TODO check if still called or required
        self._value = value
        _LOGGER.debug("PrioritySensor set value property still used")
        self.schedule_update_ha_state()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create an instance of the PrioritySwitch."""

    _LOGGER.debug("Switch async_setup_entry")

    # Create an instance of the PrioritySwitch and pass the sensor to it
    priority_switch = PrioritySwitch(
        hass=hass,
        # name=config_entry.data["switch_name"],
        # friendly_name=config_entry.data["switch_name_friendly"],
        # sensor=priority_sensor,
        # device=device,
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
        await priority_switch.add_input(input_data)

    _LOGGER.debug("Finished adding priority switch:\n%s", config_entry.data)
    # Return True if setup was successful
    return True
