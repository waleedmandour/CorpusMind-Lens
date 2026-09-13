# Reference data

The twelve supported theoretical lenses (§11.3) live in **`frameworks/`** —
that subdirectory is the single canonical copy the engine loads
(`LENS_FRAMEWORKS_DIR`, the Docker image, and the PyInstaller `--add-data`
all point there).

For the template schema, versioning rules, and the phase history of each
lens, see `frameworks/README.md`.

v0.2.1 note: this directory previously also held twelve loose copies of the
same YAML files. Byte-identical duplicates are a drift risk the moment
someone edits one copy and not the other, so the loose copies were removed;
`frameworks/` is the only location.
