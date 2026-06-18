import os
import unittest
from unittest.mock import patch

import data.sql.db_config as db_config
from data.sql.db_config import get_db_config, load_db_config


class TestDbConfig(unittest.TestCase):
    def test_load_db_config_reads_environment(self):
        with patch.dict(os.environ, {
            "TRADING_DB_HOST": "dbhost",
            "TRADING_DB_PORT": "3307",
            "TRADING_DB_USER": "tester",
            "TRADING_DB_PASSWORD": "secret",
            "TRADING_DB_DATABASE": "analytics",
        }, clear=False):
            config, source = load_db_config()

        self.assertEqual(config["host"], "dbhost")
        self.assertEqual(config["port"], 3307)
        self.assertEqual(config["user"], "tester")
        self.assertEqual(config["password"], "secret")
        self.assertEqual(config["database"], "analytics")
        self.assertIn("environment", source)

    def test_get_db_config_uses_safe_defaults_when_env_missing(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(db_config, "_ENV_CANDIDATE_FILES", ()),
        ):
            config = get_db_config()

        self.assertEqual(config["host"], "localhost")
        self.assertEqual(config["port"], 3306)
        self.assertEqual(config["user"], "root")
        self.assertEqual(config["password"], "")
        self.assertEqual(config["database"], "trading_data")
