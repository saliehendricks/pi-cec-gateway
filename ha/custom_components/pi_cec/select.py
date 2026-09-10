"""HDMI source selector."""

from __future__ import annotations

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity

from . import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([CecSourceSelect(hass, entry)])


class CecSourceSelect(SelectEntity):
    """Select the active HDMI input through CEC."""

    _attr_has_entity_name = True
    _attr_name = "HDMI Source"
    _attr_options = []
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._attr_unique_id = f"{entry.unique_id}_source"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": "HDMI CEC",
            "manufacturer": "Raspberry Pi",
            "model": "libCEC gateway",
        }
        self._attr_current_option = None
        self._sources: dict[str, str] = {}

    async def async_update(self) -> None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(f"http://{self._host}:{self._port}/api/status") as response:
                response.raise_for_status()
                physical = (await response.json()).get("active_source", "")
                self._attr_available = True
            async with session.get(f"http://{self._host}:{self._port}/api/devices") as response:
                response.raise_for_status()
                devices = (await response.json()).get("devices", [])
                self._sources = {
                    f"HDMI {device['address'][0]} - {device.get('osd_string', device['name'])}": device["address"].replace(".", "")
                    for device in devices
                    if device.get("address", "")[:1].isdigit()
                    and device.get("address", "").count(".") == 3
                }
                self._attr_options = list(self._sources)
                self._attr_current_option = next(
                    (name for name, address in self._sources.items() if address == physical.removeprefix("0x")),
                    None,
                )
        except (ClientError, OSError, KeyError, ValueError):
            self._attr_available = False

    async def async_select_option(self, option: str) -> None:
        session = async_get_clientsession(self.hass)
        async with session.put(
            f"http://{self._host}:{self._port}/api/command",
            json={"command": "source", "physical_address": self._sources[option]},
        ) as response:
            response.raise_for_status()
        self._attr_current_option = option
        self.async_write_ha_state()
