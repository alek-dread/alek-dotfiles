#!/usr/bin/python3
"""Compare helpers using isolated ClipHist databases; never touches Wayland."""
import argparse
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = {'python': str(args.old.resolve()), 'rust': str(args.new.resolve())}
    cases = {'skip_sensitive': ('sensitive', b'ignored'),
             'filter_tiff': ('data', b'II*\0payload'),
             'store_text': ('data', '  benchmark\nПривет\n'.encode()),
             'store_1mb': ('data', b'x' * 1_000_000)}
    report = {'iterations': 60, 'clock': 'perf_counter_ns; warm cache; alternating order',
              'rss': 'median of 5 GNU time maximum RSS samples, includes child processes',
              'cases': {}}
    with tempfile.TemporaryDirectory(prefix='clipboard-store-benchmark-') as directory:
        root = Path(directory)
        envs = {}
        for name in paths:
            config = root / name / 'config/cliphist'
            config.mkdir(parents=True)
            (config / 'config').write_text('max-items 200\n')
            envs[name] = dict(os.environ, XDG_CONFIG_HOME=str(config.parent),
                             XDG_CACHE_HOME=str(root / name / 'cache'))
        rng = random.Random(0)
        for case, (state, payload) in cases.items():
            samples = {name: [] for name in paths}
            for iteration in range(65):
                order = list(paths)
                rng.shuffle(order)
                for name in order:
                    start = time.perf_counter_ns()
                    result = subprocess.run([paths[name]], input=payload,
                                            env=dict(envs[name], CLIPBOARD_STATE=state),
                                            capture_output=True, timeout=15, check=True)
                    elapsed = (time.perf_counter_ns() - start) / 1_000_000
                    assert not result.stdout and not result.stderr
                    if iteration >= 5:
                        samples[name].append(elapsed)
            row = {}
            for name in paths:
                rss = []
                for _ in range(5):
                    output = root / 'time.txt'
                    subprocess.run(['/usr/bin/time', '-f', '%M', '-o', str(output), paths[name]],
                                   input=payload, env=dict(envs[name], CLIPBOARD_STATE=state),
                                   capture_output=True, timeout=15, check=True)
                    rss.append(int(output.read_text().strip()))
                row[name] = {'median_ms': round(statistics.median(samples[name]), 3),
                             'max_rss_kib': statistics.median(rss)}
            row['speedup'] = round(row['python']['median_ms'] / row['rust']['median_ms'], 2)
            report['cases'][case] = row
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n')


if __name__ == '__main__':
    main()
