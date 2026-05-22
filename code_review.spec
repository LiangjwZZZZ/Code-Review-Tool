# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Code Review Tool
# Run on Windows: pyinstaller code_review.spec

from PyInstaller.utils.hooks import collect_all, collect_data_files
import os

block_cipher = None

# Collect all data/binaries for packages that need it
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all('uvicorn')
fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all('fastapi')
starlette_datas, starlette_binaries, starlette_hiddenimports = collect_all('starlette')

a = Analysis(
    ['review/launcher.py'],
    pathex=['.'],
    binaries=uvicorn_binaries + fastapi_binaries + starlette_binaries,
    datas=[
        # Bundle pre-built frontend
        ('review/web/static', 'static'),
        # Include all other package data
        *uvicorn_datas,
        *fastapi_datas,
        *starlette_datas,
    ],
    hiddenimports=[
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # project modules
        'review.web.server',
        'review.engine.diff_parser',
        'review.engine.impact_analyzer',
        'review.engine.llm_reviewer',
        'review.engine.report_generator',
        'review.engine.module_detector',
        'review.store.report_store',
        'review.config',
        'review.gerrit',
        'review.models',
        # other deps
        'anyio',
        'anyio._backends._asyncio',
        'h11',
        'httpx',
        'anthropic',
        'yaml',
        *uvicorn_hiddenimports,
        *fastapi_hiddenimports,
        *starlette_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'test', 'tests', 'notebook', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CodeReview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Set to 'icon.ico' if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CodeReview',
)
