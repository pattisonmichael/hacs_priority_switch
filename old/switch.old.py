"""Main Priority Switch Entity Class file."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CONTROL_STATE, CONF_INPUTS, DOMAIN, DOMAIN_FRIENDLY
from .priority_input import PriorityInput

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Example sensor based on a config entry."""
    _LOGGER.debug("Switch async_setup_entry")
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={},
        identifiers={(DOMAIN, entry.data["switch_name"])},
        manufacturer="Priority Switch",
        # suggested_area="Kitchen",
        name=entry.data.get("switch_name_friendly"),
        # model=entry.data.get('switch_name_friendly'),
        # sw_version="config.swversion",
        # hw_version="config.hwversion",
    )
    # device: ExampleDevice = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            PrioritySwitch(
                device,
                hass=hass,
                name=f"{DOMAIN_FRIENDLY} {device.name}",
                data=entry,
                async_add_entities=async_add_entities,
            )
        ]
    )
    # for inp in self._inputs:
    #     print(inp)
    _LOGGER.debug("Finished adding priority switch:\n%s", entry)


class PrioritySwitch(SwitchEntity):
    """Main Priority Switch Entity Class."""

    _unrecorded_attributes: frozenset({"control_state"})
    _attr_has_entity_name = True

    def __init__(
        self,
        device,
        hass: HomeAssistant,
        name: str,
        data: Any,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up the instance."""

        # self._device = device
        self._attr_device_info = device.dict_repr
        # self.entity_description = entity_description
        self._attr_name = name
        self._data = data.data
        self._attr_available = True  # This overrides the default
        self._attr_unique_id = f"{device.name}_{name}"
        self._attr_is_on = cv.boolean(self._data.get("enabled"))
        self._inputs = {}
        self.hass = hass
        self._active_input = None
        self._async_add_entities = async_add_entities

        # for val in self._data[CONF_INPUTS]:
        #     self.add_input(
        #         identifier=val,
        #         data=self._data[CONF_INPUTS][val],
        #         async_add_entities=async_add_entities,
        #     )
        # for val in self._inputs.values():
        #     _LOGGER.debug(val.control_state)

    def add_input(self, identifier, data, async_add_entities: AddEntitiesCallback):
        # Create a new PriorityInput and store it in the inputs dictionary
        self._inputs[identifier] = PriorityInput(
            hass=self.hass,
            parent=self,
            identifier=identifier,
            data=data,
            async_add_entities=async_add_entities,
        )

    def process_input_update(self, identifier):
        """Process update from Input."""
        # Process the data received from a PriorityInput
        _LOGGER.debug("Processing update from input %s", identifier)
        highest_priority_input = max(
            (obj for obj in self._inputs.values() if obj.control_state),
            key=lambda obj: obj.priority,
            default=None,  # This avoids a ValueError if no object meets the criteria
        )

        if highest_priority_input:
            # Do something with the top-priority object
            _LOGGER.debug(
                "The active Input with the highest priority is: %s",
                highest_priority_input,
            )
            self._active_input = highest_priority_input.priority
        else:
            self._active_input = None
            _LOGGER.debug("No active Inputs found.")
        if self.entity_id is None:
            _LOGGER.debug("no entity_is")
        else:
            self.async_write_ha_state()
        # Here you would implement your logic to handle the data
        # This could involve updating the state of the PrioritySwitch
        # or making decisions based on the priority of the input

    @property
    # def extra_state_attributes(self) -> Mapping[str, Any] | None:
    def extra_state_attributes(self):
        """Return additional attributes."""
        states = {
            "active_input": self._active_input
            if self._active_input is not None
            else "None"
        }
        for item in self._inputs.values():
            states.update({item.data["name"]: {ATTR_CONTROL_STATE: item.control_state}})
        return states

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        for val in self._data[CONF_INPUTS]:
            self.add_input(
                identifier=val,
                data=self._data[CONF_INPUTS][val],
                async_add_entities=self._async_add_entities,
            )
            self.async_add_entities = None
        for val in self._inputs.values():
            _LOGGER.debug(val.control_state)
        return

    async def async_will_remove_from_hass(self) -> None:
        pass


######################
# async def async_setup_entry(
#     hass: HomeAssistant,
#     entry: ConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     """Set up Example sensor based on a config entry."""
#     _LOGGER.debug("Switch async_setup_entry")
#     device_registry = dr.async_get(hass)

#     device = device_registry.async_get_or_create(
#         config_entry_id=entry.entry_id,
#         connections={},
#         identifiers={(DOMAIN, entry.data["switch_name"])},
#         manufacturer="Priority Switch",
#         # suggested_area="Kitchen",
#         name=entry.data.get("switch_name_friendly"),
#         # model=entry.data.get('switch_name_friendly'),
#         # sw_version="config.swversion",
#         # hw_version="config.hwversion",
#     )
#     # device: ExampleDevice = hass.data[DOMAIN][entry.entry_id]

#     async_add_entities(
#         [
#             PrioritySwirchSwitchEntity(
#                 device,
#                 name=f"{DOMAIN_FRIENDLY} {device.name}",
#                 type="switch",
#                 data=entry,
#             )
#         ]
#     )
#     inputs = []
#     for inputdata in entry.data["inputs"]:
#         inputs.append(
#             PrioritySwirchSwitchEntity(
#                 device,
#                 name=f"{DOMAIN_FRIENDLY} {device.name} {entry.data['inputs'][inputdata]['name']}",
#                 type="input",
#                 data=entry.data["inputs"][inputdata],
#             )
#         )
#     async_add_entities(inputs)
#     # async_add_entities(
#     #     ExampleSensorEntity(device, description)
#     #     for description in SENSORS
#     #     if description.exists_fn(device)
#     # )


# class PrioritySwirchSwitchEntity(SwitchEntity):
#     """Represent an Example sensor."""

#     # entity_description: PrioritySwitchSwitchEntityDescription
#     _data = None
#     _attr_has_entity_name = True
#     _attr_name = None
#     _type = None
#     _attr_unique_id = None
#     _attr_is_on = None
#     # _attr_entity_category = (
#     #     EntityCategory.DIAGNOSTIC
#     # )  # This will be common to all instances of ExampleSensorEntity

#     def __init__(self, device, name: str, type: str, data: Any) -> None:
#         """Set up the instance."""
#         self._device = device
#         # self.entity_description = entity_description
#         self._attr_name = name
#         self._data = data
#         self._type = type
#         self._attr_available = False  # This overrides the default
#         self._attr_unique_id = f"{device.name}_{name}"
#         if self._type == "switch":
#             self._attr_is_on = data.data.get("enabled", False)
#         elif self._type == "input":
#             self._attr_is_on = False
