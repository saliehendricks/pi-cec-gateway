# Raspberry Pi HDMI-CEC gateway

The Pi runs `libCEC` and advertises an HTTP API over mDNS. The Home Assistant
custom integration discovers that service and creates a native `remote` entity.

## Home Assistant installation

Copy `ha/custom_components/pi_cec` into the Home Assistant configuration:

```text
/config/custom_components/pi_cec
```

Make sure the `zeroconf` integration is enabled. Restart Home Assistant. The
Pi should appear under Settings > Devices & services as `HDMI CEC`.

The resulting entity supports `remote.turn_on` and `remote.turn_off`.
