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
- The update entity exposes installed firmware metadata from MQTT. Firmware
  installation still uses the signed OTA tooling until a trusted release
  manifest source is wired into the Home Assistant UI.
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

Open `Settings -> Devices & services -> Garden Irrigation -> Configure` and set
the Home Assistant weather entity, for example:

```text
weather.forecast_dom
```

When configured, scheduled watering is blocked when the weather entity is
unavailable, current humidity is at or above the configured humidity threshold,
or the hourly forecast exceeds the configured rain probability or precipitation
threshold. Leave the weather entity empty to run schedules without weather-based
blocking.

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
  after the SoftAP claim flow is stable on hardware.

## Development Checks

```sh
python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/manifest.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/strings.json >/dev/null
find tests/fixtures -name '*.json' -print0 | xargs -0 -r -n1 python3 -m json.tool >/dev/null
python3 -m compileall -q custom_components/garden_irrigation tests
python3 -m unittest discover -s tests
```
