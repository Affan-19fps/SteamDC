from __future__ import annotations

import runpy
import sys
from unittest.mock import patch


class TestMain:
    def test_main_module_runs_cli_run(self):
        """__main__.py calls cli.run() when executed as a module."""
        with patch("steamdc.cli.run") as mock_run:
            with patch.object(sys, "argv", ["steamdc"]):
                runpy.run_module("steamdc", run_name="__main__")
                mock_run.assert_called_once()
