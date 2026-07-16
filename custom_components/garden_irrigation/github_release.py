"""Typed parsing for public or private GitHub firmware releases."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .protocol import ProtocolError

GITHUB_API_ORIGIN = "https://api.github.com"


@dataclass(frozen=True)
class GithubReleaseAssets:
    """Authenticated API URLs for one firmware release."""

    tag_name: str
    manifest_url: str
    image_urls: dict[str, str]

    def image_url(self, filename: str) -> str:
        """Return the exact image asset required by a validated manifest."""
        try:
            return self.image_urls[filename]
        except KeyError as exc:
            raise ProtocolError(f"GitHub release is missing asset {filename}") from exc


def latest_release_url(repository: str) -> str:
    """Build the GitHub API URL for a validated owner/repository value."""
    return f"{GITHUB_API_ORIGIN}/repos/{repository}/releases/latest"


def parse_release_assets(payload: object) -> GithubReleaseAssets:
    """Validate a GitHub release response and locate firmware assets."""
    if not isinstance(payload, dict):
        raise ProtocolError("GitHub release response must be an object")
    tag_name = payload.get("tag_name")
    assets = payload.get("assets")
    if not isinstance(tag_name, str) or not tag_name:
        raise ProtocolError("GitHub release tag_name is required")
    if not isinstance(assets, list):
        raise ProtocolError("GitHub release assets are required")

    manifest_url: str | None = None
    image_urls: dict[str, str] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ProtocolError("GitHub release asset must be an object")
        name = asset.get("name")
        api_url = asset.get("url")
        if not isinstance(name, str) or not name:
            raise ProtocolError("GitHub release asset name is required")
        if not isinstance(api_url, str) or not _is_github_asset_api_url(api_url):
            raise ProtocolError("GitHub release asset URL is invalid")
        if name.endswith(".manifest.json"):
            if manifest_url is not None:
                raise ProtocolError("GitHub release has multiple OTA manifests")
            manifest_url = api_url
        elif name.endswith(".bin"):
            image_urls[name] = api_url

    if manifest_url is None:
        raise ProtocolError("GitHub release is missing an OTA manifest")
    if not image_urls:
        raise ProtocolError("GitHub release is missing a firmware image")
    return GithubReleaseAssets(
        tag_name=tag_name,
        manifest_url=manifest_url,
        image_urls=image_urls,
    )


def _is_github_asset_api_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "api.github.com"
        and parsed.path.startswith("/repos/")
        and "/releases/assets/" in parsed.path
        and not parsed.query
        and not parsed.fragment
    )
