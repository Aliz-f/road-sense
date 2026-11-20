"""Offline unit checks of Phase 06 render safeguards; NO remote resources."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "phase06_render_rahti.py"
spec = importlib.util.spec_from_file_location("phase06_render", SOURCE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class Phase06RenderTests(unittest.TestCase):
    def settings(self):
        return {
            name: f"ghcr.io/example/roadsense-{name.lower()}@sha256:{'a' * 64}"
            for name in module.IMAGE_KEYS
        }

    def test_all_private_manifests_render_without_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            for name in ("core", "migrate", "apps"):
                module.render(
                    ROOT / "infrastructure" / "rahti" / f"{name}.yaml.tpl",
                    destination / f"{name}.yaml",
                    self.settings(),
                    module.IMAGE_KEYS,
                )
                content = (destination / f"{name}.yaml").read_text()
                self.assertNotIn("${", content)
                self.assertNotIn("REPLACE_", content)
            self.assertIn("kind: PersistentVolumeClaim", (destination / "core.yaml").read_text())
            self.assertNotIn("kind: Route", (destination / "core.yaml").read_text())

    def test_image_tags_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            options = self.settings()
            options["API_IMAGE"] = "ghcr.io/example/api:latest"
            with self.assertRaisesRegex(ValueError, "immutable"):
                module.render(
                    ROOT / "infrastructure" / "rahti" / "apps.yaml.tpl",
                    Path(temp) / "apps.yaml",
                    options,
                    module.IMAGE_KEYS,
                )

    def test_unexpected_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            values = Path(temp) / "images.env"
            values.write_text("POSTGRES_PASSWORD=secret-value\n")
            with self.assertRaisesRegex(ValueError, "unsupported setting"):
                module.load_settings(values)

    def test_routes_require_hostnames_and_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            options = self.settings() | {
                "MQTT_PUBLIC_HOST": "mqtt.example.org",
                "API_PUBLIC_HOST": "api.example.org",
                "VPS_EGRESS_CIDR": "198.51.100.5/32",
            }
            output = Path(temp) / "routes.yaml"
            module.render(
                ROOT / "infrastructure" / "rahti" / "routes.yaml.tpl",
                output,
                options,
                module.ROUTE_KEYS,
            )
            content = output.read_text()
            self.assertIn("passthrough", content)
            self.assertIn("198.51.100.5/32", content)
            options["VPS_EGRESS_CIDR"] = ""
            with self.assertRaisesRegex(ValueError, "required"):
                module.render(
                    ROOT / "infrastructure" / "rahti" / "routes.yaml.tpl",
                    output,
                    options,
                    module.ROUTE_KEYS,
                )


if __name__ == "__main__":
    unittest.main()
