from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from road_analyzer.config import AnalyzerConfig


BASE_ENV = {
    "MQTT_HOST": "mqtt-broker",
    "MQTT_USERNAME": "user",
    "MQTT_PASSWORD": "password",
    "MQTT_TLS_CA_FILE": "/ca.crt",
    "POSTGRES_HOST": "postgres",
    "POSTGRES_DB": "roadsense",
    "POSTGRES_USER": "roadsense",
    "POSTGRES_PASSWORD": "database-password",
}


class ConfigTests(unittest.TestCase):
    def test_defaults_are_documented_phase04_rule(self) -> None:
        with patch.dict(os.environ, BASE_ENV, clear=True):
            config = AnalyzerConfig.from_environment()
        self.assertEqual(config.vibration_rms_threshold_mg, 100.0)
        self.assertEqual(config.rule_version, "roadsense-high-vibration-rms-v1-t100")
        self.assertEqual(config.event_topic, "roadsense/v1/events")

    def test_threshold_must_be_finite_and_positive(self) -> None:
        for value in ("0", "-1", "nan", "inf", "not-a-number"):
            with self.subTest(value=value):
                env = {**BASE_ENV, "ANALYZER_VIBRATION_RMS_THRESHOLD_MG": value}
                with patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(ValueError):
                        AnalyzerConfig.from_environment()

    def test_database_password_is_required(self) -> None:
        env = {**BASE_ENV, "POSTGRES_PASSWORD": ""}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "POSTGRES_PASSWORD"):
                AnalyzerConfig.from_environment()


if __name__ == "__main__":
    unittest.main()
