"""Bootstrap tests use fake runners; never install packages or open the GUI."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'bootstrap.py'


def load_bootstrap():
    spec = importlib.util.spec_from_file_location('coach_bootstrap', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.bootstrap = load_bootstrap()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'requirements.txt').write_text('Pillow>=10,<13\nmss>=9,<11\n', encoding='utf-8')
        self.python = self.bootstrap.venv_python(self.root / '.venv', 'nt' if self.bootstrap.os.name == 'nt' else 'posix')

    def fake_runner(self, commands):
        def run(args, **kwargs):
            commands.append(list(map(str, args)))
            if args[1:4] == ['-m', 'venv', str(self.root / '.venv')]:
                self.python.parent.mkdir(parents=True, exist_ok=True)
                self.python.touch()
            elif args[1:3] == ['-c', self.bootstrap.VERSION_PROBE]:
                return mock.Mock(returncode=0, stdout=self.bootstrap.runtime_fingerprint(), stderr='')
            elif args[1:3] == ['-c', self.bootstrap.DIST_PROBE]:
                return mock.Mock(returncode=0, stdout='ok', stderr='')
            return mock.Mock(returncode=0, stdout='', stderr='')
        return run

    def test_creates_local_venv_then_installs_from_project_requirements(self):
        commands = []
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=self.fake_runner(commands)):
            exe = self.bootstrap.ensure_environment(self.root)
        self.assertEqual(exe, self.python)
        self.assertTrue(any(cmd[1:3] == ['-m', 'venv'] for cmd in commands))
        self.assertTrue(any(cmd[0] == str(self.python) and cmd[1:4] == ['-m', 'pip', 'install'] for cmd in commands))
        self.assertTrue((self.root / '.venv' / '.coach-deps.json').is_file())

    def test_second_start_skips_pip_when_installed_packages_match(self):
        commands = []
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=self.fake_runner(commands)):
            self.bootstrap.ensure_environment(self.root)
            commands.clear()
            self.bootstrap.ensure_environment(self.root)
        self.assertFalse(any(cmd[1:4] == ['-m', 'pip', 'install'] for cmd in commands))

    def test_requirements_change_reinstalls(self):
        commands = []
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=self.fake_runner(commands)):
            self.bootstrap.ensure_environment(self.root)
            (self.root / 'requirements.txt').write_text('Pillow>=11,<13\n', encoding='utf-8')
            commands.clear()
            self.bootstrap.ensure_environment(self.root)
        self.assertTrue(any(cmd[1:4] == ['-m', 'pip', 'install'] for cmd in commands))

    def test_failed_install_does_not_mark_complete(self):
        commands = []
        runner = self.fake_runner(commands)
        def fail_install(args, **kwargs):
            if args[1:4] == ['-m', 'pip', 'install']:
                raise self.bootstrap.subprocess.CalledProcessError(1, args)
            return runner(args, **kwargs)
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=fail_install):
            with self.assertRaises(self.bootstrap.BootstrapError):
                self.bootstrap.ensure_environment(self.root)
        self.assertFalse((self.root / '.venv' / '.coach-deps.json').exists())

    def test_invalid_existing_venv_does_not_fall_back_to_global_python(self):
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        def stale(args, **kwargs):
            return mock.Mock(returncode=1, stdout='', stderr='broken')
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=stale):
            with self.assertRaises(self.bootstrap.BootstrapError):
                self.bootstrap.ensure_environment(self.root)

    def test_missing_installed_package_triggers_repair(self):
        commands = []
        runner = self.fake_runner(commands)
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=runner):
            self.bootstrap.ensure_environment(self.root)
        commands.clear()
        def missing(args, **kwargs):
            if args[1:3] == ['-c', self.bootstrap.DIST_PROBE]:
                # Probe fails on the first restart, succeeds after pip repairs packages.
                if not any(c[1:4] == ['-m', 'pip', 'install'] for c in commands):
                    commands.append(list(map(str, args)))
                    return mock.Mock(returncode=2, stdout='', stderr='missing')
            return runner(args, **kwargs)
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=missing):
            self.bootstrap.ensure_environment(self.root)
        self.assertTrue(any(c[1:4] == ['-m', 'pip', 'install'] for c in commands))

    def test_main_prepare_never_launches_coach(self):
        with mock.patch.object(self.bootstrap, 'ensure_environment', return_value=self.python), \
             mock.patch.object(self.bootstrap.subprocess, 'run') as call:
            self.assertEqual(self.bootstrap.main(['--prepare']), 0)
            call.assert_not_called()

    def test_bootstrap_messages_support_cp1252_console(self):
        commands = []
        output = io.TextIOWrapper(io.BytesIO(), encoding='cp1252', write_through=True)
        with mock.patch.object(self.bootstrap.subprocess, 'run', side_effect=self.fake_runner(commands)), \
             mock.patch.object(self.bootstrap.sys, 'stdout', output):
            self.bootstrap.ensure_environment(self.root)

    def test_venv_python_paths_are_platform_specific(self):
        p = Path('/project/.venv')
        self.assertEqual(self.bootstrap.venv_python(p, 'nt'), p / 'Scripts' / 'python.exe')
        self.assertEqual(self.bootstrap.venv_python(p, 'posix'), p / 'bin' / 'python')


if __name__ == '__main__':
    unittest.main()