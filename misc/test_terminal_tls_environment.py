"""Exercise the installed shell configuration without changing user files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "layout/usr/macOS/bin/configure_terminal_cli.sh"


class TerminalTLSConfiguration(unittest.TestCase):
    def test_preserves_user_configuration_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            rc = Path(td) / "Users/root/.bashrc"
            rc.parent.mkdir(parents=True)
            original = "# user configuration\nexport USER_SETTING=retained\n"
            rc.write_text(original)
            for _ in range(2):
                subprocess.run(["bash", str(INSTALLER), td], check=True,
                               capture_output=True, text=True)
            configured = rc.read_text()
            self.assertTrue(configured.startswith(original))
            self.assertEqual(configured.count("# MacWS: verified curl TLS backend v1"), 1)
            for override, expected in [(None, "openssl"), ("secure-transport", "secure-transport")]:
                env = os.environ.copy()
                env.pop("CURL_SSL_BACKEND", None)
                if override:
                    env["CURL_SSL_BACKEND"] = override
                result = subprocess.run(
                    ["bash", "-c", '. "$1"; printf "%s" "$CURL_SSL_BACKEND"', "test", str(rc)],
                    env=env, check=True, capture_output=True, text=True)
                self.assertEqual(result.stdout, expected)

    def test_cli_wrapper_defaults_and_preserves_arguments(self):
        source = (ROOT / "layout/usr/macOS/bin/run_bash.sh").read_text()
        prefix = source.split("/var/jb/usr/macOS/bin/launchdchrootexec", 1)[0]
        for override, expected in [(None, "openssl"), ("secure-transport", "secure-transport")]:
            env = os.environ.copy()
            env.pop("CURL_SSL_BACKEND", None)
            if override:
                env["CURL_SSL_BACKEND"] = override
            result = subprocess.run(["bash", "-c", prefix + '\nprintf "%s" "$CURL_SSL_BACKEND"'],
                                    env=env, check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, expected)
        self.assertTrue(source.rstrip().endswith('/bin/bash "$@"'))


if __name__ == "__main__":
    unittest.main()
