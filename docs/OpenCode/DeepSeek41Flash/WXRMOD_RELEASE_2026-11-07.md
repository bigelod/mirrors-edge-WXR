# WXRMOD performance overlay — 2026-11-07

This is the implementation that goes with
[the tweak review](PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md). It turns the
Mirror's Edge Tweaks findings into a WinlatorXR mod build plus a drop-in game
overlay in `Release/WXRMOD/` (gitignored, local only).

## What changed in the source

All changes are in `src/d3d9.cpp`.

1. **`WxrInstallBundledConfig()`** — at `DLL_PROCESS_ATTACH`, before the engine
   reads its config, copies `mevr-TdEngine.ini` from beside `d3d9.dll` over the
   user config at:
   `...\Documents\EA Games\Mirror's Edge\TdGame\Config\TdEngine.ini`.
   The first existing file is copied once to `TdEngine.ini.mevr-backup`; the
   write uses a temporary file and `MoveFileEx` so a failed write cannot leave a
   half-written config. Controlled by `WinlatorXrInstallConfig = on/off`
   (default on).
2. **`FindTdEngineIniCandidate()`** — the existing Documents locator now has a
   `requireExisting` flag. The installer passes `false`, so a fresh Wine prefix
   gets the config even before the game has created it; the resolution writer
   still requires an existing file.
3. **`WxrApplyQuestGraphics()`** — no longer resets the engine to visual
   defaults. It now enforces the performance profile:
   shadows/DoF/AO/bloom/lens flares/fog/distortion off, `DetailMode=1`,
   `MaxShadowResolution=512`, `MaxAnisotropy=0`, `MaxMultisamples=1`,
   `PhysXEnhanced=False`, `ScreenPercentage=100`, plus the tweak tool's decal,
   LOD, and lighting values.
4. **`WinlatorXrInstallConfig`** parsing added in `LoadSettingsFile()`.
5. **`WinlatorXrStereo = mono|aer|sbs`** added. Mono is the default: one
   view, no eye offset, no draw duplication, `MODE_VR=1`/`MODE_3D=0`. The
   auto-arm path skips stereo, `AdoptLocatedViews` still supplies the forced
   FOV, and Auto resolution uses the full screen size rather than a doubled
   eye width. AER and SBS remain selectable.
6. **Resolution re-apply after install:** the bundled file pins 1440x1080, so
   `SyncEngineResolution()` runs again after the install with the explicit or
   Auto size from `mevr.ini`. A 1280x720 selection is not overwritten by the
   bundled pin.
7. **DllMain order:** install config, re-apply resolution, enforce graphics.
8. **OpenXR/OpenVR stripped from the WinlatorXR build as far as the shared
   code allows:** `xr_diagnostics.inl` (OpenXR loader/layer/reflection
   diagnostics) is excluded, the instance is created with zero extensions, and
   `XrDetailedLogging` is desktop-only. The remaining OpenXR headers are
   compile-time type declarations for the in-process XrAPI shim; the built DLL
   imports no `openxr_loader.dll`, `openvr_api.dll`, `d3d11.dll` or `dxgi.dll`.

The bundled file carries what a key rewrite cannot add: the texture-group LODs,
`[Engine.ISVHacks]`, `[ALAudio]`, `[Engine.GameEngine]`, `[Engine.Client]`, and
the resolution keys. The in-place table remains the guarantee that an old user
config cannot re-enable the expensive passes.

## Release overlay

`Release/WXRMOD/` contains:

```
Binaries\
  d3d9.dll            WinlatorXR build, x86, no openxr_loader/d3d11/dxgi imports
  mevr.ini            1440x1080, mono, WinlatorXrGraphics=quest, InstallConfig=on
  mevr-TdEngine.ini   performance config installed into Documents by the mod
  MirrorsEdge.exe     tweak-tool patched exe (GOG)
  OpenAL32.dll        OpenAL Soft 1.25.1
  PhysXCore.dll       copy of PhysXCore.bak
  Macro, SpeedrunOff  optional tweak-tool scripts
TdGame\
  Config\DefaultHudEffects.ini
  CookedPC\Engine.u, TdGame.u, Ts_LOC_*.upk   (decompressed)
Symbols\d3d9.pdb
README.txt
BUILD.txt
```

Key hashes:

| File | SHA-256 |
|---|---|
| `d3d9.dll` | `D0AD5915041809485C03FB299AA3502DB231C09B05A7AAA3B1BC90E0F8F3B6D4` |
| `mevr.ini` | `A87EB263711190BC3C9FF21A3D6CBBFDFA310E7007A7382E412665A1E2651173` |
| `mevr-TdEngine.ini` | `A44BC437F6AF52519D0CC8DC2E294AFCB9F15892E8ECDAB33F6A435741423D47` |
| `MirrorsEdge.exe` | `EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33` |
| `OpenAL32.dll` | `0F8AC05ADF791904D6ECF74CDE08F6C0ED84411FC55DDC7B1B5E3EB106F34D4D` |
| `DefaultHudEffects.ini` | `40A4E4E7A04865BC12E46CF5B082F09D7E884D88B1236542F2993F495CB9917B` |
| `Engine.u` | `91C2D37C38361100831A682D88127FB30261FBF0F9751E3E7C1308D2964380EB` |
| `TdGame.u` | `866F6F4AC7582F6B56B620FBEF452320757B21856905970707BE193A1E7017FB` |
| `Ts_LOC_int.upk` | `B11DAB124A3C2D124158378CA70BB10087251E5F552EE1582A12C9D03348F1E3` |

Build identity: `2F60E228EC9A13870AD77F6E5C387B1B489BF542C108A0F03855B9EE2F10D727`.

## Build and verification

- Built on Windows with x86 MSVC `/O2` against the OpenXR headers; the
  WinlatorXR flavour links no `openxr_loader.lib`, `openvr_api.lib`,
  `d3d11.lib`, or `dxgi.lib`.
- Confirmed imports: `USER32`, `ADVAPI32`, `WS2_32`, `KERNEL32`, `MSVCP140`,
  `VCRUNTIME140`, UCRT. The x86 VC++ 2015–2022 runtime is required.
- `Fallback\d3d9-mt.dll` is the same source rebuilt `/O2 /MT` and imports only
  `USER32`, `ADVAPI32`, `WS2_32`, `KERNEL32`; use it if the dynamic runtime is
  missing (`89DB482A...`).
- The desktop flavour was compile-checked (`/c`) to ensure the
  `FindTdEngineIniCandidate` refactor did not break it.
- `tools/check-wxrmod-overlay.ps1` validates the overlay hashes, required
  `mevr.ini` keys, the performance keys, the x86 PE machine, and (with
  `-GameDirectory`) the target exe version. It passes 24 checks against this
  overlay and the GOG staging copy.
- The DLL and game files were **not launched** and **not headset-tested**.
  This is a new candidate, not an approved release.

## Caveats

- The installer overwrites the user `TdEngine.ini` on every launch. That is the
  intended "performance is king" behavior; `WinlatorXrInstallConfig = off`
  stops it, and the original is kept once as `.mevr-backup`.
- The release sets `Resolution = 1440x1080` and `WinlatorXrStereo = mono`.
  Mono VR is implemented in this build; AER and SBS remain selectable with
  `WinlatorXrStereo = aer|sbs`.
- The patched `MirrorsEdge.exe` is from the GOG copy. Do not mix it with Steam
  files. Keep it paired with the modified `DefaultHudEffects.ini`.
- `MaxChannels=256` is the tweak-tool value; test 64/128 if the CPU is the
  limit.
- The approved desktop v0.2.2-alpha release is untouched; this is a separate
  local Quest candidate.
- Game-derived files live only under gitignored `Release/`; do not commit them.

## Freeze report, 2026-11-08

The first device attempts (`E:/tmp/Q3Mods/MirrorsEdge/Logs/FirstAttempt`) hang
on the intro/cutscene → tutorial transition.

- The 23:27 run used PERFORMANCE (`STRONGMEM=0`) and ended at
  `MirrorsEdge.exe+73079A` (null vtable, the known out-of-order-write symptom).
- The 23:54 run also used PERFORMANCE and a 1280x720 container with
  `Resolution=1440x1080`; the 2D screen was scaled 960x720 into 1280x720.
- The latest run used STABILITY (`STRONGMEM=2`) and matched 1440x1080, and
  still hung after the cutscene: pawn invalidated at frame 2346, camera fields
  unreadable, a first-chance `VCRUNTIME140+ED67` (inside `memcpy`) bad read,
  then the log stops at frame 2544 / 45.2 s.
- The latest config install failed with error 5: the tweak tool had made
  `TdEngine.ini` read-only, so neither the install nor the profile could write.
  The game also cannot save settings while it is read-only.

Code changes from this report: clear the read-only attribute before config
writes; stop sending `MODE_VR 0` on shutdown; clamp `MODE_3D` to 0 for any
`MODE_VR` other than 1 and log every UDP mode change; log a container-desktop
vs `Resolution` mismatch.

The remaining suspects, in test order: PhysX still enabled in-game; mono
presentation (`WinlatorXrStereo=aer` is the known-good fallback); the tweak
tool's decompressed packages; the patched exe/config-hash patch; OpenAL Soft;
the bundled config/profile. The `memcpy` bad read at the transition makes a
package/exe issue more likely than the mod's rendering path, but the isolation
steps in `Release/WXRMOD/README.txt` are the test.

## Next checks

1. Install the overlay in the Quest game folder, with the container screen at
   1440x1080 for mono (or a 16:9 screen plus a 16:9 `Resolution`). Launch once,
   quit, relaunch so the installed config is read. In `mevr.log`, confirm
   `[wxr] config: installed bundled TdEngine.ini`,
   `[wxr] graphics: Quest performance profile`,
   `[cfg] WinlatorXrInstallConfig = on`, and `[cfg] WinlatorXrStereo = mono`.
2. Confirm the 4:3 1440x1080 image is not white-screened and the game reaches
   gameplay. If it fails, restore the untouched exe/config pair first.
3. Compare fps and chapter-load time against the previous AER build.
4. Compare mono at 1440x1080 against `WinlatorXrStereo = aer` and `sbs` at a
   16:9 resolution (1920x1080 or 1536x864). If mono is stable but the image
   is too soft, raise Resolution or test AER.
