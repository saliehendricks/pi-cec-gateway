"""CEC status sensors."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.sensor import SensorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    session = async_get_clientsession(hass)

    async def fetch_status() -> dict[str, Any]:
        async with session.get(
            f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/api/status"
        ) as response:
            response.raise_for_status()
            return await response.json()

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name="CEC status",
        update_method=fetch_status,
        update_interval=timedelta(seconds=10),
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [
            CecSensor(coordinator, entry, "active_source", "Active HDMI Source"),
            CecSensor(coordinator, entry, "volume", "Volume"),
            CecSensor(coordinator, entry, "mute", "Mute"),
            CecSensor(coordinator, entry, "playback", "Playback"),
        ]
    )


class CecSensor(CoordinatorEntity, SensorEntity):
    """A value read from the Pi CEC gateway."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": "HDMI CEC",
            "manufacturer": "Raspberry Pi",
            "model": "libCEC gateway",
        }

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self._key, "unknown")
