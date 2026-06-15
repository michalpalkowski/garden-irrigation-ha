# Garden Irrigation Home Assistant Integration

Home Assistant custom integration for the Garden Irrigation Wi-Fi/MQTT controller.

## Install with HACS

1. Open HACS in Home Assistant.
2. Open the top-right menu and choose `Custom repositories`.
3. Add this repository URL:

   ```text
   https://github.com/michalpalkowski/garden-irrigation-ha
   ```

4. Select category `Integration`.
5. Install `Garden Irrigation`.
6. Restart Home Assistant.
7. Add the integration from `Settings -> Devices & services -> Add integration`.

## Discovery And Identity

With firmware that supports `garden-irrigation-device/v1`, the controller
publishes retained identity to:

```text
garden/irrigation/discovery/<device_id>
<base_topic>/identity
```

Home Assistant can propose the integration automatically when the controller is
already online on MQTT. Confirm the discovered controller in
`Settings -> Devices & services`.

For manual setup, enter the stable controller device ID, for example:

```text
xiao-esp32c6-1
```

The integration builds the default runtime MQTT base topic as
`garden/irrigation/<device_id>`. Use the advanced custom MQTT base topic field
only when firmware was provisioned with a different base topic. Manual setup
validates the retained `<base_topic>/identity` payload before creating the
config entry.

## Safety

- Zone start commands are explicit and bounded, for example `ON:900`.
- Commands are published with `retain=false`.
- Firmware remains the safety authority and must close valves locally when runtime expires.
- Zone duration numbers are Home Assistant manual start durations. The current
  production Wi-Fi firmware does not publish `zone/N/duration_minutes`; the
  integration sends the selected value directly as `ON:<seconds>`.
- Schedule entities are Home Assistant owned, disabled by default, and use the
  same bounded command path as manual starts.
- The update entity exposes installed firmware metadata from MQTT and can read a
  trusted HTTPS OTA manifest for latest-version metadata. Firmware installation
  still uses the signed OTA tooling until the HA install path is
  hardware-verified.
- The controller `device_id`, runtime `base_topic`, board, chip, firmware
  version, and capabilities come from validated firmware identity exposed as
  retained MQTT payloads.

## Entities

- Zone switches
- Zone manual duration numbers
- Zone scheduled duration numbers
- Zone schedule enabled switches
- Zone weekday switches
- Zone schedule time entities
- Weather guard threshold numbers
- MQTT availability binary sensor
- Stop-all button
- Controller state, diagnostics, network, Wi-Fi, automation decision, plan, zone
  state, and runtime sensors

## Weather Guard

Open `Settings -> Devices & services -> Garden Irrigation -> Configure`.

Set the Home Assistant weather entity, for example:

```text
weather.forecast_dom
```

When configured, scheduled watering is blocked when the weather entity is
unavailable, current humidity is at or above the configured humidity threshold,
or the hourly forecast exceeds the configured rain probability or precipitation
threshold. Leave the weather entity empty to run schedules without weather-based
blocking.

## Firmware Metadata

The same options screen accepts an optional `ota_manifest_url`. Use a full HTTPS
URL to a `garden-ota-manifest/v1` JSON manifest.

When configured, the firmware update entity shows latest-version metadata and
validates that the manifest board/chip matches the controller. The integration
does not install firmware from Home Assistant yet; signed OTA installation stays
in the external tooling until the HA install path has been tested on real XIAO
ESP32-C6 hardware.

## Claim Contract

The integration includes typed helpers for the HA-assisted claim contract and
the firmware SoftAP form payload. The current production-supported claim path is
still the device SoftAP page at:

```text
http://192.168.4.1/
```

One-click claim from Home Assistant remains gated on hardware validation of the
full SoftAP round trip.

## Services

- `garden_irrigation.start_zone`
- `garden_irrigation.stop_zone`
- `garden_irrigation.stop_all`

When only one controller is configured, services can be called without
`device_id` or `entry_id`. With multiple controllers, pass the controller name
as `device_id`.

## Dashboard Template

The repository includes:

```text
dashboards/garden-irrigation-view.yaml
```

It is a Lovelace view template for the example controller name
`xiao-esp32c6-1`. For a different controller name, replace the generated
entity ID prefix before importing it.

## Current Limitations

- The integration does not automatically edit Home Assistant storage dashboards.
- Firmware OTA installation remains in external signed OTA tooling for now.
- Runtime Wi-Fi/MQTT provisioning is firmware-backed; HA claim UI is planned
  after the SoftAP claim flow is validated on hardware.

## Development Checks

```sh
scripts/ha-integration-release-check.sh
```
