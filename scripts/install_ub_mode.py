"""Operator-initiated, pinned upstream skill installer (not part of CI)."""
import argparse
from pathlib import Path
import urllib.request

COMMIT = '57a8bdd28e45ed41900ace0bafa2ff76dd9ed70f'
SOURCE = f'https://raw.githubusercontent.com/unclebob/ub-mode/{COMMIT}/SKILL.md'


def main():
    p = argparse.ArgumentParser(description='Download original ub-mode to your personal agent skills directory')
    p.add_argument('--target', type=Path, default=Path.home()/'.agents/skills/ub-mode/SKILL.md')
    p.add_argument('--yes', action='store_true', help='Explicitly permit network download and writing to target')
    args = p.parse_args()
    if not args.yes:
        p.error('Supply --yes after reviewing upstream source and destination')
    if args.target.exists():
        p.error(f'Target already exists: {args.target}; no automatic overwrites')
    with urllib.request.urlopen(SOURCE, timeout=20) as response:
        body = response.read(32769)
    if len(body) > 32768 or not body.startswith(b'---\nname: ub-mode\n'):
        p.error('Unexpected skill content')
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_bytes(body)
    print(f'Installed pinned upstream ub-mode to {args.target}')


if __name__ == '__main__': main()