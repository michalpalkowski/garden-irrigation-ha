"""Shared paths for source and HACS distribution contract tests."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SUPPORTED_COMPONENT_PATHS = (
    REPOSITORY_ROOT
    / "integrations"
    / "home-assistant"
    / "custom_components"
    / "garden_irrigation",
    REPOSITORY_ROOT / "custom_components" / "garden_irrigation",
)
_AVAILABLE_COMPONENT_PATHS = tuple(
    path for path in _SUPPORTED_COMPONENT_PATHS if (path / "manifest.json").is_file()
)

if len(_AVAILABLE_COMPONENT_PATHS) != 1:
    raise RuntimeError(
        "Expected exactly one Garden Irrigation component in a supported "
        f"repository layout, found: {_AVAILABLE_COMPONENT_PATHS}"
    )

COMPONENT_PATH = _AVAILABLE_COMPONENT_PATHS[0]
