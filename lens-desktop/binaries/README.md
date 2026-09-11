# binaries/

This directory holds (or symlinks to) the PyInstaller-built `lens-engine`
sidecar binary that the Tauri shell bundles (`bundle.resources` in
`tauri.conf.json`).

The binary is **never committed**. Build it with the release pipeline
(`.github/workflows/release.yml`) or locally:

```bash
cd lens-engine
pyinstaller --onefile --name lens-engine -c lens_engine/__main__.py
# then copy dist/lens-engine* here:
cp dist/lens-engine* ../lens-desktop/binaries/lens-engine/
```

Per-OS naming follows the documented pitfalls in `src/lib.rs`:
Windows Defender cold-start scanning (60s health budget), macOS quarantine
stripping, log-to-file (not piped), full child detach on exit.

For development, the shell falls back to `python -m uvicorn
lens_engine.main:app` when no binary is present, so `cargo tauri dev` works
without a PyInstaller build.
