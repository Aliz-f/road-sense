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

SECRET_SOURCE = ROOT / "tools" / "phase06_validate_secret_files.py"
secret_spec = importlib.util.spec_from_file_location("phase06_secrets", SECRET_SOURCE)
secret_module = importlib.util.module_from_spec(secret_spec)
assert secret_spec and secret_spec.loader
secret_spec.loader.exec_module(secret_module)


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
            documents: list[str] = []
            for path in destination.glob("*.yaml"):
                documents.extend(path.read_text().split("\n---\n"))
            self.assertTrue(documents)
            self.assertTrue(
                all("apiVersion:" in item and "kind:" in item for item in documents)
            )

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

    def test_cidr_rejects_invalid_octets_and_noncanonical_network(self):
        options = self.settings() | {
            "MQTT_PUBLIC_HOST": "mqtt.example.org",
            "API_PUBLIC_HOST": "api.example.org",
            "VPS_EGRESS_CIDR": "999.51.100.5/32",
        }
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "canonical IPv4"):
                module.render(
                    ROOT / "infrastructure" / "rahti" / "routes.yaml.tpl",
                    Path(temp) / "routes.yaml",
                    options,
                    module.ROUTE_KEYS,
                )

    def test_rahti_security_persistence_and_migration_controls_are_rendered(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            for name in ("core", "migrate", "apps"):
                module.render(
                    ROOT / "infrastructure" / "rahti" / f"{name}.yaml.tpl",
                    destination / f"{name}.yaml",
                    self.settings(),
                    module.IMAGE_KEYS,
                )
            rendered = "\n".join(path.read_text() for path in destination.glob("*.yaml"))
            self.assertNotIn("RuntimeDefault", rendered)
            self.assertIn("rahti-custom-seccomp.json", rendered)
            self.assertIn("verify-mqtt-persistence-writable", rendered)
            self.assertIn("signal_processor.health", rendered)
            migrate = (destination / "migrate.yaml").read_text()
            self.assertIn("generateName: roadsense-migrate-", migrate)
            self.assertIn("roadsense.io/migration-id:", migrate)
            self.assertNotIn("${MIGRATION_ID}", migrate)

    def test_postgres_secret_bytes_match_environment_and_file_consumers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "mqtt-password").write_bytes(b"mqtt-secret")
            (root / "postgres-password").write_bytes(b"postgres-secret")
            (root / "password_file").write_bytes(b"roadsense-remote:$7$hashed\n")
            for name in ("ca.crt", "server.crt", "server.key"):
                (root / name).write_text("placeholder")
            secret_module.validate(root)
            (root / "postgres-password").write_bytes(b"postgres-secret\n")
            with self.assertRaisesRegex(ValueError, "newline-free"):
                secret_module.validate(root)

        core = (ROOT / "infrastructure" / "rahti" / "core.yaml.tpl").read_text()
        apps = (ROOT / "infrastructure" / "rahti" / "apps.yaml.tpl").read_text()
        migrate = (ROOT / "infrastructure" / "rahti" / "migrate.yaml.tpl").read_text()
        self.assertIn("secretKeyRef: {name: roadsense-postgres-auth, key: password}", core)
        self.assertGreaterEqual((apps + migrate).count("{key: password, path: password}"), 3)

    def test_vps_dashboard_does_not_receive_replay_credentials(self):
        compose = (ROOT / "infrastructure" / "vps" / "compose.yaml").read_text()
        dashboard = (ROOT / "infrastructure" / "vps" / "dashboard.env.example").read_text()
        replay = (ROOT / "infrastructure" / "vps" / "sensor-replay.env.example").read_text()
        self.assertIn("dashboard.env", compose)
        self.assertIn("sensor-replay.env", compose)
        self.assertNotIn("MQTT_PASSWORD", dashboard)
        self.assertNotIn("API_INTERNAL_URL", replay)

    def test_docker_build_context_excludes_sensitive_material(self):
        patterns = (ROOT / ".dockerignore").read_text()
        for pattern in ("**/.env", "**/*-password", "**/password_file", "**/*.key", "**/*.tar"):
            self.assertIn(pattern, patterns)


if __name__ == "__main__":
    unittest.main()
