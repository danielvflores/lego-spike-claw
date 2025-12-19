# -*- mode: python ; coding: utf-8 -*-

# Lista completa de módulos hidden necesarios para pybricksdev
hiddenimports = [
    'pybricksdev',
    'pybricksdev.ble',
    'pybricksdev.connections',
    'pybricksdev.connections.pybricks',
    'pybricksdev.ble.lwp3',
    'pybricksdev.ble.nus',
    'pybricksdev.ble.pybricks',
    'bleak',
    'bleak.backends',
    'bleak.backends.winrt',
    'bleak.backends.winrt.client',
    'bleak.backends.winrt.scanner',
    'bleak.backends.winrt.characteristic',
    'bleak.backends.winrt.service',
    'bleak.backends.winrt.descriptor',
    'bleak.backends.winrt.util',
    'winrt',
    'winrt.windows.devices.bluetooth',
    'winrt.windows.devices.bluetooth.advertisement',
    'winrt.windows.devices.bluetooth.genericattributeprofile',
    'winrt.windows.devices.enumeration',
    'winrt.windows.devices.radios',
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.storage.streams',
    'asyncio',
    'pygame',
    'tkinter',
    'tempfile',
    'queue',
    'threading',
]

import os
import sys

# Rutas a los paquetes mpy-cross completos - relativo al directorio donde está el .spec
spec_root = os.path.dirname(os.path.abspath(SPECPATH))
venv_path = os.path.join(spec_root, 'SpikeLego', 'Lib', 'site-packages')
mpy_cross_v5_dir = os.path.join(venv_path, 'mpy_cross_v5')
mpy_cross_v6_dir = os.path.join(venv_path, 'mpy_cross_v6')

# Lista de datas para incluir directorios completos de mpy-cross
datas_list = []
if os.path.exists(mpy_cross_v5_dir):
    datas_list.append((mpy_cross_v5_dir, 'mpy_cross_v5'))
    print(f"✓ Incluyendo mpy_cross_v5 desde: {mpy_cross_v5_dir}")
else:
    print(f"✗ No encontrado: {mpy_cross_v5_dir}")

if os.path.exists(mpy_cross_v6_dir):
    datas_list.append((mpy_cross_v6_dir, 'mpy_cross_v6'))
    print(f"✓ Incluyendo mpy_cross_v6 desde: {mpy_cross_v6_dir}")
else:
    print(f"✗ No encontrado: {mpy_cross_v6_dir}")

# Ruta al runtime hook
runtime_hook_path = os.path.join(os.getcwd(), 'src', 'pyi_rth_mpy_cross.py')

a = Analysis(
    ['SistemaControlSpike.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[runtime_hook_path] if os.path.exists(runtime_hook_path) else [],
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
    name='SistemaControlSpike',
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
