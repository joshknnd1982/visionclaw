# Building VisionClaw

## Licence

VisionClaw's Python code is licensed under the GNU General Public License, version 2 or later. See `LICENSE`.
It is a fork of VisionMate by Athiban Vijay; files that came from VisionMate keep his copyright line and carry
a "Modified for VisionClaw" line. The bundled engine (llama.cpp, MIT) and the separately downloaded models
(Qwen, Apache 2.0) keep their own licences.

## The engine

The engine is llama.cpp's server, built with Vulkan, and its DLLs. The binaries are not in this repository.
VisionClaw uses the same engine build as VisionMate 5.0.1:

1. Download `VisionMate.nvda-addon` from https://github.com/athee06/VisionMate/releases and open it as a ZIP
   archive, or use the `engine` folder of an installed VisionMate
   (`%APPDATA%\nvda\addons\visionMate\engine`).
2. Copy every `.dll` from its `engine` folder into `addon/engine/`.
3. Copy `vmengine.exe` into `addon/engine/` under the name `vcengine.exe`.

The engine's licence files are already in `addon/engine/`. This documents assembly from released binaries; it
does not claim a reproducible engine build. Any llama.cpp server build new enough for Qwen3.5 that supports
`--list-devices`, `--device` and `response_format` JSON schemas will work.

## Test

```
python tests/run_all.py
python tests/live_orchestrator.py
```

`run_all.py` needs only Python 3.10 or later with Pillow. `live_orchestrator.py` also needs the engine and a
model on the computer: models downloaded by VisionClaw, or VisionMate's vision data.

## Package

```
python build.py
```

writes `dist/VisionClaw-<version>.nvda-addon` and a copy named `dist/VisionClaw.nvda-addon`. Change `version`
and `changelog` in `addon/manifest.ini` before distributing a changed package; never replace a released
version's file with different bytes. The models are not in the package: users choose and download them in
VisionClaw's models window. `claw/catalog.py` holds each model's download address, size and SHA-256.

Test in NVDA before publishing a full release (`docs/TESTPLAN.md`).
