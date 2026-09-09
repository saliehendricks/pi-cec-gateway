"""Config flow for Raspberry Pi HDMI-CEC."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DOMAIN


class PiCecConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle discovery of a Pi CEC gateway."""

    VERSION = 1

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        host = discovery_info.host
        serial = discovery_info.properties.get("serialno", discovery_info.name)
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(
            title="HDMI CEC",
            data={CONF_HOST: host, CONF_PORT: discovery_info.port},
        )
