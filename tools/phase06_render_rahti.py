#!/usr/bin/env python3
"""Render non-secret OpenShift manifest templates. NEVER applies changes."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import sys
from pathlib import Path

IMAGE_KEYS = ("BROKER_IMAGE", "PROCESSOR_IMAGE", "ANALYZER_IMAGE", "API_IMAGE", "POSTGRES_IMAGE")
API_ROUTE_KEYS = ("API_PUBLIC_HOST", "VPS_EGRESS_CIDR")
MQTT_EXTERNAL_KEYS = ("VPS_EGRESS_CIDR",)
SETTING_KEYS = IMAGE_KEYS + API_ROUTE_KEYS
PRIVATE_TEMPLATES = ("core", "migrate", "apps")
IMAGE_RE = re.compile(r"^[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}$")
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SUBSTITUTION_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for index, original in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{index}: expected KEY=VALUE")
        name, value = line.split("=", 1)
        if name in values:
            raise ValueError(f"duplicate setting {name}")
        if name not in SETTING_KEYS:
            raise ValueError(f"unsupported setting {name}; no secrets are permitted")
        values[name] = value.strip()
    return values


def render(src: Path, dst: Path, settings: dict[str, str], selected: tuple[str, ...]) -> None:
    for key in selected:
        if not settings.get(key):
            raise ValueError(f"required setting {key} is missing")
    if selected in (API_ROUTE_KEYS, MQTT_EXTERNAL_KEYS):
        if "API_PUBLIC_HOST" in selected:
            name = "API_PUBLIC_HOST"
            if not HOST_RE.fullmatch(settings[name]) or "." not in settings[name]:
                raise ValueError(f"{name} must be a fully qualified DNS hostname")
        try:
            network = ipaddress.ip_network(settings["VPS_EGRESS_CIDR"], strict=True)
        except ValueError as error:
            raise ValueError(
                "VPS_EGRESS_CIDR must be an explicit canonical IPv4 CIDR; verify IP and routing"
            ) from error
        if network.version != 4:
            raise ValueError("VPS_EGRESS_CIDR must be an explicit IPv4 CIDR; verify IP and routing")
    else:
        for name in IMAGE_KEYS:
            if not IMAGE_RE.fullmatch(settings[name]):
                raise ValueError(f"{name} must be an immutable image@sha256:<64hex> reference")
    render_settings = dict(settings)
    render_settings["MIGRATION_ID"] = hashlib.sha256(
        settings.get("ANALYZER_IMAGE", "").encode("utf-8")
    ).hexdigest()[:12]
    content = src.read_text(encoding="utf-8")
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in render_settings or not render_settings[key]:
            raise ValueError(f"{src.name}: unresolved variable {key}")
        return render_settings[key]
    result = SUBSTITUTION_RE.sub(replace, content)
    if "REPLACE_" in result:
        raise ValueError(f"{src.name}: unresolved placeholder")
    dst.write_text(result, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", required=True, type=Path, help="non-secret images.env with pinned digests")
    parser.add_argument("--output-dir", required=True, type=Path, help="local destination (ignored if inside infrastructure/rahti/generated)")
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="render guarded API Route and MQTT LoadBalancer; still does NOT apply",
    )
    args = parser.parse_args()
    settings = load_settings(args.settings)
    source = Path(__file__).resolve().parents[1] / "infrastructure" / "rahti"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    templates: list[tuple[str, tuple[str, ...]]] = [
        (name, IMAGE_KEYS) for name in PRIVATE_TEMPLATES
    ]
    if args.include_external:
        templates.extend(
            (("routes", API_ROUTE_KEYS), ("mqtt-external", MQTT_EXTERNAL_KEYS))
        )
    for name, required in templates:
        render(source / f"{name}.yaml.tpl", args.output_dir / f"{name}.yaml", settings, required)
        print(f"rendered non-secret manifest: {args.output_dir / f'{name}.yaml'}")
    print("No remote changes performed. Review YAML before approval/deployment.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"render failed: {error}", file=sys.stderr)
        raise SystemExit(2)
