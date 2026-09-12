# binaries/

This directory holds the PyInstaller-built `lens-engine` sidecar binary that
the Tauri shell bundles (`bundle.resources` in `tauri.conf.json` maps
`../../binaries/lens-engine/` into the app's resource dir, resolved at
runtime by `src/lib.rs`).

The binaries are **never committed** (`.gitignore` covers everything here
except this README). The release pipeline (`.github/workflows/release.yml`)
builds them per OS/CPU and hands them to the desktop jobs:

| bundle | sidecar placed here |
|---|---|
| Linux (deb/AppImage) | `lens-engine/lens-engine` (x64) |
| Windows (NSIS `.exe` + WiX `.msi`) | `lens-engine/lens-engine.exe` (x64) |
| macOS universal (`.app`/`.dmg`, Intel + Apple Silicon) | `lens-engine/lens-engine-aarch64` + `lens-engine/lens-engine-x86_64` |

The macOS universal build carries BOTH engine architectures; the shell picks
the matching one at runtime via `std::env::consts::ARCH` (the x86_64 engine
itself was produced by PyInstaller under Rosetta 2 on the arm64 runner, since
GitHub no longer ships Intel macOS runners).

Local build (Linux example):

```bash
cd lens-engine
pyinstaller --onefile --name lens-engine \
  --add-data "../reference-data/frameworks:reference-data/frameworks" \
  --hidden-import lens_engine.api.imagesets \
  ... # see release.yml for the full flag set (router + uvicorn hidden imports)
  lens_engine/__main__.py
cp dist/lens-engine ../lens-desktop/binaries/lens-engine/
```

Documented sidecar pitfalls are handled in `src/lib.rs`: Windows Defender
cold-start scanning (60s health budget), macOS quarantine stripping,
log-to-file (not piped), full child detach on exit, `CREATE_NO_WINDOW` on
Windows. For development, the shell falls back to `python -m uvicorn
lens_engine.main:app` when no binary is present, so `cargo tauri dev` works
without a PyInstaller build.
