#!/usr/bin/python3
"""Exercise the compiled utility through isolated fake Hyprland Unix sockets."""
import ctypes
import json
import os
from pathlib import Path
import queue
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest


BIN = Path(os.environ.get('WAYBAR_WORKSPACE_TEST_BIN',
                         Path(__file__).parent / 'target/release/waybar-workspace')).resolve()


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.005)
    raise AssertionError('Timed out waiting for expected state')


class Hyprland:
    def __init__(self, root):
        self.path = root / 'hypr/test'
        self.path.mkdir(parents=True)
        self.output = root / 'output'
        self.output.mkdir()
        self.env = dict(os.environ, XDG_RUNTIME_DIR=str(root),
                        HYPRLAND_INSTANCE_SIGNATURE='test', WAYBAR_WORKSPACE_DIR=str(self.output))
        self.workspaces = [dict(id=1, windows=2), dict(id=2, windows=0)]
        self.active = 1
        self.clients = []
        self.reply = b'ok'
        self.commands = []
        self.connections = queue.Queue()
        self.listeners = []
        self.open_connections = []
        self.closed = threading.Event()
        self.block_counts = None
        self.counts_requested = threading.Event()
        self.threads = []
        for name, handler in [('.socket.sock', self.command), ('.socket2.sock', self.events)]:
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(str(self.path / name))
            listener.listen(32)
            listener.settimeout(.1)
            self.listeners.append(listener)
            thread = threading.Thread(target=self.accept, args=(listener, handler), daemon=True)
            thread.start()
            self.threads.append(thread)

    def accept(self, listener, handler):
        while not self.closed.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.open_connections.append(connection)
            thread = threading.Thread(target=handler, args=(connection,), daemon=True)
            thread.start()
            self.threads.append(thread)

    def events(self, connection):
        self.connections.put(connection)

    def command(self, connection):
        with connection:
            try:
                command = connection.recv(4096).decode()
                self.commands.append(command)
                if command == 'j/workspaces':
                    if self.block_counts is not None:
                        self.counts_requested.set()
                        self.block_counts.wait(timeout=3)
                    response = json.dumps(self.workspaces).encode()
                elif command == 'j/activeworkspace':
                    response = json.dumps(dict(id=self.active)).encode()
                elif command == 'j/clients':
                    response = json.dumps(self.clients).encode()
                else:
                    response = self.reply
                connection.sendall(response)
            except OSError:
                pass

    def close(self):
        self.closed.set()
        if self.block_counts:
            self.block_counts.set()
        for connection in self.open_connections + self.listeners:
            connection.close()
        for thread in list(self.threads):
            thread.join(timeout=.3)


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ww-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.hypr = Hyprland(self.root)
        self.addCleanup(self.hypr.close)
        self.processes = []
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for child in self.processes:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream:
                    stream.close()

    def spawn(self, *args):
        child = subprocess.Popen([str(BIN), *args], env=self.hypr.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(child)
        return child

    def serve(self):
        child = self.spawn('serve')
        event = self.hypr.connections.get(timeout=2)
        wait_for(lambda: (self.hypr.output / 'ready').exists())
        self.assertIsNone(child.poll())
        return child, event

    def cache(self, number):
        return json.loads((self.hypr.output / f'{number}.json').read_text())

    def has(self, number, css):
        return css in self.cache(number)['class']

    def test_status_classes_and_exact_requests(self):
        for number, classes in [(1, ['workspace', 'occupied', 'active']), (2, ['workspace', 'empty']), (9, ['workspace', 'empty'])]:
            result = subprocess.run([str(BIN), 'status', str(number)], env=self.hypr.env,
                                    capture_output=True, check=True, timeout=2)
            self.assertEqual(json.loads(result.stdout), dict(text=str(number), **{'class': classes}))
        self.assertEqual(self.hypr.commands, ['j/workspaces', 'j/activeworkspace'] * 3)

    def test_focus_uses_direct_ipc_and_propagates_errors(self):
        result = subprocess.run([str(BIN), 'focus', '7'], env=dict(self.hypr.env, PATH='/nonexistent'),
                                capture_output=True, timeout=2)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'ok\n')
        self.assertEqual(self.hypr.commands, ['/dispatch hl.dsp.focus({ workspace = 7 })'])
        self.hypr.reply = b'error: invalid dispatcher'
        result = subprocess.run([str(BIN), 'focus', '7'], env=self.hypr.env,
                                capture_output=True, timeout=2)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, self.hypr.reply + b'\n')

    def test_cli_rejects_invalid_arguments(self):
        for args in [[], ['serve', '1'], ['status'], ['status', '0'], ['focus', '10'],
                     ['watch', 'abc'], ['unknown', '1'], ['status', '1', 'extra']]:
            result = subprocess.run([str(BIN), *args], env=self.hypr.env, capture_output=True, timeout=2)
            self.assertEqual(result.returncode, 2, args)

    def test_snapshot_atomic_files_and_unchanged_state(self):
        _, event = self.serve()
        for number in range(1, 10):
            path = self.hypr.output / f'{number}.json'
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            self.assertEqual(self.cache(number)['text'], str(number))
        self.assertTrue(self.has(1, 'occupied'))
        self.assertTrue(self.has(1, 'active'))
        self.assertFalse(list(self.hypr.output.glob('*.tmp')))
        before = {p.name: p.stat().st_mtime_ns for p in self.hypr.output.glob('*.json')}
        event.sendall(b'unknown>>ignored\n')
        time.sleep(.05)
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in self.hypr.output.glob('*.json')})

    def test_partial_and_malformed_events_do_not_disconnect(self):
        child, event = self.serve()
        event.sendall(b'no-separator\nworkspacev2>>bad\n\xff>>bad\nworkspacev2>>')
        time.sleep(.03)
        self.assertTrue(self.has(1, 'active'))
        event.sendall(b'2,name,with,commas\n')
        wait_for(lambda: self.has(2, 'active'))
        self.assertIsNone(child.poll())
        event.sendall(b'focusedmonv2>>DP-1,1\n')
        wait_for(lambda: self.has(1, 'active'))

    def test_focus_publishes_before_blocked_count_query(self):
        _, event = self.serve()
        self.hypr.block_counts = threading.Event()
        self.hypr.workspaces = [dict(id=1, windows=2), dict(id=2, windows=3)]
        event.sendall(b'openwindow>>abc,2,app,title\nworkspacev2>>2,2\n')
        self.assertTrue(self.hypr.counts_requested.wait(timeout=1))
        self.assertTrue(self.has(2, 'active'))
        self.assertTrue(self.has(2, 'empty'))
        self.hypr.block_counts.set()
        wait_for(lambda: self.has(2, 'occupied'))

    def test_window_event_batch_queries_counts_once(self):
        _, event = self.serve()
        initial = self.hypr.commands.count('j/workspaces')
        self.hypr.workspaces.append(dict(id=9, windows=1))
        event.sendall(b'openwindow>>abc,9,app,title\nmovewindowv2>>abc,9,name\nclosewindow>>def\n')
        wait_for(lambda: self.has(9, 'occupied'))
        self.assertEqual(self.hypr.commands.count('j/workspaces'), initial + 1)

    def test_urgent_move_close_and_focus(self):
        _, event = self.serve()
        self.hypr.clients = [dict(address='0xabc', workspace=dict(id=2), urgent=False)]
        event.sendall(b'urgent>>abc\n')
        wait_for(lambda: self.has(2, 'urgent'))
        event.sendall(b'movewindowv2>>0xabc,3,name\n')
        wait_for(lambda: self.has(3, 'urgent'))
        self.assertFalse(self.has(2, 'urgent'))
        event.sendall(b'closewindow>>abc\n')
        wait_for(lambda: not self.has(3, 'urgent'))
        event.sendall(b'urgent>>0xabc\n')
        wait_for(lambda: self.has(2, 'urgent'))
        event.sendall(b'workspacev2>>2,2\n')
        wait_for(lambda: self.has(2, 'active'))
        self.assertFalse(self.has(2, 'urgent'))
        event.sendall(b'workspacev2>>1,1\n')
        wait_for(lambda: self.has(1, 'active'))
        self.assertFalse(self.has(2, 'urgent'))

    def test_reload_rebuilds_snapshot(self):
        _, event = self.serve()
        self.hypr.active = 3
        self.hypr.workspaces = [dict(id=3, windows=4)]
        self.hypr.clients = [dict(address='0xabc', workspace=dict(id=2), urgent=True)]
        event.sendall(b'configreloaded>>\n')
        wait_for(lambda: self.has(3, 'active') and self.has(2, 'urgent'))
        self.assertTrue(self.has(3, 'occupied'))
        self.assertTrue(self.has(1, 'empty'))

    def test_disconnect_marks_unavailable_and_reconnects(self):
        child, event = self.serve()
        event.shutdown(socket.SHUT_RDWR)
        event.close()
        wait_for(lambda: self.has(1, 'unavailable'))
        self.hypr.active = 9
        self.hypr.connections.get(timeout=3)
        wait_for(lambda: self.has(9, 'active'))
        self.assertIsNone(child.poll())

    def test_watch_deduplicates_and_handles_closed_pipe(self):
        child = self.spawn('watch', '1')
        event = self.hypr.connections.get(timeout=2)
        self.assertTrue(select.select([child.stdout], [], [], 2)[0])
        self.assertIn('active', json.loads(child.stdout.readline())['class'])
        event.sendall(b'unknown>>ignored\n')
        self.assertFalse(select.select([child.stdout], [], [], .08)[0])
        child.stdout.close()
        event.sendall(b'workspacev2>>2,2\n')
        self.assertEqual(child.wait(timeout=2), 0)

    def test_wrong_pid_identity_is_not_signalled(self):
        sleeper = subprocess.Popen(['/usr/bin/sleep', '30'])
        self.processes.append(sleeper)
        stat = Path(f'/proc/{sleeper.pid}/stat').read_text().rsplit(') ', 1)[1].split()[19]
        (self.hypr.output / 'bar.pid').write_text(f'{sleeper.pid} {stat}\n')
        self.serve()
        time.sleep(.05)
        self.assertIsNone(sleeper.poll())

    def test_only_changed_workspaces_receive_rt_signals(self):
        code = '''
import ctypes,json,os,signal,sys
ctypes.CDLL(None).prctl(15,b'waybar',0,0,0)
signals=set(range(signal.SIGRTMIN+1,signal.SIGRTMIN+10))
signal.pthread_sigmask(signal.SIG_BLOCK,signals)
print('ready',flush=True)
while True:
    event=signal.sigwaitinfo(signals)
    print(event.si_signo-signal.SIGRTMIN,flush=True)
'''
        bar = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE)
        self.processes.append(bar)
        self.assertEqual(bar.stdout.readline().strip(), b'ready')
        stat = Path(f'/proc/{bar.pid}/stat').read_text().rsplit(') ', 1)[1].split()[19]
        (self.hypr.output / 'bar.pid').write_text(f'{bar.pid} {stat}\n')
        _, event = self.serve()
        initial = {int(bar.stdout.readline()) for _ in range(9)}
        self.assertEqual(initial, set(range(1,10)))
        event.sendall(b'workspacev2>>2,2\n')
        changed = {int(bar.stdout.readline()) for _ in range(2)}
        self.assertEqual(changed, {1,2})
        self.assertFalse(select.select([bar.stdout], [], [], .08)[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
