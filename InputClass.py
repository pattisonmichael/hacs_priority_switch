"""Module contains the InputClass for managing priority switches in Home Assistant."""  # pylint: disable=invalid-name

from collections.abc import Callable
from datetime import datetime, timedelta
import functools
import logging
from typing import Any

from homeassistant.components.template.template_entity import _TemplateAttribute
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Context,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_call_later,
    async_track_state_change_event,
    async_track_template_result,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger import async_initialize_triggers

from .const import DOMAIN
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
        manual_trigger=None,
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
        self.manual_trigger = manual_trigger
        self.manual_unregister_callback = None
        self._logger = _LOGGER
        self.auto_on_job = HassJob(
            functools.partial(self._auto_on, hass),
            # job_type=HassJobType.Callback,
            cancel_on_shutdown=True,
        )
        self.auto_off_job = HassJob(
            functools.partial(self._auto_off, hass),
            # job_type=HassJobType.Callback,
            cancel_on_shutdown=True,
        )
        # self.register_control_callbacks()

    # self._async_cancel_retry_setup = async_call_later(
    #                     hass,
    #                     wait_time,
    #                     HassJob(
    #                         functools.partial(self._async_setup_again, hass),
    #                         job_type=HassJobType.Callback,
    #                         cancel_on_shutdown=True,
    #                     ),
    #                 )
    #################

    @callback
    async def _auto_off(self, now: timedelta, *_: Any) -> None:  # pylint: disable=unused-argument
        self.control_state = False
        self.priority_switch.recalculate_value(caller="auto_off")
        self._logger.debug("Auto Off")

    @callback
    async def _auto_on(self, hass: HomeAssistant, *_: Any) -> None:  # pylint: disable=unused-argument
        self.control_state = True
        self.priority_switch.recalculate_value(caller="auto_off")
        self._logger.debug("Auto On")

    ######

    @callback
    def _handle_results(
        self,
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Call back the results to the attributes."""
        self._logger.debug("_handle_results: %s", event)
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
            # self.register_value_callbacks()
            #     self.auto_off_job = HassJob(
            #     functools.partial(self._auto_off, hass),
            #     # job_type=HassJobType.Callback,
            #     cancel_on_shutdown=True,
            # )
            self.hass.async_run_hass_job(
                hassjob=HassJob(self.register_value_callbacks, cancel_on_shutdown=True)
            )
            # asyncio.run_coroutine_threadsafe(
            #     self.register_value_callbacks(), self.hass.loop
            # )
            if self.auto_off:
                self._logger.debug("Setup Auto Off")
                async_call_later(
                    hass=self.hass,
                    delay=timedelta(**self.auto_off),
                    # action=self.auto_off_job,
                    action=self._auto_off,
                )
        else:
            self.remove_callbacks_value()
            if self.auto_on:
                self._logger.debug("Setup Auto On")
                async_call_later(
                    hass=self.hass,
                    delay=timedelta(**self.auto_on),
                    # action=self.auto_on_job,
                    action=self._auto_on,
                )

        self._control_state = value
        self.priority_switch.recalculate_value(caller="control_state setter")

    ### for manual trigger
    async def async_trigger(
        self, variables: dict[str, Any], context: Context | None = None
    ) -> None:
        """Trigger the control state manually."""
        # self._async_set_remaining_time_var(timeout_handle)
        # self._variables["wait"]["completed"] = True
        # self._variables["wait"]["trigger"] = variables["trigger"]
        # _set_result_unless_done(done)
        self.control_state = True
        self._logger.debug("test async_done")
        self._logger.debug(
            "Manual Trigger reached. Context: %s Variables: %s",
            context,
            variables,
        )

    def log_cb(self, level: int, msg: str, **kwargs: Any) -> None:
        """Log for trigger."""
        self._logger.debug(msg)

        ###

    async def register_control_callbacks(self):
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
            _LOGGER.debug("Should this be Control callback?:")
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
        elif ctype == ControlType.MANUAL:
            #####
            # remove_triggers = self.hass.async_run_job(
            #     async_initialize_triggers(
            #         self.hass,
            #         self.manual_trigger,
            #         async_done,
            #         DOMAIN,
            #         self.name,
            #         log_cb,
            #         # variables=variables,
            #     )
            # )
            # remove_triggers = asyncio.run_coroutine_threadsafe(
            #     async_initialize_triggers(
            #         self.hass,
            #         self.manual_trigger,
            #         async_done,
            #         DOMAIN,
            #         self.name,
            #         log_cb,
            #         # variables=variables,
            #     ),
            #     self.hass.loop,
            # )
            remove_triggers = await async_initialize_triggers(
                self.hass,
                self.manual_trigger,
                self.async_trigger,
                DOMAIN,
                self.name,
                self.log_cb,
                # variables=variables,
            )
            ##
            #      return await async_initialize_triggers(
            #     self.hass,
            #     self._trigger_config,
            #     self._async_trigger_if_enabled,
            #     DOMAIN,
            #     str(self.name),
            #     self._log_callback,
            #     home_assistant_start,
            #     variables,
            # )

            ##
            if not remove_triggers:
                return

            self.manual_unregister_callback = remove_triggers
            _LOGGER.debug(
                "Setup Manual Trigger: %s",
                self.manual_trigger,
            )

    #####
    # self.priority_switch.recalculate_value(
    #     caller="process_entity_state", trigger=self.name
    # )
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

    async def register_value_callbacks(self):
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

            # self.control_state = new_state.state
            self.value = new_state.state
            _LOGGER.debug("Should this be Value Callback?:")
            _LOGGER.debug(
                "Received control callback: %s ,%s", self.name, new_state.state
            )
            _LOGGER.debug(
                "Context user: %s origin: %s",
                event.context.user_id,
                event.context.origin_event,
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
        # elif itype == InputType.MANUAL:
        #     if self.manual_trigger is not None:
        #         ###
        #         async def async_done(
        #             variables: dict[str, Any], context: Context | None = None
        #         ) -> None:
        #             # self._async_set_remaining_time_var(timeout_handle)
        #             # self._variables["wait"]["completed"] = True
        #             # self._variables["wait"]["trigger"] = variables["trigger"]
        #             # _set_result_unless_done(done)
        #             _LOGGER.debug(
        #                 "Manual Trigger reached. Context: %s Variables: %s",
        #                 context,
        #                 variables,
        #             )

        #         def log_cb(level: int, msg: str, **kwargs: Any) -> None:
        #             _LOGGER.debug(msg)

        #         remove_triggers = await async_initialize_triggers(
        #             self.hass,
        #             self.manual_trigger,
        #             async_done,
        #             DOMAIN,
        #             self.name,
        #             log_cb,
        #             # variables=variables,
        #         )
        #         if not remove_triggers:
        #             return

        #         self.manual_unregister_callback = remove_triggers
        #         _LOGGER.debug(
        #             "Setup Manual Trigger: %s",
        #             self.manual_trigger,
        #         )
        #         ####
        #         # template_var_tups: list[TrackTemplate] = []
        #         # template_var_tup = TrackTemplate(Template(self.value_template), None)
        #         # template_var_tups.insert(0, template_var_tup)

        #         # result_info = async_track_template_result(
        #         #     self.hass,
        #         #     template_var_tups,
        #         #     self._value_handle_results,
        #         #     has_super_template=False,
        #         # )
        #         # self.value_unregister_callback = result_info.async_remove
        #         # self._value_template_result_info = result_info
        #         # result_info.async_refresh()
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
        if self.manual_unregister_callback is not None:
            self.manual_unregister_callback()

    def remove_callbacks_value(self):
        """Deregister callback functions for entity and template updates.

        This is where you would disconnect from Home Assistant's event system
        """
        while self.cleanup_value_callbacks:
            self.cleanup_value_callbacks.pop()()
