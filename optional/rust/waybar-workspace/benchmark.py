#!/usr/bin/python3
"""Compare implementations on isolated IPC sockets, without changing the desktop."""
import argparse
import json
import os
from pathlib import Path
import random
import select
import statistics
import subprocess
import tempfile
import time

from test_integration import Hyprland, wait_for


def memory(pid):
    text = Path(f'/proc/{pid}/status').read_text()
    result = {}
    for line in text.splitlines():
        if line.startswith(('VmRSS:', 'Threads:')):
            key, value, *_ = line.split()
            result[key.rstrip(':')] = int(value)
    result['fds'] = len(list(Path(f'/proc/{pid}/fd').iterdir()))
    return result


def cpu_ticks(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
    return int(fields[11]) + int(fields[12])


def stop(child):
    child.terminate()
    try:
        child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    for stream in (child.stdout, child.stderr):
        if stream:
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = {'python': str(args.old.resolve()), 'rust': str(args.new.resolve())}
    report = {'startup_iterations': 60, 'event_iterations': 500,
              'method': 'Warm cache, shuffled startup order, mock Unix IPC; no desktop changes',
              'startup': {}, 'event_watch': {}, 'idle_serve': {},
              'binary_bytes': args.new.stat().st_size}
    rng = random.Random(0)
    with tempfile.TemporaryDirectory(prefix='ww-benchmark-') as directory:
        hypr = Hyprland(Path(directory))
        try:
            for action in ['status', 'focus']:
                samples = {name: [] for name in paths}
                for iteration in range(65):
                    order = list(paths)
                    rng.shuffle(order)
                    for name in order:
                        start = time.perf_counter_ns()
                        subprocess.run([paths[name], action, '1'], env=hypr.env,
                                       capture_output=True, check=True, timeout=4)
                        elapsed = (time.perf_counter_ns() - start) / 1_000_000
                        if iteration >= 5:
                            samples[name].append(elapsed)
                report['startup'][action] = {name: {'median_ms': round(statistics.median(values), 3)}
                                              for name, values in samples.items()}
                report['startup'][action]['speedup'] = round(statistics.median(samples['python']) /
                                                             statistics.median(samples['rust']), 2)
            for name, path in paths.items():
                child = subprocess.Popen([path, 'watch', '1'], env=hypr.env,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    event = hypr.connections.get(timeout=3)
                    assert select.select([child.stdout], [], [], 3)[0]
                    child.stdout.readline()
                    samples = []
                    for index in range(520):
                        target = 2 if index % 2 == 0 else 1
                        start = time.perf_counter_ns()
                        event.sendall(f'workspacev2>>{target},{target}\n'.encode())
                        assert select.select([child.stdout], [], [], 2)[0]
                        value = json.loads(child.stdout.readline())
                        elapsed = (time.perf_counter_ns() - start) / 1000
                        assert ('active' in value['class']) == (target == 1)
                        if index >= 20:
                            samples.append(elapsed)
                    report['event_watch'][name] = {'median_us': round(statistics.median(samples), 2),
                                                   'p95_us': round(sorted(samples)[int(len(samples)*.95)-1], 2)}
                finally:
                    stop(child)
                for file in hypr.output.iterdir():
                    file.unlink()
                child = subprocess.Popen([path, 'serve'], env=hypr.env,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    hypr.connections.get(timeout=3)
                    wait_for(lambda: (hypr.output / 'ready').exists())
                    start = cpu_ticks(child.pid)
                    time.sleep(.3)
                    usage = memory(child.pid)
                    usage['cpu_ticks_during_300ms_idle'] = cpu_ticks(child.pid) - start
                    report['idle_serve'][name] = usage
                finally:
                    stop(child)
        finally:
            hypr.close()
    report['event_watch']['speedup'] = round(report['event_watch']['python']['median_us'] /
                                            report['event_watch']['rust']['median_us'], 2)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n')


if __name__ == '__main__':
    main()
