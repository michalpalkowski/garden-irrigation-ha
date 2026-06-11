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

With firmware `0.4.0` or newer, the controller publishes retained identity to:

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
- OTA protocol helpers are included, but the Home Assistant update entity is not implemented in this initial release.
- The controller `device_id`, runtime `base_topic`, board, chip, firmware
  version, and capabilities come from signed firmware provisioning data exposed
  as retained MQTT identity.

## Entities

- Zone switches
- Zone manual duration numbers
- Zone scheduled duration numbers
- Zone schedule enabled switches
- Zone weekday switches
- Zone schedule time entities
- MQTT availability binary sensor
- Stop-all button
- Controller state, diagnostics, network, Wi-Fi, plan, zone state, and runtime sensors

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
`garden-irrigation-wifi`. For a different controller name, replace the generated
entity ID prefix before importing it.

## Current Limitations

- The integration does not automatically edit Home Assistant storage dashboards.
- Weather guard parity from the original project YAML package is not built into
  the integration scheduler yet.
- OTA update entities are not implemented yet.
- Runtime Wi-Fi/MQTT provisioning is not implemented in the integration yet;
  current firmware is still provisioned at build time.

## Development Checks

```sh
python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/manifest.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/strings.json >/dev/null
python3 -m compileall -q custom_components/garden_irrigation tests
python3 -m unittest tests.test_garden_irrigation_protocol
```
