"""Main Priority Switch Entity Class file."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

from voluptuous import error as vol_err

from homeassistant.components.sensor import RestoreSensor, SensorEntity

# from homeassistant.components.switch import SwitchEntity
from homeassistant.components.template.template_entity import _TemplateAttribute
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

# from homeassistant.core import HomeAssistant
from homeassistant.core import (
    Event,
    EventStateChangedData,
    # CALLBACK_TYPE,
    # Context,
    HomeAssistant,
    # State,
    callback,
)

# validate_state,
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import Entity  # , EntityDescription
from homeassistant.helpers.event import (
    # EventStateChangedData,
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    # async_call_later,
    async_track_state_change_event,
    async_track_template_result,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template  # , result_as_boolean

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

_LOGGER = logging.getLogger(__name__)


class InputClass(Entity):
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
        azimut=None,
        elevation=None,
        building_deviation=None,
        offset_entry=None,
        offset_exit=None,
        update_interval=None,
        sun_entity=None,
        set_if_in_shadow=None,
        shadow=None,
        elevation_lt10=None,
        elevation_10to20=None,
        elevation_20to30=None,
        elevation_30to40=None,
        elevation_40to50=None,
        elevation_50to60=None,
        elevation_gt60=None,
    ):
        """Init Class for Input."""
        self.priority_switch = (
            priority_switch  # Reference to the PrioritySwitch instance
        )
        self.name = name
        self.priority = priority
        self.control_type = ControlType(control_type)
        self._control_state = control_state
        self.control_value = control_value
        self.control_entity = control_entity
        self.control_template = control_template
        self._template_attrs: dict[Template, list[_TemplateAttribute]] = {}
        self._template_result_info: TrackTemplateResultInfo | None = None
        self._self_ref_update_count = 0
        self._value_template_attrs: dict[Template, list[_TemplateAttribute]] = {}
        self._value_template_result_info: TrackTemplateResultInfo | None = None
        self._value_self_ref_update_count = 0
        self.control_sensor_source_id = None
        self.control_unregister_callback = None
        self.value_sensor_source_id = None
        self.value_unregister_callback = None
        self.value_type = InputType(value_type)
        self.value = value
        self.value_template = value_template
        self.value_entity = value_entity
        self.auto_on = auto_on
        self.auto_off = auto_off
        self.hass = hass
        # self.parent_callback = callback
        self.azimut = azimut
        self.elevation = elevation
        self.building_deviation = building_deviation
        self.offset_entry = offset_entry
        self.offset_exit = offset_exit
        self.update_interval = update_interval
        self.sun_entity = sun_entity
        self.set_if_in_shadow = set_if_in_shadow
        self.shadow = shadow
        self.in_sun = False
        self.elevation_lt10 = elevation_lt10
        self.elevation_10to20 = elevation_10to20
        self.elevation_20to30 = elevation_20to30
        self.elevation_30to40 = elevation_30to40
        self.elevation_40to50 = elevation_40to50
        self.elevation_50to60 = elevation_50to60
        self.elevation_gt60 = elevation_gt60
        self.cleanup_value_callbacks: list[Callable[[], None]] = []
        self.register_control_callbacks()

    #################

    ######

    @callback
    def _handle_results(
        self,
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Call back the results to the attributes."""
        if event:
            self.async_set_context(event.context)

        entity_id = event and event.data["entity_id"]

        if entity_id and entity_id == self.entity_id:
            self._self_ref_update_count += 1
        else:
            self._self_ref_update_count = 0

        if self._self_ref_update_count > len(self._template_attrs):
            for update in updates:
                _LOGGER.warning(
                    (
                        "Template loop detected while processing event: %s, skipping"
                        " template render for Template[%s]"
                    ),
                    event,
                    update.template.template,
                )
            return

        if updates is not None:
            self.control_state = cv.boolean(updates[0].result)
            self.priority_switch.recalculate_value()

    @callback
    def _value_handle_results(
        self,
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Call back the results to the attributes."""
        if event:
            self.async_set_context(event.context)

        entity_id = event and event.data["entity_id"]

        if entity_id and entity_id == self.entity_id:
            self._value_self_ref_update_count += 1
        else:
            self._value_self_ref_update_count = 0

        if self._value_self_ref_update_count > len(self._value_template_attrs):
            for update in updates:
                _LOGGER.warning(
                    (
                        "Template loop detected while processing event: %s, skipping"
                        " template render for Template[%s]"
                    ),
                    event,
                    update.template.template,
                )
            return

        if updates is not None:
            self.value = updates[0].result
            self.priority_switch.recalculate_value()

    ######

    @property
    def control_state(self):
        """Get the control state."""
        # Getter method
        return self._control_state

    @control_state.setter
    def control_state(self, value):
        # Setter method
        if cv.boolean(value):
            self.register_value_callbacks()
        else:
            self.remove_callbacks_value()
        self._control_state = value

    def register_control_callbacks(self):
        """Register callback functions for entity and template updates.

        This is where you would connect to Home Assistant's event system
        """

        @callback
        def process_entity_state(event: Event[EventStateChangedData]) -> None:
            """Handle the sensor state changes."""
            if (
                (old_state := event.data["old_state"]) is None
                or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                or (new_state := event.data["new_state"]) is None
                or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return

            self.control_state = new_state.state
            _LOGGER.debug("Received value callback: %s ,%s", self.name, new_state.state)
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
                self.hass, self.control_sensor_source_id, process_entity_state
            )
            try:
                entity = self.hass.states.get(self.control_sensor_source_id)
                if entity is not None:
                    self.control_state = entity.state
            finally:
                pass
            # )
        elif ctype == ControlType.TEMPLATE:
            if self.control_template is not None:
                template_var_tups: list[TrackTemplate] = []
                template_var_tup = TrackTemplate(Template(self.control_template), None)
                template_var_tups.insert(0, template_var_tup)

                result_info = async_track_template_result(
                    self.hass,
                    template_var_tups,
                    self._handle_results,
                    # log_fn=log_fn,
                    has_super_template=False,
                )
                self.control_unregister_callback = result_info.async_remove
                self._template_result_info = result_info
                result_info.async_refresh()

        self.priority_switch.recalculate_value(
            caller="process_entity_state", trigger=self.name
        )
        # TODO also check shadow position and act acoringly
        # self.async_on_remove(
        # self.value_unregister_callback = async_track_state_change_event(
        #     self.hass, self.value_sensor_source_id, process_entity_state
        # )
        # try:
        #     self.value = self.hass.states.get(self.value_sensor_source_id).state
        #     self.sun
        # finally:
        #     pass

    def register_value_callbacks(self):
        """Register callback functions for entity and template updates.

        This is where you would connect to Home Assistant's event system
        """

        @callback
        def process_entity_state(event: Event[EventStateChangedData]) -> None:
            """Handle the sensor state changes."""
            if (
                (old_state := event.data["old_state"]) is None
                or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                or (new_state := event.data["new_state"]) is None
                or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return

            self.control_state = new_state.state
            _LOGGER.debug(
                "Received control callback: %s ,%s", self.name, new_state.state
            )
            self.priority_switch.recalculate_value(
                caller="process_entity_state", trigger=self.name
            )

        @callback
        async def update_sun_callback(now: datetime) -> None:  # pylint: disable=unused-argument
            """Update the sun calculations."""
            self.calc_shade_position()
            self.priority_switch.recalculate_value()

        if (itype := self.value_type) == InputType.ENTITY:
            registry = er.async_get(self.hass)
            # Validate + resolve entity registry id to entity_id
            self.value_sensor_source_id = er.async_validate_entity_id(
                registry, self.value_entity
            )
            # self.async_on_remove(
            self.value_unregister_callback = async_track_state_change_event(
                self.hass, self.value_sensor_source_id, process_entity_state
            )
            try:
                self.value = self.hass.states.get(self.value_sensor_source_id).state
            finally:
                pass
            # )
        elif itype == InputType.TEMPLATE:
            if self.value_template is not None:
                template_var_tups: list[TrackTemplate] = []
                template_var_tup = TrackTemplate(Template(self.value_template), None)
                template_var_tups.insert(0, template_var_tup)

                result_info = async_track_template_result(
                    self.hass,
                    template_var_tups,
                    self._value_handle_results,
                    has_super_template=False,
                )
                self.value_unregister_callback = result_info.async_remove
                self._value_template_result_info = result_info
                result_info.async_refresh()
        elif itype == InputType.SUN:
            if self.sun_entity is not None:
                registry = er.async_get(self.hass)
                # Validate + resolve entity registry id to entity_id
                self.value_sensor_source_id = er.async_validate_entity_id(
                    registry, self.sun_entity
                )
                if self.value_sensor_source_id is not None:
                    self.cleanup_value_callbacks.append(
                        async_track_time_interval(
                            self.hass,
                            update_sun_callback,
                            timedelta(minutes=self.update_interval),
                            cancel_on_shutdown=True,
                        )
                    )

                    self.calc_shade_position()
                    _LOGGER.debug(
                        "Set in sun: %s with position: %s", self.in_sun, self.value
                    )
                else:
                    _LOGGER.error(
                        "Couldn't find sun entity: %s", self.value_sensor_source_id
                    )

    # TODO Sun Value Type
    ####
    @callback
    def calc_shade_position(self):
        """Calculate position of shutter according to sun."""

        value = 0
        sun = False
        elevation = self.hass.states.get(self.value_sensor_source_id).attributes.get(
            "elevation", 0
        )
        azimuth = self.hass.states.get(self.value_sensor_source_id).attributes.get(
            "azimuth", 0
        )
        facadeentry = self.building_deviation + self.offset_entry
        facadeexit = self.building_deviation + self.offset_exit
        if elevation <= 0:
            sun = False
        elif facadeentry < 0:
            helper = facadeentry + 360
            if azimuth >= helper or azimuth <= facadeexit:
                sun = True
            else:
                sun = False
        # Azimuth needs to be smaller than helper or larger than facadeentry
        elif facadeexit > 360:
            helper = facadeexit - 360
            if azimuth <= helper or azimuth >= facadeentry:
                sun = True
            else:
                sun = False
            # Check if Azimuth is between facadeentry and facadeexit
        elif azimuth >= facadeentry and azimuth <= facadeexit:
            sun = True
        else:
            sun = False

        if sun:
            if elevation <= 10:
                value = self.elevation_lt10
            elif elevation <= 20:
                value = self.elevation_10to20
            elif elevation <= 30:
                value = self.elevation_20to30
            elif elevation <= 40:
                value = self.elevation_30to40
            elif elevation <= 50:
                value = self.elevation_40to50
            elif elevation <= 60:
                value = self.elevation_50to60
            else:
                value = self.elevation_gt60
        # in shadow
        elif self.set_if_in_shadow:
            value = self.shadow
            _LOGGER.debug("Set in Shadow: %s", value)
            sun = True
        _LOGGER.debug(
            "Set height to: %s Sun: %s, Azimuth: %i, Elevation: %i",
            value,
            sun,
            azimuth,
            elevation,
        )
        #        return value, sun
        self.value = value
        self.in_sun = sun

    ###
    def remove_callbacks(self):
        """Deregister callback functions for entity and template updates.

        This is where you would disconnect from Home Assistant's event system
        """
        if self.control_unregister_callback is not None:
            self.control_unregister_callback()
        if self.value_unregister_callback is not None:
            self.value_unregister_callback()

    def remove_callbacks_value(self):
        """Deregister callback functions for entity and template updates.

        This is where you would disconnect from Home Assistant's event system
        """
        while self.cleanup_value_callbacks:
            self.cleanup_value_callbacks.pop()()


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

    def add_input(self, input_data):
        """Add a new input to the switch."""
        if len(self._inputs) < 20:
            # input_data.update({"hass": self.hass})
            input_obj = InputClass(self, hass=self.hass, **input_data)
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
        self.schedule_update_ha_state()

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

            now = datetime.now()

            # Check if we're within the grace period of an automated command
            if self._last_command_time and now - self._last_command_time <= timedelta(
                **self._deadtime
            ):
                # This change is considered part of the automated command; no action needed
                _LOGGER.debug("Change within grace period, considered as automated.")
            else:
                # Detected a change outside the grace period, likely manual
                _LOGGER.debug(
                    "Change detected outside grace period, likely manual. Pausing operations."
                )
                self._is_paused = True
                self.recalculate_value(caller="handle_output_entity_state_change")

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
        if self._is_paused and (
            (now - (self._last_command_time or datetime.min))
            >= timedelta(**self._deadtime)
        ):
            #####
            self._is_paused = False
            self._prev_value = None

        #####
        if (
            self.state == self._prev_value
            and self._only_send_on_change
            or self._is_paused
        ):
            return
        self._last_command_time = datetime.now()
        self._prev_value = self.state
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
                context=self._context,
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
                        context=self._context,
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
                        context=self._context,
                    )
                elif entity.domain == "cover":
                    _LOGGER.debug("Cover entity: %s", entity)
                    await self.hass.services.async_call(
                        domain="cover",
                        service="set_cover_position",
                        service_data={
                            "position": int(self.state) if self.state is not None else 0
                        },
                        target=x,
                        blocking=False,
                        context=self._context,
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
        priority_switch.add_input(input_data)

    _LOGGER.debug("Finished adding priority switch:\n%s", config_entry.data)
    # Return True if setup was successful
    return True
