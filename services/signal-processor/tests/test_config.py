from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from signal_processor.config import ProcessorConfig


class ProcessorConfigTests(unittest.TestCase):
    def environment(self) -> dict[str, str]:
        return {
            "MQTT_HOST": "mqtt-broker",
            "MQTT_USERNAME": "processor",
            "MQTT_PASSWORD": "secret",
            "MQTT_TLS_CA_FILE": "/run/roadsense/mqtt/ca.crt",
            "PROCESSOR_MQTT_CLIENT_ID": "stable-processor-id",
        }

    def test_persistent_session_requires_nonempty_stable_client_id(self) -> None:
        values = self.environment()
        values["PROCESSOR_MQTT_CLIENT_ID"] = "   "
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(ValueError, "1-128 UTF-8 bytes"):
                ProcessorConfig.from_environment()

    def test_readiness_file_can_be_configured_for_container_probe(self) -> None:
        values = self.environment()
        values["PROCESSOR_READY_FILE"] = "/tmp/custom-processor-ready"
        values["PROCESSOR_STATE_FILE"] = "/tmp/custom-processor-state.sqlite3"
        with patch.dict(os.environ, values, clear=True):
            config = ProcessorConfig.from_environment()
        self.assertEqual(str(config.ready_file), "/tmp/custom-processor-ready")
        self.assertEqual(
            str(config.state_file), "/tmp/custom-processor-state.sqlite3"
        )


if __name__ == "__main__":
    unittest.main()
