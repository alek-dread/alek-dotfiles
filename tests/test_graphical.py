"""Failure and lifecycle tests; never manipulate the live desktop."""
import importlib.util
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module

ws = load('workspace_test', ROOT / 'home/.local/libexec/waybar-workspace')
wall = load('wallpaper_test', ROOT / 'home/.local/bin/desktop-wallpaper')
lock = load('lock_test', ROOT / 'home/.local/bin/desktop-lock-state')
record = load('record_test', ROOT / 'home/.local/bin/desktop-record-menu')


class RecordingCleanup(unittest.TestCase):
    def test_one_unload_failure_does_not_skip_other_modules_and_can_retry(self):
        entries = [dict(id=str(n), name='module-loopback', argument=f'source={n}')
                   for n in range(1, 4)]
        current = {entry['id']: entry for entry in entries}
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'audio.json'
            state.write_text(json.dumps(entries))
            def unload(*args):
                if args[-1] == '3':
                    raise RuntimeError('simulated audio-server failure')
            with patch.object(record, 'modules', return_value=current), \
                    patch.object(record, 'run', side_effect=unload) as run:
                with self.assertRaisesRegex(RuntimeError, 'cleanup will be retried'):
                    record.cleanup(state)
                self.assertEqual([call.args[-1] for call in run.call_args_list], ['1', '2', '3'])
            self.assertEqual(json.loads(state.read_text()), [entries[2]])
            with patch.object(record, 'modules', return_value=current), patch.object(record, 'run') as run:
                record.cleanup(state)
                run.assert_called_once_with('pactl', 'unload-module', '3')
            self.assertFalse(state.exists())


    def test_orphan_cleanup_recovers_only_recorder_modules(self):
        entries = [
            dict(id='7', name='module-null-sink', argument='sink_name=desktop_record_mix_123'),
            dict(id='8', name='module-loopback', argument='source=mic sink=desktop_record_mix_123'),
            dict(id='9', name='module-loopback', argument='source=mic sink=music'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'audio.json'
            state.write_text('{truncated')
            with patch.object(record, 'modules', return_value={e['id']: e for e in entries}), \
                    patch.object(record, 'run') as run:
                record.cleanup(state)
                self.assertEqual([call.args[-1] for call in run.call_args_list], ['8', '7'])
            self.assertFalse(state.exists())


class Workspaces(unittest.TestCase):
    def state(self):
        s = ws.State();s.workspaces = [{'id': 1, 'windows': 1}, {'id': 2, 'windows': 1}];s.active = 1
        return s

    def test_focus_does_not_query_ipc(self):
        s = self.state()
        with patch.object(ws, 'query', side_effect=AssertionError('focus-time query')):
            s.event('workspacev2', '2,two');out = s.output()
            self.assertIn('active', json.loads(out[2])['class'])
            self.assertNotIn('active', json.loads(out[1])['class'])

    def test_close_removes_urgent_marker(self):
        s = self.state();s.urgent['abc'] = 2
        self.assertIn('urgent', json.loads(s.output()[2])['class'])
        s.event('closewindow', '0xabc')
        self.assertNotIn('urgent', json.loads(s.output()[2])['class'])

    def test_urgent_moves_with_its_window_and_focus_clears_it(self):
        s = self.state();s.urgent['abc'] = 2
        s.event('movewindowv2', 'abc,3,three')
        self.assertNotIn('urgent', json.loads(s.output()[2])['class'])
        self.assertIn('urgent', json.loads(s.output()[3])['class'])
        s.event('focusedmonv2', 'DP-1,3')
        s.output()
        self.assertFalse(s.urgent)

    def test_new_window_urgency_not_lost_before_counts_refresh(self):
        s = self.state();s.urgent['abc'] = 3
        self.assertIn('urgent', json.loads(s.output()[3])['class'])
        s.workspaces.append({'id': 3, 'windows': 1})
        self.assertIn('urgent', json.loads(s.output()[3])['class'])

    def test_publisher_atomic_snapshot_changed_signals_and_no_redundant_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = ws.Publisher(Path(tmp));out = self.state().output()
            with patch.object(p, 'notify') as notify:
                p.publish(out);notify.assert_called_once_with(list(range(1, 10)))
                mtimes = {n: (Path(tmp)/f'{n}.json').stat().st_mtime_ns for n in out}
                notify.reset_mock();p.publish(out)
                notify.assert_not_called()
                self.assertEqual(mtimes,{n:(Path(tmp)/f'{n}.json').stat().st_mtime_ns for n in out})
                self.assertFalse(list(Path(tmp).glob('*.tmp')))

    def test_never_signals_reused_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = ws.Publisher(Path(tmp));(Path(tmp)/'bar.pid').write_text('12345 old-start')
            with patch.object(ws,'process_start',return_value='new-start'), patch.object(ws.os,'kill') as kill:
                p.notify([1]);kill.assert_not_called()


class Wallpapers(unittest.TestCase):
    def test_rollback_restores_symlink_after_late_failure(self):
        import gi
        gi.require_version('GdkPixbuf','2.0')
        from gi.repository import GdkPixbuf
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'valid.png';pointer=root/'current'
            pb=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,1,1);pb.fill(0x282828ff);pb.savev(str(image),'png',[],[])
            pointer.symlink_to('previous.png')
            with patch.object(wall,'CURRENT',pointer),patch('sys.argv',['desktop-wallpaper',str(image)]), \
                 patch.dict(os.environ,XDG_RUNTIME_DIR=tmp),patch.object(wall,'restart',side_effect=[RuntimeError('late failure'),None]):
                with self.assertRaises(SystemExit):wall.main()
            self.assertEqual(os.readlink(pointer),'previous.png')

    def test_non_image_never_changes_pointer_or_restarts_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'readable.txt';image.write_text('not an image');pointer=root/'current';pointer.symlink_to('previous.png')
            with patch.object(wall,'CURRENT',pointer),patch('sys.argv',['desktop-wallpaper',str(image)]),patch.object(wall,'restart') as restart:
                with self.assertRaises(SystemExit):wall.main()
                restart.assert_not_called()
            self.assertEqual(os.readlink(pointer),'previous.png')


class LockState(unittest.TestCase):
    def test_selects_real_wayland_login_not_uwsm_manager(self):
        sessions=[{'session':'2','uid':os.getuid(),'seat':'seat0'}, {'session':'3','uid':os.getuid(),'seat':None}]
        replies=[json.dumps(sessions),'Type=wayland\nRemote=no','o "/org/freedesktop/login1/session/_32"','']
        with patch.object(lock.subprocess, 'run') as notify, patch.object(lock,'output',side_effect=replies) as output,patch('sys.argv',['desktop-lock-state','locked']):
            lock.main()
        notify.assert_called_once_with(['makoctl', 'mode', '-a', 'locked'], check=True, timeout=5)
        self.assertIn('SetLockedHint',output.call_args.args)
        self.assertEqual(output.call_args.args[-2:],('b','true'))

    def test_notification_failure_still_synchronizes_login_hint(self):
        sessions = [{'session': '2', 'uid': os.getuid(), 'seat': 'seat0'}]
        replies = [json.dumps(sessions), 'Type=wayland\nRemote=no',
                   'o "/org/freedesktop/login1/session/_32"', '']
        for error in (FileNotFoundError('makoctl'),
                      subprocess.CalledProcessError(1, 'makoctl'),
                      subprocess.TimeoutExpired('makoctl', 5)):
            with self.subTest(error=type(error).__name__), \
                    patch.object(lock.subprocess, 'run', side_effect=error), \
                    patch.object(lock, 'output', side_effect=replies) as output, \
                    patch('sys.argv', ['desktop-lock-state', 'unlocked']):
                with self.assertRaisesRegex(RuntimeError, 'LockedHint synchronized'):
                    lock.main()
                self.assertIn('SetLockedHint', output.call_args.args)
                self.assertEqual(output.call_args.args[-2:], ('b', 'false'))

    def test_ambiguous_login_never_changes_hint(self):
        sessions=[{'session':'2','uid':os.getuid(),'seat':'seat0'},{'session':'4','uid':os.getuid(),'seat':'seat1'}]
        with patch.object(lock.subprocess, 'run'), patch.object(lock,'output',side_effect=[json.dumps(sessions),'Type=wayland\nRemote=no','Type=wayland\nRemote=no']) as output, \
             patch('sys.argv',['desktop-lock-state','unlocked']):
            with self.assertRaisesRegex(RuntimeError,'one local Wayland'):lock.main()
            self.assertFalse(any('SetLockedHint' in c.args for c in output.call_args_list))


if __name__=='__main__':unittest.main()
