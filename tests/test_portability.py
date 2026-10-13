"""Portability checks; system commands are mocked and live settings are untouched."""
import types
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
power_path = REPO / 'home/.local/bin/desktop-power-menu'
power = types.ModuleType('power_menu')
exec(compile(power_path.read_text(), str(power_path), 'exec'), power.__dict__)


class PowerProfiles(unittest.TestCase):
    def test_running_powerprofiles_service_takes_precedence(self):
        with patch.object(power.shutil, 'which', return_value='/usr/bin/tool'), \
                patch.object(power, 'run', return_value='b true') as run:
            self.assertEqual(power.backend(), 'powerprofilesctl')
            self.assertEqual(run.call_args.args[-2:], ('s', 'org.freedesktop.UPower.PowerProfiles'))

    def test_stopped_services_are_only_queried_and_not_started(self):
        with patch.object(power.shutil, 'which', return_value='/usr/bin/tool'), \
                patch.object(power, 'run', return_value='b false') as run:
            with self.assertRaisesRegex(RuntimeError, 'No supported'):
                power.backend()
            self.assertTrue(all(call.args[0] == 'busctl' and 'NameHasOwner' in call.args
                                for call in run.call_args_list))

    def test_tuned_fallback_when_powerprofiles_cli_is_missing(self):
        with patch.object(power.shutil, 'which', side_effect=lambda name:
                          '/usr/bin/tuned-adm' if name == 'tuned-adm' else None), \
                patch.object(power, 'run', return_value='b true'):
            self.assertEqual(power.backend(), 'tuned-adm')

    def test_powerprofiles_lists_only_available_profiles(self):
        output = '  power-saver:\n    CpuDriver: placeholder\n\n* balanced:\n    PlatformDriver: test\n'
        with patch.object(power, 'run', return_value=output):
            self.assertEqual(power.profiles('powerprofilesctl'),
                             [('power-saver', 'Power Saver'), ('balanced', 'Balanced')])

    def test_tuned_lists_standard_and_existing_custom_profiles(self):
        output = ('Available profiles:\n- balanced - General profile\n'
                  '- laptop-custom - Existing laptop profile\n'
                  'Current active profile: laptop-custom\n')
        with patch.object(power, 'run', return_value=output):
            self.assertEqual([name for name, _ in power.profiles('tuned-adm')],
                             ['balanced', 'laptop-custom'])
            self.assertEqual(power.active('tuned-adm'), 'laptop-custom')

    def test_switch_uses_selected_service_and_verifies_result(self):
        for tool, command in [('powerprofilesctl', 'set'), ('tuned-adm', 'profile')]:
            with self.subTest(tool=tool), patch.object(power, 'run') as run, \
                    patch.object(power, 'active', return_value='balanced'), \
                    patch.object(power, 'notify'):
                power.switch(tool, 'balanced')
                run.assert_called_once_with(tool, command, 'balanced')
        with patch.object(power, 'run'), patch.object(power, 'active', return_value='powersave'), \
                patch.object(power, 'notify') as notify:
            with self.assertRaisesRegex(RuntimeError, 'did not confirm'):
                power.switch('tuned-adm', 'balanced')
            notify.assert_not_called()

    def test_set_rejects_nonexistent_profile_before_switching(self):
        with tempfile.TemporaryDirectory() as runtime, \
                patch.dict(os.environ, XDG_RUNTIME_DIR=runtime), \
                patch('sys.argv', ['desktop-power-menu', '--set', 'missing']), \
                patch.object(power, 'backend', return_value='tuned-adm'), \
                patch.object(power, 'profiles', return_value=[('balanced', 'Balanced')]), \
                patch.object(power, 'switch') as switch:
            with self.assertRaisesRegex(RuntimeError, 'Unavailable'):
                power.main()
            switch.assert_not_called()

    def test_menu_selection_and_cancellation(self):
        available = [('balanced', 'Balanced'), ('laptop-custom', 'Laptop custom')]
        for returncode, output, expected in [(0, '1\n', 'laptop-custom'), (2, '', None),
                                             (0, '12\n', None)]:
            with self.subTest(returncode=returncode, output=output), \
                    tempfile.TemporaryDirectory() as runtime, \
                    patch.dict(os.environ, XDG_RUNTIME_DIR=runtime), \
                    patch('sys.argv', ['desktop-power-menu']), \
                    patch.object(power, 'backend', return_value='tuned-adm'), \
                    patch.object(power, 'profiles', return_value=available), \
                    patch.object(power, 'active', return_value='balanced'), \
                    patch.object(power.subprocess, 'run', return_value=subprocess.CompletedProcess(
                        [], returncode, output, '')), \
                    patch.object(power, 'switch') as switch:
                power.main()
                if expected:
                    switch.assert_called_once_with('tuned-adm', expected)
                else:
                    switch.assert_not_called()


class Installer(unittest.TestCase):
    def test_copy_backup_preserve_preferences_and_no_power_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            shutil.copytree(REPO, repo, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            # Make the OS check deterministic, without requiring a Fedora test host.
            release = root / 'os-release'
            release.write_text('ID=fedora\nVERSION_ID=44\n')
            script = repo / 'install.sh'
            script.write_text(script.read_text().replace('/etc/os-release', str(release)))
            (repo / 'home/.config/hypr/local.lua').write_text('-- another machine\n')
            home = root / 'home & test'
            home.mkdir()
            bindir = root / 'bin'
            bindir.mkdir()
            log = root / 'calls.jsonl'
            mock = '''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ['TEST_CALLS'], 'a') as f:
    f.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'id': print('1000')
if name == 'sudo' and os.environ.get('TEST_FAIL') == '1': sys.exit(1)
if name == 'rpm': sys.exit(1)
'''
            for name in ('sudo', 'rpm', 'id', 'gsettings', 'dconf'):
                target = bindir / name
                target.write_text(mock)
                target.chmod(0o755)
            env = dict(os.environ, HOME=str(home), PATH=str(bindir) + ':' + os.environ['PATH'],
                       TEST_CALLS=str(log), XDG_STATE_HOME=str(home / 'state'))
            existing = home / '.config/hypr/hyprland.lua'
            existing.parent.mkdir(parents=True)
            existing.write_text('previous configuration\n')
            local = existing.with_name('local.lua')
            local.write_text('-- local monitor settings\n')
            settings = home / '.config/desktop-record/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('{"audio":"system","fps":60}\n')
            machine_env = home / '.config/uwsm/env-hyprland.local'
            machine_env.parent.mkdir(parents=True)
            machine_env.write_text('export DESKTOP_RECORD_ENCODER=vaapi\n')
            repo_env = repo / 'home/.config/uwsm/env-hyprland.local'
            repo_env.write_text('export DESKTOP_RECORD_ENCODER=software\n')
            result = subprocess.run(['sh', str(script)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            backups = list((home / 'state/alek-dotfiles/backups').iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / '.config/hypr/hyprland.lua').read_text(),
                             'previous configuration\n')
            self.assertEqual(local.read_text(), '-- local monitor settings\n')
            self.assertEqual(settings.read_text(), '{"audio":"system","fps":60}\n')
            for source in (repo / 'home').rglob('*'):
                if not source.is_file():
                    continue
                target = home / source.relative_to(repo / 'home')
                if target in (settings, local, machine_env):
                    continue
                self.assertEqual(target.read_text(), source.read_text().replace('/home/alek', str(home)))
                self.assertEqual(target.stat().st_mode & 0o777, source.stat().st_mode & 0o777)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(machine_env.read_text(), 'export DESKTOP_RECORD_ENCODER=vaapi\n')
            self.assertTrue((backups[0] / 'desktop-interface.dconf').exists())
            self.assertTrue(any(c[:3] == ['sudo', 'rpm', '--import'] for c in calls))
            self.assertTrue(any('--setopt=terra.gpgcheck=1' in c for c in calls))
            self.assertFalse(any('--nogpgcheck' in c for c in calls))
            self.assertFalse(any('lact' in c or 'tuned' in c or 'power-profiles-daemon' in c
                                 or 'ilyaz/LACT' in c for c in calls))
            self.assertTrue(any('wf-recorder' in c and 'pulseaudio-utils' in c for c in calls))
            # Reinstall still keeps preferences and saves another backup.
            subprocess.run(['sh', str(script)], env=env, check=True, capture_output=True)
            self.assertEqual(len(list((home / 'state/alek-dotfiles/backups').iterdir())), 2)
            self.assertEqual(settings.read_text(), '{"audio":"system","fps":60}\n')
            # Unsupported releases must fail before commands or configuration changes.
            release.write_text('ID=fedora\nVERSION_ID=43\n')
            count = len(log.read_text().splitlines())
            result = subprocess.run(['sh', str(script)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(log.read_text().splitlines()), count)
            release.write_text('ID=fedora\nVERSION_ID=44\n')
            # A failed package transaction must not replace any settings.
            failed_home = root / 'failed-home'
            failed_home.mkdir()
            result = subprocess.run(['sh', str(script)],
                                    env=dict(env, HOME=str(failed_home), TEST_FAIL='1'),
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(failed_home.iterdir()), [])


class Recording(unittest.TestCase):
    def test_default_software_and_optional_hardware_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / 'home'
            helpers = home / '.local/bin'
            helpers.mkdir(parents=True)
            menu = helpers / 'desktop-record-menu'
            menu.write_text('#!/bin/sh\n[ "$1" != --prepare ] || printf "30\\nsource-test\\n"\n')
            menu.chmod(0o755)
            bindir = root / 'bin'
            bindir.mkdir()
            recorder = bindir / 'wf-recorder'
            recorder.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
Path(os.environ['TEST_ARGS']).write_text(json.dumps(sys.argv[1:]))
Path(sys.argv[sys.argv.index('-f') + 1]).write_text('mock recording')
''')
            recorder.chmod(0o755)
            notify = bindir / 'notify-send'
            notify.write_text('#!/bin/sh\nexit 0\n')
            notify.chmod(0o755)
            runtime = root / 'runtime'
            runtime.mkdir()
            env = dict(os.environ, HOME=str(home), PATH=str(bindir) + ':' + os.environ['PATH'],
                       XDG_RUNTIME_DIR=str(runtime), XDG_STATE_HOME=str(root / 'state'),
                       XDG_CONFIG_HOME=str(home / '.config'),
                       TEST_ARGS=str(root / 'args.json'))
            env.pop('DESKTOP_RECORD_ENCODER', None)
            env.pop('DESKTOP_RECORD_DEVICE', None)
            script = str(REPO / 'home/.local/bin/desktop-record')
            for encoder, device, codec, audio in [
                    ('software', '', 'libvpx', 'libopus'),
                    ('vaapi', '', 'h264_vaapi', 'aac'),
                    ('vaapi', '/dev/dri/renderD129', 'h264_vaapi', 'aac')]:
                with self.subTest(encoder=encoder, device=device):
                    options = {} if encoder == 'software' else {'DESKTOP_RECORD_ENCODER': encoder}
                    options['DESKTOP_RECORD_DEVICE'] = device
                    result = subprocess.run([script, '_record', str(root / 'video'), '-g', '0,0 128x128'],
                                            env=dict(env, **options), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    args = json.loads((root / 'args.json').read_text())
                    self.assertEqual(args[args.index('-c') + 1], codec)
                    self.assertEqual(args[args.index('-C') + 1], audio)
                    self.assertIn('--audio=source-test', args)
                    if device:
                        self.assertEqual(args[args.index('-d') + 1], device)
                    else:
                        self.assertNotIn('-d', args)
                    self.assertFalse((runtime / 'desktop-record/pid').exists())
            result = subprocess.run([script, 'status'],
                                    env=dict(env, DESKTOP_RECORD_ENCODER='unknown'), capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
