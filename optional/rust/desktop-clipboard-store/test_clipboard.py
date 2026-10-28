#!/usr/bin/python3
"""Behavioral regressions for the local clipboard integration (no live clipboard)."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


HOME = Path.home()
REPO = Path(__file__).resolve().parents[3]
UI = load('clipboard_ui', REPO / 'home/.local/bin/desktop-clipboard')
STORE = Path(os.environ.get('DESKTOP_CLIPBOARD_STORE_TEST_BIN',
                            Path(__file__).resolve().parent / 'target/release/desktop-clipboard-store'))
MAX_ENTRY = 5_000_000
TIFF = (b'II*\0', b'MM\0*', b'II+\0', b'MM\0+')


def completed(code=0, out=b'', err=b''):
    return subprocess.CompletedProcess([], code, out, err)


def states(active='active', enabled='enabled'):
    return {unit: dict(Id=unit, ActiveState=active, UnitFileState=enabled) for unit in UI.UNITS}


class PickerTests(unittest.TestCase):
    def test_wlcopy_never_inherits_capture_pipes(self):
        with patch.object(UI.subprocess, 'run', return_value=completed()) as call:
            UI.run('wl-copy', data=b'payload')
        self.assertEqual(call.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(call.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(call.call_args.args[0][0], '/usr/bin/wl-copy')

    def test_missing_entry_is_distinguished(self):
        with patch.object(UI.subprocess, 'run', return_value=completed(1, err=b'id 4 not found')):
            with self.assertRaises(UI.MissingEntry):
                UI.run('cliphist', 'decode', data=b'4\n')

    def test_new_database_is_empty(self):
        with patch.object(UI.subprocess, 'run', return_value=completed(1, err=b'opening db: please store something first')):
            self.assertEqual(UI.entries(), [])

    def test_corrupt_database_is_not_silently_empty(self):
        with patch.object(UI.subprocess, 'run', return_value=completed(1, err=b'checksum mismatch')):
            with self.assertRaises(RuntimeError):
                UI.entries()

    def test_only_lf_splits_records(self):
        with patch.object(UI, 'run', return_value='9\tfoo\u2028bar\n8\tOK\n'.encode()):
            self.assertEqual(UI.entries(), [('9', 'foo\u2028bar'), ('8', 'OK')])

    def test_invalid_ids_are_ignored(self):
        with patch.object(UI, 'run', return_value=b'bad\trow\n7\tvalid\n\n'):
            self.assertEqual(UI.entries(), [('7', 'valid')])

    def test_metadata_and_display_controls_are_literal(self):
        value = UI.display_text('a\0icon\x1f/etc/passwd\u202e\u2028b')
        self.assertNotIn('\0', value)
        self.assertNotIn('\x1f', value)
        self.assertNotIn('\u202e', value)
        self.assertNotIn('\u2028', value)
        self.assertIn('\\u0000', value)
        self.assertEqual(UI.display_text('Привет'), 'Привет')

    def test_empty_picker_does_not_launch(self):
        with patch.object(UI.subprocess, 'run') as call:
            self.assertEqual(UI.choose([], '>'), (None, False))
            call.assert_not_called()

    def test_cancel_invalid_index_and_custom_shortcuts(self):
        for code, out, history, expected in [
            (2,b'',True,(None,False)), (0,b'wrong',True,(None,False)),
            (0,b'-1',True,(None,False)), (0,b'99',True,(None,False)),
            (10,b'0',True,(0,True)), (10,b'0',False,(None,False)),
            (0,b'0',True,(0,False)), (11,b'0',True,(None,False))]:
            with self.subTest(code=code, out=out, history=history):
                with patch.object(UI.subprocess, 'run', return_value=completed(code,out)):
                    self.assertEqual(UI.choose(['item'], '>', history=history), expected)

    def test_picker_failure_surfaces(self):
        with patch.object(UI.subprocess, 'run', return_value=completed(1,err=b'bad config')):
            with self.assertRaises(RuntimeError): UI.choose(['item'], '>')

    def test_cancel_does_not_touch_clipboard(self):
        with patch.object(UI,'entries',return_value=[('1','item')]), patch.object(UI,'recording_state',return_value='recording'), patch.object(UI,'choose',return_value=(None,False)), patch.object(UI,'run') as call:
            UI.history()
            call.assert_not_called()

    def test_selection_uses_id_and_preserves_exact_bytes(self):
        data=b'  test\n\t'+ 'Привет'.encode()+b'\n'
        with patch.object(UI,'entries',return_value=[('7','truncated preview')]), patch.object(UI,'recording_state',return_value='recording'), patch.object(UI,'choose',return_value=(0,False)), patch.object(UI,'run',side_effect=[data,b'']) as call:
            UI.history()
            self.assertEqual(call.call_args_list[0].kwargs['data'],b'7')
            self.assertEqual(call.call_args_list[1].kwargs['data'],data)

    def test_selection_refreshes_after_deduplication(self):
        with patch.object(UI,'entries',side_effect=[[('7','same')],[('9','same')]]), patch.object(UI,'recording_state',return_value='recording'), patch.object(UI,'choose',return_value=(0,False)), patch.object(UI,'run',side_effect=[UI.MissingEntry(),b'exact',b'']) as call, patch.object(UI,'notify'):
            UI.history()
            self.assertEqual(call.call_args_list[1].kwargs['data'],b'9')
            self.assertEqual(call.call_args_list[2].kwargs['data'],b'exact')

    def test_delete_refreshes_and_never_copies(self):
        with patch.object(UI,'entries',return_value=[('7','item')]), patch.object(UI,'recording_state',return_value='recording'), patch.object(UI,'choose',side_effect=[(0,True),(None,False)]), patch.object(UI,'run',return_value=b'') as call:
            UI.history()
            call.assert_called_once_with('cliphist','delete',data=b'7')

    def test_notification_failure_is_nonfatal(self):
        for error in (OSError('missing'),subprocess.TimeoutExpired('notify-send',3)):
            with patch.object(UI.subprocess,'run',side_effect=error): UI.notify('hello')


class ControlsTests(unittest.TestCase):
    def test_state_accounts_for_actual_processes(self):
        for active,enabled,expected in [('active','enabled','recording'),('inactive','disabled','paused'),('inactive','enabled','degraded'),('failed','enabled','degraded'),('active','disabled','degraded')]:
            with self.subTest(active=active,enabled=enabled), patch.object(UI,'unit_states',return_value=states(active,enabled)):
                self.assertEqual(UI.recording_state(),expected)

    def test_mixed_state_is_degraded(self):
        value=states();value[UI.UNITS[0]]['ActiveState']='failed'
        with patch.object(UI,'unit_states',return_value=value): self.assertEqual(UI.recording_state(),'degraded')

    def test_unit_state_parser(self):
        text='\n\n'.join('\n'.join(f'{k}={v}' for k,v in s.items()) for s in states().values())+'\n'
        with patch.object(UI,'run',return_value=text.encode()): self.assertEqual(UI.unit_states(),states())

    def test_incomplete_unit_status_is_error(self):
        with patch.object(UI,'run',return_value=b'Id=unknown\n'):
            with self.assertRaises(RuntimeError): UI.unit_states()

    def test_clear_cancel_has_no_effects(self):
        with patch.object(UI,'choose',return_value=(0,False)),patch.object(UI,'run') as call:
            UI.clear();call.assert_not_called()

    def test_clear_restores_only_previously_active_watchers(self):
        value=states();value[UI.UNITS[1]]['ActiveState']='inactive'
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,XDG_RUNTIME_DIR=temp),patch.object(UI,'choose',return_value=(1,False)),patch.object(UI,'unit_states',return_value=value),patch.object(UI,'notify'),patch.object(UI,'run',return_value=b'') as call:
            UI.clear()
            self.assertEqual(call.call_args_list[-1].args,('systemctl','--user','start',UI.UNITS[0]))
            self.assertEqual([c.args[0] for c in call.call_args_list],['systemctl','wl-copy','cliphist','systemctl'])

    def test_clear_failures_restore_watchers(self):
        for failure in (0,1,2):
            calls=[]
            def invoke(*args,**kwargs):
                calls.append(args)
                if len(calls)-1==failure: raise RuntimeError('injected failure')
                return b''
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,XDG_RUNTIME_DIR=temp),patch.object(UI,'choose',return_value=(1,False)),patch.object(UI,'unit_states',return_value=states()),patch.object(UI,'notify'),patch.object(UI,'run',side_effect=invoke):
                with self.assertRaises(RuntimeError): UI.clear()
                self.assertEqual(calls[-1],('systemctl','--user','start',*UI.UNITS))

    def test_clear_does_not_resume_paused_recording(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,XDG_RUNTIME_DIR=temp),patch.object(UI,'choose',return_value=(1,False)),patch.object(UI,'unit_states',return_value=states('inactive','disabled')),patch.object(UI,'notify'),patch.object(UI,'run',return_value=b'') as call:
            UI.clear()
            self.assertFalse(any(c.args[:3]==('systemctl','--user','start') for c in call.call_args_list))

    def test_pause_main_bypasses_menu_lock(self):
        with patch.object(UI.sys,'argv',['desktop-clipboard','pause']),patch.object(UI,'recording') as recording,patch.object(UI,'lock') as lock:
            UI.main();recording.assert_called_once_with(False);lock.assert_not_called()

    def test_lock_contention_and_descriptors(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,XDG_RUNTIME_DIR=temp):
            before=len(os.listdir('/proc/self/fd'))
            with UI.lock('menu'):
                with self.assertRaises(BlockingIOError):
                    with UI.lock('menu',blocking=False): pass
                with UI.lock('control',blocking=False): pass
            for _ in range(200):
                with UI.lock('menu'): pass
            self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_symlink_lock_is_rejected_without_truncation(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,XDG_RUNTIME_DIR=temp):
            target=Path(temp)/'target';target.write_text('unchanged')
            (Path(temp)/'desktop-clipboard-menu.lock').symlink_to(target)
            with self.assertRaises(OSError):
                with UI.lock('menu'): pass
            self.assertEqual(target.read_text(),'unchanged')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='clipboard-store-test-')
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        config = root / 'config/cliphist'
        config.mkdir(parents=True)
        (config / 'config').write_text('max-items 200\n')
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'),
                        XDG_CACHE_HOME=str(root / 'cache'), CLIPBOARD_STATE='data')

    def invoke(self, data, state='data'):
        env = dict(self.env)
        if state is None:
            env.pop('CLIPBOARD_STATE', None)
        else:
            env['CLIPBOARD_STATE'] = state
        result = subprocess.run([str(STORE)], input=data, env=env,
                                capture_output=True, timeout=15)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')
        return result.returncode

    def stored(self):
        result = subprocess.run(['/usr/bin/cliphist', 'list'], env=self.env,
                                capture_output=True, timeout=5)
        if result.returncode:
            self.assertIn(b'please store something first', result.stderr)
            return []
        values = []
        for row in result.stdout.split(b'\n'):
            if not row:
                continue
            entry_id = row.partition(b'\t')[0]
            decoded = subprocess.run(['/usr/bin/cliphist', 'decode'], input=entry_id,
                                     env=self.env, capture_output=True, check=True, timeout=5)
            values.append(decoded.stdout)
        return values

    def test_sensitive_empty_and_unknown_states_are_skipped(self):
        for state in ['sensitive','clear','nil','unexpected','',None]:
            with self.subTest(state=state):
                self.assertEqual(self.invoke(b'not recorded',state),0)
                self.assertEqual(self.stored(), [])

    def test_empty_and_oversized_input_are_skipped(self):
        for data in (b'',b'x'*(MAX_ENTRY+1)):
            self.assertEqual(self.invoke(data),0)
            self.assertEqual(self.stored(), [])

    def test_limit_boundary_is_accepted(self):
        data=b'x'*MAX_ENTRY
        self.assertEqual(self.invoke(data),0)
        self.assertEqual(self.stored(), [data])

    def test_both_tiff_byte_orders_and_bigtiff_are_skipped(self):
        for header in TIFF:
            self.assertEqual(self.invoke(header+b'payload'),0)
            self.assertEqual(self.stored(), [])

    def test_normal_text_and_png_are_unchanged(self):
        for data in (b'  a\n\tb\n',b'\x89PNG\r\n\x1a\nfixture'):
            self.assertEqual(self.invoke(data),0)
            self.assertEqual(self.stored()[0],data)

    def test_unfinished_input_times_out(self):
        child = subprocess.Popen([str(STORE)], env=self.env, stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            child.stdin.write(b'unfinished')
            child.stdin.flush()
            self.assertEqual(child.wait(timeout=6.5), 1)
            self.assertEqual(self.stored(), [])
        finally:
            child.stdin.close()
            if child.poll() is None:
                child.kill()
            child.wait()

    def test_skipped_state_does_not_wait_for_input(self):
        child = subprocess.Popen([str(STORE)], env=dict(self.env, CLIPBOARD_STATE='sensitive'),
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        try:
            self.assertEqual(child.wait(timeout=1), 0)
            self.assertEqual(self.stored(), [])
        finally:
            child.stdin.close()
            if child.poll() is None:
                child.kill()
            child.wait()

    def test_created_history_is_private(self):
        self.assertEqual(self.invoke(b'private test entry'), 0)
        database = Path(self.env['XDG_CACHE_HOME']) / 'cliphist/db'
        self.assertEqual(stat.S_IMODE(database.stat().st_mode) & 0o077, 0)
        self.assertEqual(stat.S_IMODE(database.parent.stat().st_mode) & 0o077, 0)


if __name__=='__main__':
    unittest.main(verbosity=2)
