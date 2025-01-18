"""Support for switches which integrates with other components."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
import logging
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, DOMAIN_FRIENDLY
from collections.abc import Callable
from dataclasses import dataclass

# from example import ExampleDevice, ExampleException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class PrioritySwitchSwitchEntityDescription(SwitchEntityDescription):
    """Describes Priority Switch entity."""

    _LOGGER.debug("Class PrioritySwitchSwitchEntityDescription")
    # exists_fn: Callable[[ExampleDevice], bool] = lambda _: True


# value_fn: Callable[[ExampleDevice], StateType]


# SENSORS: tuple[PrioritySwitchSwitchEntityDescription, ...] = (
#     PrioritySwitchSwitchEntityDescription(
#         key="estimated_current",
#         # native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
#         # device_class=SensorDeviceClass.CURRENT,
#         # state_class=SensorStateClass.MEASUREMENT,
#         value_fn=lambda device: device.power,
#         exists_fn=lambda device: bool(device.max_power),
#     ),
# )


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
            PrioritySwirchSwitchEntity(
                device,
                name=f"{DOMAIN_FRIENDLY} {device.name}",
                type="switch",
                data=entry,
            )
        ]
    )
    inputs = []
    for inputdata in entry.data["inputs"]:
        inputs.append(
            PrioritySwirchSwitchEntity(
                device,
                name=f"{DOMAIN_FRIENDLY} {device.name} {entry.data['inputs'][inputdata]['name']}",
                type="input",
                data=entry.data["inputs"][inputdata],
            )
        )
    async_add_entities(inputs)
    # async_add_entities(
    #     ExampleSensorEntity(device, description)
    #     for description in SENSORS
    #     if description.exists_fn(device)
    # )


class PrioritySwirchSwitchEntity(SwitchEntity):
    """Represent an Example sensor."""

    # entity_description: PrioritySwitchSwitchEntityDescription
    _data = None
    _attr_has_entity_name = True
    _attr_name = None
    _type = None
    _attr_unique_id = None
    _attr_is_on = None
    # _attr_entity_category = (
    #     EntityCategory.DIAGNOSTIC
    # )  # This will be common to all instances of ExampleSensorEntity

    def __init__(self, device, name: str, type: str, data: Any) -> None:
        """Set up the instance."""
        self._device = device
        # self.entity_description = entity_description
        self._attr_name = name
        self._data = data
        self._type = type
        self._attr_available = False  # This overrides the default
        self._attr_unique_id = f"{device.name}_{name}"
        if self._type == "switch":
            self._attr_is_on = data.data.get("enabled", False)
        elif self._type == "input":
            self._attr_is_on = False

    async def async_update(self) -> None:
        """Update entity state."""
        # try:
        #     self._device.update()
        # except:
        #     if self.available:  # Read current state, no need to prefix with _attr_
        #         _LOGGER.warning("Update failed for %s", self.entity_id)
        #     self._attr_available = False  # Set property value
        #     return
        self._attr_available = True
        # We don't need to check if device available here
        # self._attr_native_value = self.entity_description.value_fn(self._device)  # U
        # self._attr_state = "enabled"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        return

    async def async_will_remove_from_hass(self) -> None:
        pass
