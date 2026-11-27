from __future__ import annotations

import os
import tempfile
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
    def test_default_vibration_threshold_rule(self) -> None:
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

    def test_direct_and_file_password_are_mutually_exclusive(self) -> None:
        env = {**BASE_ENV, "POSTGRES_PASSWORD_FILE": "/password"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "only one"):
                AnalyzerConfig.from_environment()

    def test_password_file_is_read_each_time_and_falls_back_during_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current = os.path.join(directory, "password")
            previous = os.path.join(directory, "password.previous")
            with open(current, "w", encoding="utf-8") as stream:
                stream.write("current\n")
            with open(previous, "w", encoding="utf-8") as stream:
                stream.write("fallback\n")
            env = {key: value for key, value in BASE_ENV.items() if key != "POSTGRES_PASSWORD"}
            env.update({"POSTGRES_PASSWORD_FILE": current,
                        "POSTGRES_PREVIOUS_PASSWORD_FILE": previous})
            with patch.dict(os.environ, env, clear=True):
                config = AnalyzerConfig.from_environment()
            self.assertEqual(config.postgres_password_candidates(), ("current", "fallback"))
            with open(current, "w", encoding="utf-8") as stream:
                stream.write("rotated\n")
            self.assertEqual(config.postgres_password_candidates(), ("rotated", "fallback"))

    def test_rule_version_and_topics_are_validated(self) -> None:
        for env_update in (
            {"ANALYZER_RULE_VERSION": "Rule v1"},
            {"MQTT_FEATURE_TOPIC": "roadsense/+/features"},
            {"MQTT_FEATURE_TOPIC": "roadsense/v1/events"},
        ):
            with self.subTest(env_update=env_update):
                with patch.dict(os.environ, {**BASE_ENV, **env_update}, clear=True):
                    with self.assertRaises(ValueError):
                        AnalyzerConfig.from_environment()


if __name__ == "__main__":
    unittest.main()
