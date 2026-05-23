# -*- mode: python ; coding: utf-8 -*-
import os
from shutil import copyfile, copytree

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'openai',
    'dotenv',
    'questionary',
    'prompt_toolkit',
    'rich',
    'crawl4ai',
    'playwright',
    'patchright',
    'litellm',
    'lxml',
]

for package_name in [
    'questionary',
    'prompt_toolkit',
    'rich',
    'crawl4ai',
    'playwright',
    'patchright',
    'litellm',
    'lxml',
]:
    tmp_ret = collect_all(package_name)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Tenz-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

dist_root = os.path.abspath(DISTPATH if 'DISTPATH' in globals() else 'dist')
os.makedirs(dist_root, exist_ok=True)
os.makedirs(os.path.join(dist_root, 'config'), exist_ok=True)
os.makedirs(os.path.join(dist_root, 'docs'), exist_ok=True)

copyfile('system_prompt.md', os.path.join(dist_root, 'system_prompt.md'))
copyfile('.env.example', os.path.join(dist_root, '.env.example'))
copyfile('README.md', os.path.join(dist_root, 'README.md'))
copyfile(os.path.join('config', 'playwright_config.json'), os.path.join(dist_root, 'config', 'playwright_config.json'))
copyfile(os.path.join('docs', 'tools.md'), os.path.join(dist_root, 'docs', 'tools.md'))

playwright_browsers_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
if os.path.isdir(playwright_browsers_dir):
    dist_browsers_dir = os.path.join(dist_root, 'ms-playwright')
    os.makedirs(dist_browsers_dir, exist_ok=True)

    for browser_prefix in ['chromium', 'chromium_headless_shell']:
        browser_dirs = [
            name for name in os.listdir(playwright_browsers_dir)
            if name.startswith(browser_prefix + '-')
        ]
        if browser_dirs:
            latest_browser_dir = sorted(
                browser_dirs,
                key=lambda name: int(name.rsplit('-', 1)[-1]) if name.rsplit('-', 1)[-1].isdigit() else 0,
            )[-1]
            copytree(
                os.path.join(playwright_browsers_dir, latest_browser_dir),
                os.path.join(dist_browsers_dir, latest_browser_dir),
                dirs_exist_ok=True,
            )
