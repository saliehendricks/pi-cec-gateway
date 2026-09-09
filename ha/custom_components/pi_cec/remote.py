"""Remote entity for a Raspberry Pi HDMI-CEC gateway."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([PiCecRemote(entry)])


class PiCecRemote(RemoteEntity):
    """Home Assistant remote backed by the Pi gateway HTTP API."""

    _attr_has_entity_name = True
    _attr_name = "Remote"
    _attr_should_poll = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._attr_unique_id = f"{DOMAIN}_{entry.unique_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": "HDMI CEC",
            "manufacturer": "Raspberry Pi",
            "model": "libCEC gateway",
        }
        self._is_on = False
        self._status: dict[str, Any] = {}

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_update(self) -> None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(f"http://{self._host}:{self._port}/api/status") as response:
                response.raise_for_status()
                self._status = await response.json()
                self._is_on = self._status.get("power") == "on"
                self._attr_available = True
        except (ClientError, OSError, KeyError, ValueError):
            self._attr_available = False

    async def _set_power(self, state: str) -> None:
        session = async_get_clientsession(self.hass)
        async with session.post(
            f"http://{self._host}:{self._port}/api/power", json={"state": state}
        ) as response:
            response.raise_for_status()
        self._is_on = state == "on"
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "active_source": self._status.get("active_source", "unknown"),
            "volume": self._status.get("volume", "unknown"),
            "mute": self._status.get("mute", "unknown"),
            "playback": self._status.get("playback", "unknown"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_power("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_power("off")

    async def async_send_command(self, command: list[str], **kwargs: Any) -> None:
        session = async_get_clientsession(self.hass)
        for item in command:
            payload: dict[str, str]
            if item.startswith("source:"):
                payload = {"command": "source", "physical_address": item.split(":", 1)[1]}
            else:
                payload = {"command": item}
            async with session.put(
                f"http://{self._host}:{self._port}/api/command", json=payload
            ) as response:
                response.raise_for_status()
