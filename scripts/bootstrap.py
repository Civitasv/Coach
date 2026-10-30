"""Local-first Python bootstrap for Coach.

Uses the system Python *only* to create/check .venv; installs and runs in .venv.
Does not upgrade system pip or install any global packages.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAMP_NAME = '.coach-deps.json'

# Deliberately standard-library-only: run by the host Python before dependencies exist.
VERSION_PROBE = 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
DIST_PROBE = '''import importlib.metadata as metadata
import pathlib
import re
import sys
requirements = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()
names = [re.match(r'\\s*([A-Za-z0-9_.-]+)', line).group(1) for line in requirements
         if line.strip() and not line.lstrip().startswith('#')]
missing = []
for name in names:
    try:
        metadata.version(name)
    except metadata.PackageNotFoundError:
        missing.append(name)
if missing:
    print('Missing dependencies: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(2)
print('ok')
'''


class BootstrapError(RuntimeError):
    """Actionable setup failure that must never fall back to global pip."""


def runtime_fingerprint():
    return f'{sys.version_info.major}.{sys.version_info.minor}'


def venv_python(folder: Path, os_name=None):
    return folder / 'Scripts' / 'python.exe' if (os_name or os.name) == 'nt' else folder / 'bin' / 'python'


def probe(exe: Path, code: str, *args):
    return subprocess.run([str(exe), '-c', code, *map(str, args)],
                          capture_output=True, text=True, check=False)


def ensure_environment(root=ROOT):
    """Prepare an isolated environment; reuse a healthy install on subsequent runs."""
    if sys.version_info < (3, 11):
        raise BootstrapError('Coach 需要 Python 3.11 或更新版本。')
    root = Path(root).resolve()
    requirements = root / 'requirements.txt'
    if not requirements.is_file():
        raise BootstrapError(f'找不到项目依赖清单：{requirements}')

    folder = root / '.venv'
    python = venv_python(folder)
    if not python.is_file():
        print('[Coach] 创建项目虚拟环境 .venv ...', flush=True)
        try:
            subprocess.run([sys.executable, '-m', 'venv', str(folder)], check=True, cwd=root)
        except (subprocess.CalledProcessError, OSError) as exc:
            raise BootstrapError('创建 .venv 失败；请检查系统 Python 的 venv/ensurepip 支持。') from exc
        if not python.is_file():
            raise BootstrapError('创建 .venv 后找不到 Python 可执行文件；请删除 .venv 再试。')

    version = probe(python, VERSION_PROBE)
    if version.returncode or version.stdout.strip() != runtime_fingerprint():
        raise BootstrapError('现有 .venv 不可用或 Python 版本已变更；请删除项目中的 .venv 后重试。')

    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    signature = {'requirements_sha256': digest, 'python': runtime_fingerprint()}
    stamp = folder / STAMP_NAME
    try:
        saved = json.loads(stamp.read_text(encoding='utf-8')) if stamp.is_file() else None
    except (OSError, ValueError):
        saved = None
    ready = saved == signature and probe(python, DIST_PROBE, requirements).returncode == 0
    if not ready:
        print('[Coach] 在 .venv 中安装或修复依赖（首次运行需要联网）...', flush=True)
        try:
            subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                            '--no-input', '-r', str(requirements)], check=True, cwd=root)
        except (subprocess.CalledProcessError, OSError) as exc:
            stamp.unlink(missing_ok=True)
            raise BootstrapError('依赖安装失败；已保留 .venv，下次启动会重试。请检查网络及 pip 日志。') from exc
        if probe(python, DIST_PROBE, requirements).returncode:
            stamp.unlink(missing_ok=True)
            raise BootstrapError('依赖安装后仍有包缺失；请检查 requirements.txt 或删除 .venv 重试。')
        temp = folder / (STAMP_NAME + '.tmp')
        temp.write_text(json.dumps(signature, sort_keys=True), encoding='utf-8')
        temp.replace(stamp)
    else:
        print('[Coach] 复用已安装的 .venv 依赖。', flush=True)
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare Coach .venv and launch the desktop app')
    parser.add_argument('--prepare', action='store_true', help='Install/repair .venv without launching GUI')
    options = parser.parse_args(argv)
    try:
        python = ensure_environment(ROOT)
        if options.prepare:
            print(f'[Coach] 环境已就绪：{python}')
            return 0
        return subprocess.run([str(python), str(ROOT / 'coach.py')], cwd=ROOT, check=False).returncode
    except BootstrapError as exc:
        print(f'[Coach] {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())