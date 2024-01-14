"""The Priority Switch integration."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry, device_registry as dr
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
# Inside a component

# PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]
PLATFORMS: list[Platform] = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Priority Switch from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Use `hass.async_create_task` to avoid a circular dependency between the platform and the component
    # print(hass.data[DOMAIN][entry.entry_id])
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
    #     hass.data[DOMAIN].pop(entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    # TODO implement
    return True
