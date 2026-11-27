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
            self.assertIn("roadsense-processor-state", rendered)
            self.assertIn("PROCESSOR_REJECTED_TOMBSTONE_LIMIT", rendered)
            self.assertNotIn("local-load-balancer", rendered)
            migrate = (destination / "migrate.yaml").read_text()
            self.assertIn("generateName: roadsense-migrate-", migrate)
            self.assertIn("roadsense.io/migration-id:", migrate)
            self.assertNotIn("${MIGRATION_ID}", migrate)

    def test_mqtt_subscriber_deployments_use_recreate(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "apps.yaml"
            module.render(
                ROOT / "infrastructure" / "rahti" / "apps.yaml.tpl",
                output,
                self.settings(),
                module.IMAGE_KEYS,
            )
            deployments: dict[str, str] = {}
            for document in output.read_text().split("\n---\n"):
                if "kind: Deployment" not in document:
                    continue
                for name in ("signal-processor", "road-analyzer", "api"):
                    if f"  name: {name}\n" in document:
                        deployments[name] = document
            self.assertEqual(
                {"signal-processor", "road-analyzer", "api"}, set(deployments)
            )
            for name in ("signal-processor", "road-analyzer"):
                self.assertIn("  replicas: 1\n", deployments[name])
                self.assertIn("  strategy:\n    type: Recreate\n", deployments[name])

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

    def test_laptop_clients_use_loopback_port_forwards_without_dependencies(self):
        override = (
            ROOT / "infrastructure" / "compose" / "rahti-client.compose.yaml"
        ).read_text()
        self.assertIn("network_mode: host", override)
        self.assertIn("MQTT_HOST: localhost", override)
        self.assertIn("API_INTERNAL_URL: http://localhost:", override)
        self.assertIn("depends_on: !reset {}", override)
        self.assertIn("--server.address=127.0.0.1", override)
        self.assertNotIn("LoadBalancer", override)
        self.assertNotIn("kind: Route", override)

    def test_vps_external_settings_are_not_accepted_by_active_renderer(self):
        with tempfile.TemporaryDirectory() as temp:
            values = Path(temp) / "images.env"
            values.write_text("VPS_EGRESS_CIDR=198.51.100.5/32\n")
            with self.assertRaisesRegex(ValueError, "unsupported setting"):
                module.load_settings(values)

    def test_active_tooling_has_no_public_or_vps_stage(self):
        renderer = (ROOT / "tools" / "phase06_render_rahti.py").read_text()
        deployer = (ROOT / "tools" / "phase06_rahti.sh").read_text()
        preflight = (ROOT / "tools" / "phase06_preflight.sh").read_text()
        self.assertNotIn("include-external", renderer)
        self.assertNotIn("mqtt-external", renderer + deployer)
        self.assertNotIn("routes|", deployer)
        self.assertNotIn("vps)", preflight)

    def test_docker_build_context_excludes_sensitive_material(self):
        patterns = (ROOT / ".dockerignore").read_text()
        for pattern in (
            "**/.env",
            "**/*.env",
            "**/*.env.*",
            "**/*-password",
            "**/password_file",
            "**/*.key",
            "**/*.tar",
        ):
            self.assertIn(pattern, patterns)
        self.assertNotIn("!**/.env.example", patterns)
        self.assertIn("**/*.env", patterns)
        git_patterns = (ROOT / ".gitignore").read_text()
        self.assertIn("infrastructure/compose/rahti-client.env", git_patterns)


if __name__ == "__main__":
    unittest.main()
