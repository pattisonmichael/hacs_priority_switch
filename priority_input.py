import logging

from homeassistant import exceptions
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform, UnitOfTime
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
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_call_later,
    async_track_state_change_event,
    async_track_template_result,
)

# from homeassistant.helpers.event import (
#     EventStateChangedData,
#     async_track_state_change_event,
#     async_track_template_result,
#     TrackTemplateResultInfo
# )
from homeassistant.helpers.template import Template, result_as_boolean
from homeassistant.components.template.template_entity import _TemplateAttribute
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

from .const import ATTR_CONTROL_ENTITY, ATTR_CONTROL_ENTITY_VALUE, ATTR_CONTROL_STATE

_LOGGER = logging.getLogger(__name__)


class PriorityInput:
    """Main Class for Inputs."""

    def __init__(
        self,
        hass: HomeAssistant,
        parent,
        identifier,
        data,
        async_add_entities: AddEntitiesCallback,
    ):
        self.parent = parent
        self.identifier = identifier
        self.data = data
        # self.parent.process_input_update(self.identifier, data)
        self._input = None
        self._control_state = None
        self._hass = hass
        self._attr_name = self.data["name"]
        self.priority = self.data["priority"]
        self._type = self.data["control_type"]
        if (ctype := self.data["control_type"]) in ["True", "False"]:
            self._input = PriorityInputFixed(parent=self, data=data)
        elif ctype == "entity":
            self._input = PriorityInputEntity(hass=hass, parent=self, data=data)
            async_add_entities([self._input])
        elif ctype == "template":
            self._input = PriorityInputTemplate(hass=hass, parent=self, data=data)
            async_add_entities([self._input])
        else:
            _LOGGER.debug("Error in PriorityInput, unknown control type: %s", ctype)

    def update(self, data):
        """Update Input."""
        # Forward the data to the parent PrioritySwitch
        _LOGGER.debug("PriorityInput.update(data=%s)", data)
        self.parent.process_input_update(self.identifier)

    def update_control(self, state: bool):
        """Update Control State."""
        self._control_state = state
        # self.update({"control_state": state})
        self.parent.process_input_update(self.identifier)

    @property
    def control_state(self) -> bool:
        """Return the control state of theinput."""
        return self._control_state if self._control_state is not None else False


class PriorityInputFixed:
    """Fixed Input."""

    def __init__(self, parent, data):
        """Init Fixed Input and set state."""
        self.parent = parent
        self.data = data
        # self.parent.process_input_update(self.identifier, data)
        self._control_state = cv.boolean(data["control_type"])
        self.parent.update_control(self._control_state)


class PriorityInputEntity(Entity):
    """Entity Control Input."""

    def __init__(self, hass: HomeAssistant, parent, data):
        """Init Entity Control and set state."""
        self.parent = parent
        self.data = data
        # self._hass = hass
        self.hass = hass
        self._control_entity = data["control_entity"]
        self._control_state = None
        # self.parent.process_input_update(self.identifier, data)
        # self._state = bool(data["control_type"])
        registry = er.async_get(hass)
        # Validate + resolve entity registry id to entity_id
        self._sensor_source_id = er.async_validate_entity_id(
            registry, self._control_entity
        )

        # source_entity = registry.async_get(source_entity_id)
        # self._sensor_source_id = source_entity_id
        # self.parent.update_control(self._state)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

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

            self._control_state = new_state.state
            # self.parent._control_state = cv.boolean(new_state.state)
            self.parent.update_control(cv.boolean(new_state.state))
            # self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sensor_source_id, process_entity_change
            )
        )


class PriorityInputTemplate(Entity):
    """Template Control Input."""

    def __init__(self, hass: HomeAssistant, parent, data):
        """Init Template Control Input and set state."""
        self.parent = parent
        self.data = data
        self.hass = hass
        self._attr_has_entity_name = True
        self._attr_name = data["name"]
        # self._control_entity = data["control_entity"]
        self._control_state = None
        self._control_template = data["control_template"]
        self._template_attrs: dict[Template, list[_TemplateAttribute]] = {}
        self._template_result_info: TrackTemplateResultInfo | None = None
        self._self_ref_update_count = 0
        # self.parent.process_input_update(self.identifier, data)
        # self._state = bool(data["control_type"])
        # registry = er.async_get(hass)
        # # Validate + resolve entity registry id to entity_id
        # self._sensor_source_id = er.async_validate_entity_id(
        #     registry, self._control_entity
        # )

        # source_entity = registry.async_get(source_entity_id)
        # self._sensor_source_id = source_entity_id
        # self.parent.update_control(self._state)

    @callback
    def _handle_results(
        self,
        event: EventType[EventStateChangedData] | None,
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
            self._control_state = updates[0].result
            # self.parent._control_state = cv.boolean(new_state.state)
            self.parent.update_control(cv.boolean(self._control_state))

        # for update in updates:
        #     for template_attr in self._template_attrs[update.template]:
        #         template_attr.handle_result(
        #             event, update.template, update.last_result, update.result
        #         )

        # if not self._preview_callback:
        #     self.async_write_ha_state()
        #     return

        try:
            calculated_state = self._async_calculate_state()
            validate_state(calculated_state.state)
        except Exception as err:  # pylint: disable=broad-exception-caught
            # self._preview_callback(None, None, None, str(err))
            _LOGGER.error(str(err))
        else:
            assert self._template_result_info
            _LOGGER.debug(
                "Template result:\nstate: %s\nattributes: %s",
                calculated_state.state,
                calculated_state.attributes,
            )
            # self._preview_callback(
            #     calculated_state.state,
            #     calculated_state.attributes,
            #     self._template_result_info.listeners,
            #     None,
            # )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        # control_template: Template = self.data["control_template"]
        # control_template.hass = self.hass
        # trigger_info: TriggerInfo
        ######

        template_var_tups: list[TrackTemplate] = []
        has_availability_template = False

        # variables = {"this": TemplateStateFromEntityId(self.hass, self.entity_id)}
        # variables = {}
        # for template, attributes in self._template_attrs.items():
        #     template_var_tup = TrackTemplate(template, variables)
        #     is_availability_template = False
        #     for attribute in attributes:
        #         # pylint: disable-next=protected-access
        #         if attribute._attribute == "_attr_available":
        #             has_availability_template = True
        #             is_availability_template = True
        #         attribute.async_setup()
        #     # Insert the availability template first in the list
        #     if is_availability_template:
        #         template_var_tups.insert(0, template_var_tup)
        #     else:
        #         template_var_tups.append(template_var_tup)
        template_var_tup = TrackTemplate(Template(self._control_template), None)
        template_var_tups.insert(0, template_var_tup)

        result_info = async_track_template_result(
            self.hass,
            template_var_tups,
            self._handle_results,
            # log_fn=log_fn,
            has_super_template=has_availability_template,
        )
        self.async_on_remove(result_info.async_remove)
        self._template_result_info = result_info
        result_info.async_refresh()

        ########
        # self.async_remove(
        #     async_track_template_result(hass=self.hass,track_templates=[self._template],action=process_entity_change)
        # )
        # self.async_on_remove(
        #     async_track_state_change_event(
        #         self.hass, self._sensor_source_id, process_entity_change
        #     )
        # )
        # info = async_track_template_result(
        #     self.hass,
        #     [TrackTemplate(control_template, trigger_info["variables"])],
        #     template_listener,
        # )
        # unsub = info.async_remove

        # @callback
        # def async_remove():
        #     """Remove state listeners async."""
        #     unsub()
        #     # if delay_cancel:
        #     #     delay_cancel()

        # return async_remove
