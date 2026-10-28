"""Greeter backup/rollback regressions using only temporary files and mocked tools."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_greeter', REPO / 'docs/install-greeter.py')
greeter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(greeter)


class GreeterConfiguration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'etc/greetd/config.toml'
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(b'previous greeter config')
        self.config.chmod(0o640)
        self.css = self.config.with_name('gtkgreet.css')
        self.manager = self.root / 'etc/systemd/system/display-manager.service'
        self.manager.parent.mkdir(parents=True)
        self.manager.symlink_to('/usr/lib/systemd/system/gdm.service')
        self.backups = self.root / 'backups'
        self.items = [(self.config, b'new config', 0o644), (self.css, b'new CSS', 0o644)]
        for target, value in [('BACKUPS', self.backups), ('DISPLAY_MANAGER', self.manager)]:
            context = patch.object(greeter, target, value)
            context.start()
            self.addCleanup(context.stop)
        for function in ('fchown', 'chown'):
            context = patch.object(greeter.os, function)
            context.start()
            self.addCleanup(context.stop)

    def test_success_backs_up_config_and_enables_without_stopping_current_session(self):
        with patch.object(greeter.subprocess, 'run') as run:
            backup = greeter.configure(self.items)
        self.assertEqual(self.config.read_bytes(), b'new config')
        self.assertEqual(self.css.read_bytes(), b'new CSS')
        saved = backup / self.config.relative_to('/')
        self.assertEqual(saved.read_bytes(), b'previous greeter config')
        self.assertEqual(saved.stat().st_mode & 0o777, 0o640)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads((backup / 'previous-display-manager.json').read_text()),
                         '/usr/lib/systemd/system/gdm.service')
        self.assertEqual(run.call_args.args[0], ['systemctl', 'enable', '--force', 'greetd.service'])
        for call in run.call_args_list:
            self.assertFalse({'--now', 'stop', 'restart', 'start'} & set(call.args[0]))

    def test_enable_failure_restores_files_permissions_and_previous_manager(self):
        def execute(args, **kwargs):
            if args[:2] == ['systemctl', 'enable']:
                self.manager.unlink()
                self.manager.symlink_to('/usr/lib/systemd/system/greetd.service')
                raise subprocess.CalledProcessError(1, args)
        with patch.object(greeter.subprocess, 'run', side_effect=execute):
            with self.assertRaises(subprocess.CalledProcessError):
                greeter.configure(self.items)
        self.assertEqual(self.config.read_bytes(), b'previous greeter config')
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        self.assertFalse(self.css.exists())
        self.assertEqual(os.readlink(self.manager), '/usr/lib/systemd/system/gdm.service')

    def test_backup_failure_happens_before_any_configuration_or_service_changes(self):
        with patch.object(greeter.shutil, 'copy2', side_effect=OSError('backup disk full')), \
                patch.object(greeter.subprocess, 'run') as run:
            with self.assertRaises(OSError):
                greeter.configure(self.items)
        run.assert_not_called()
        self.assertEqual(self.config.read_bytes(), b'previous greeter config')
        self.assertFalse(self.css.exists())

    def test_failure_with_no_previous_manager_leaves_no_new_alias(self):
        self.manager.unlink()
        def execute(args, **kwargs):
            if args[:2] == ['systemctl', 'enable']:
                self.manager.symlink_to('/usr/lib/systemd/system/greetd.service')
                raise subprocess.CalledProcessError(1, args)
        with patch.object(greeter.subprocess, 'run', side_effect=execute):
            with self.assertRaises(subprocess.CalledProcessError):
                greeter.configure(self.items)
        self.assertFalse(self.manager.is_symlink())
        self.assertEqual(self.config.read_bytes(), b'previous greeter config')


if __name__ == '__main__':
    unittest.main()
