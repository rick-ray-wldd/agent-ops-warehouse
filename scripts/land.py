#!/usr/bin/env python3
"""Copy raw daily batches into data/landing, up to a cutoff day: simulates the exporter delivering over time.

usage: python3 scripts/land.py --through YYYY-MM-DD | --all     (and --reset to empty landing first)
"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('events', 'presence', 'task_changes', 'rework')


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--through')
    g.add_argument('--all', action='store_true')
    ap.add_argument('--reset', action='store_true')
    a = ap.parse_args(argv)
    landing = ROOT / 'data/landing'
    if a.reset and landing.exists():
        shutil.rmtree(landing)
    copied = 0
    for table in TABLES:
        (landing / table).mkdir(parents=True, exist_ok=True)
        for f in sorted((ROOT / 'data/raw' / table).glob('batch_*.csv')):
            day = f.stem.removeprefix('batch_')
            if a.all or day <= a.through:
                dest = landing / table / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    copied += 1
    print(f'landed {copied} new batch files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
