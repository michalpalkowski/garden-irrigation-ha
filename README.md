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

## MQTT Base Topic

During setup, enter the controller name, for example:

```text
xiao-esp32c6-1
```

The integration builds the default MQTT base topic as `garden/irrigation/<controller-name>`. Use the advanced custom MQTT base topic field only for non-standard firmware builds. The integration validates the topic by waiting for retained controller MQTT state before creating the config entry.

## Safety

- Zone start commands are explicit and bounded, for example `ON:900`.
- Commands are published with `retain=false`.
- Firmware remains the safety authority and must close valves locally when runtime expires.
- OTA protocol helpers are included, but the Home Assistant update entity is not implemented in this initial release.

## Initial Entities

- Zone switches
- Zone duration numbers
- Stop-all button
- Controller state and diagnostics sensors
- Zone state and runtime sensors

## Development Checks

```sh
python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/manifest.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/strings.json >/dev/null
python3 -m compileall -q custom_components/garden_irrigation tests
python3 -m unittest tests.test_garden_irrigation_protocol
```
