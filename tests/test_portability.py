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


class Recording(unittest.TestCase):
    def test_default_software_and_optional_hardware_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / 'home'
            helpers = home / '.local/bin'
            helpers.mkdir(parents=True)
            menu = helpers / 'desktop-record-menu'
            menu.write_text('#!/bin/sh\nif [ "$1" = --prepare ]; then printf "30\\nsource-test\\n"; '
                            'else [ "${TEST_CLEANUP_FAIL:-0}" = 0 ]; fi\n')
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
            (runtime / 'desktop-record').mkdir()
            def request():
                (runtime / 'desktop-record/request').write_bytes(
                    ('\0'.join([str(root / 'video'), '-g', '0,0 128x128']) + '\0').encode())
            env.pop('DESKTOP_RECORD_ENCODER', None)
            env.pop('DESKTOP_RECORD_DEVICE', None)
            env.pop('DESKTOP_RECORD_DISABLE_VAAPI', None)
            script = str(REPO / 'home/.local/bin/desktop-record')
            for encoder, device, codec, audio in [
                    ('software', '', 'libvpx', 'libopus'),
                    ('vaapi', '', 'h264_vaapi', 'aac'),
                    ('vaapi', '/dev/dri/renderD129', 'h264_vaapi', 'aac')]:
                with self.subTest(encoder=encoder, device=device):
                    options = {} if encoder == 'software' else {'DESKTOP_RECORD_ENCODER': encoder}
                    options['DESKTOP_RECORD_DEVICE'] = device
                    request()
                    result = subprocess.run([script, '_record'],
                                            env=dict(env, **options), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    args = json.loads((root / 'args.json').read_text())
                    self.assertEqual(args[args.index('-c') + 1], codec)
                    self.assertEqual(args[args.index('-C') + 1], audio)
                    self.assertIn('--audio=source-test', args)
                    if encoder == 'software':
                        self.assertIn('--no-dmabuf', args)
                        self.assertIn('deadline=realtime', args)
                        self.assertIn('cpu-used=4', args)
                    if device:
                        self.assertEqual(args[args.index('-d') + 1], device)
                    else:
                        self.assertNotIn('-d', args)
                    cleanup = subprocess.run([script, '_cleanup'], env=env, capture_output=True, text=True)
                    self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                    self.assertFalse((runtime / 'desktop-record/pid').exists())
            # Machine policy must keep even inherited VA-API requests off the GPU.
            request()
            result = subprocess.run([script, '_record'],
                                    env=dict(env, DESKTOP_RECORD_ENCODER='vaapi',
                                             DESKTOP_RECORD_DISABLE_VAAPI='1'),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads((root / 'args.json').read_text())
            self.assertEqual(args[args.index('-c') + 1], 'libvpx')
            self.assertIn('--no-dmabuf', args)
            self.assertNotIn('-d', args)
            self.assertNotIn('h264_vaapi', args)
            # ExecStopPost can fail cleanup and retry without losing the request.
            request()
            result = subprocess.run([script, '_record'],
                                    env=dict(env, TEST_CLEANUP_FAIL='1'),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            cleanup = subprocess.run([script, '_cleanup'], env=dict(env, TEST_CLEANUP_FAIL='1'),
                                     capture_output=True, text=True)
            self.assertNotEqual(cleanup.returncode, 0)
            self.assertTrue((runtime / 'desktop-record/request').exists())
            cleanup = subprocess.run([script, '_cleanup'], env=env, capture_output=True, text=True)
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            self.assertFalse((runtime / 'desktop-record/pid').exists())
            result = subprocess.run([script, 'status'],
                                    env=dict(env, DESKTOP_RECORD_ENCODER='unknown'), capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
