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
6. **Resolution on the WXR build:** the default is `1280x720`, and the bundled
   `TdEngine.ini` pins `ResX=1280` / `ResY=720`. `Resolution = auto` remains
   available: for mono it queries the WinlatorXR container desktop directly in
   `LoadSettings()` and uses the maximum size on the first launch.
   `SyncEngineResolution()` rewrites `ResX/ResY` to whatever is selected. The
   Resolution menu row is hidden in the WXR build.
7. **DllMain order:** install config, re-apply resolution, enforce graphics.
8. **Input policy:** ESC is never blocked. Mouse messages and DirectInput
   mouse state pass while the game is in a menu/2D state (`g_wxrFlat`) or the
   VR panel is open; gameplay remains gamepad-only. DirectInput keyboard state
   keeps `DIK_ESCAPE`; other keys stay silenced.
9. **PC handshake fallback:** `ChooseXrDirectory()` uses `Z:\tmp\xr` when
   `Z:\tmp` exists, otherwise `D:\xrtemp` (the HWXR/Shogo convention). It
   writes `version`/`vr` there and reads `system` if present; `Present()` uses
   `fopen` rather than `GetFileAttributes`, because the latter is unreliable
   under Wine. `tools/fake-xrapi.py` now defaults to the same directory on
   Windows.
10. **Quest focus policy:** `WxrWindowProc` swallows `WM_KILLFOCUS`,
    `WM_ACTIVATE(WA_INACTIVE)`, `WM_ACTIVATEAPP(FALSE)` and
    `WM_NCACTIVATE(FALSE)`, so UE3 does not pause audio or set
    `bIgnoreMoveInput` when WinlatorXR briefly moves the foreground away from
    the only window. In a container (`Z:\tmp` exists) the window re-asserts the
    foreground via a posted message on its own thread; the `D:\xrtemp` PC-test
    fallback leaves alt-tab alone. The installed `TdEngine.ini` also has
    `bPauseOnLossOfFocus=FALSE`. `ProbeInputGates()` now logs each
    `bIgnoreMoveInput` change with the foreground/active window at that moment.
11. **Level-transition heartbeat:** `WxrTransitionTick()` notices the player
    pawn/controller disappearing for more than a second, logs the transition,
    then a five-second `still loading` line with elapsed seconds and
    `MANAGED` pool count, and logs when the pawn returns. This is diagnostic
    only. The prologue -> training load looked like a freeze; the same handover
    took 13.5 s on the PC run, while the reported Quest log ended 13.6 s after
    it, before the ~45 MB training map had finished loading under Box64.
12. **Head-roll direction:** `HeadRollSign` is now `1` = normal, `-1` =
    inverted, `0` = injection off. Both signed values were reported wrong on
    the headset, so `0` is the test default while we determine whether
    WinlatorXR already handles roll. The Comfort menu page has a live HEAD ROLL
    row; `END` still flips the sign, and the same sign feeds the logical head
    frame used by the hands.
13. **Cutscene head look:** `SampleScriptedHeadAngles()` now applies
    `g_yawSign` to the scripted-camera yaw (it was raw, so cutscenes turned the
    view opposite to gameplay) and uses the same sign as the controller-pitch
    write for cinematic pitch. The previous opposite sign was inverted in
    cutscenes while gameplay was correct. The scripted-look log prints both
    effective signs.
14. **Independent FOV controls:** the VR menu's FIELD OF VIEW page (reached
    from Graphics -> XR FOV) has three sliders with visible bars:
    `GameFov` (engine horizontal culling FOV, default `105`; `0` = auto widest
    axis plus margin), `WinlatorXrFov` (HMD horizontal; `0` = auto/headset
    native), and `WinlatorXrFovV` (HMD vertical; `0` = auto). The HMD pair in
    `AdoptLocatedViews()` drives both the rendered target
    frustum and the FOV sent to XrAPI; if only one axis is explicit, the other
    is derived from the render aspect. All three save to `mevr.ini`, apply live,
    and log their effective values.
15. **Texture detail LEVEL:** the bundled `TdEngine.ini` uses the game's own
    LOW texture bucket: max 256 for world/character/weapon/vehicle/effects, 512
    for skybox and light/shadow. This replaces the previous medium 1024/2048
    values.
16. **Original renderer and window:** the WXR build subclasses/pins the game's
    own `hFocusWindow` and hooks the game's existing D3D9 device; it does not
    create a second renderer or window. `D3D9Ex` and `FastCapture` are PCVR
    shared-surface capture features and are forced off for WinlatorXR, so the
    game keeps its original plain D3D9 device. The menu rows are hidden in the
    WXR build.
17. **Detailed Logging defaults off:** `MotionHandsDebug`, `ArmSwingDebug` and
    `ParkourDebug` are off in the code defaults and the shipped `mevr.ini`.
    The Troubleshooting row can enable them for a diagnostic run; they write a
    very large log.
18. **VR menu scaled for 1280x720:** the raster is 1800x1500 (1.5x the old
    1200x1000), `MenuWidth` defaults to 1.65 m (1.5x), and the font scales are
    doubled. That makes the panel 1.5x larger physically and the text 2x the
    old physical size, which restores readability at the lower render
    resolution.
19. **OpenXR/OpenVR stripped from the WinlatorXR build as far as the shared
    code allows:** `xr_diagnostics.inl` (OpenXR loader/layer/reflection
   diagnostics) is excluded, the instance is created with zero extensions, and
   `XrDetailedLogging` is desktop-only. The remaining OpenXR headers are
   compile-time type declarations for the in-process XrAPI shim; the built DLL
   imports no `openxr_loader.dll`, `openvr_api.dll`, `d3d11.dll` or `dxgi.dll`.

The bundled file carries what a key rewrite cannot add: the texture-group LODs,
`[Engine.ISVHacks]`, the game-default `[ALAudio]` device settings,
`[Engine.GameEngine]`, `[Engine.Client]`, and the resolution keys. OpenAL Soft
and the tweak tool's audio overrides are deliberately gone; the WXR mod no
longer ships or replaces `OpenAL32.dll`. The in-place table remains the
guarantee that an old user config cannot re-enable the expensive passes.

## Release overlay

`Release/WXRMOD/` contains:

```
Binaries\
  d3d9.dll            WinlatorXR build, x86, no openxr_loader/d3d11/dxgi imports
  mevr.ini            1280x720, mono, WinlatorXrGraphics=quest, InstallConfig=on
  mevr-TdEngine.ini   performance config installed into Documents by the mod
  MirrorsEdge.exe     tweak-tool patched exe (GOG)
  PhysXCore.dll       copy of PhysXCore.bak
  Macro, SpeedrunOff  optional tweak-tool scripts
TdGame\
  Config\DefaultHudEffects.ini
  CookedPC\Engine.u, TdGame.u, Ts_LOC_int.upk  (original compressed for the
  first device test; the tweak-tool decompressed versions moved to
  Optional\Decompressed)
Symbols\d3d9.pdb
README.txt
BUILD.txt
```

Key hashes:

| File | SHA-256 |
|---|---|
| `d3d9.dll` | `DEF690ACBB0B0F53270EEA90D3C2CC04BDD6A10C6EBFD66D768B518067C47E89` |
| `mevr.ini` | `C8290CA58FB6C1D8B2A5A5E8A24E63B50FA76EC638D3FFE41979D969C560D2C3` |
| `mevr-TdEngine.ini` | `1FB7324D1290EE9166E15565D29F2AF37173286E1C17E80E7415D9FD180F7BB0` |
| `MirrorsEdge.exe` | `EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33` |
| `DefaultHudEffects.ini` | `40A4E4E7A04865BC12E46CF5B082F09D7E884D88B1236542F2993F495CB9917B` |
| `Engine.u` | `8C8A4C79FCFFCCC4882D27FFE522BC299B67D423595B921E0FAC518EF5B8E7FB` |
| `TdGame.u` | `AF4A5ADA7972E949DF1F0C6588617143C86B8EF027F7FBC206ECFF1AD97B0524` |
| `Ts_LOC_int.upk` | `3448981058D0469E9BC5BA1AF475B810F9A4A0AC3424617DDF77B2A71DB5145B` |

Build identity: `1586CE5F864351F197FE054F9C181F5A7C39750DE2182F0C53F7256E06B81038`.

## Build and verification

- Built on Windows with x86 MSVC `/O2` against the OpenXR headers; the
  WinlatorXR flavour links no `openxr_loader.lib`, `openvr_api.lib`,
  `d3d11.lib`, or `dxgi.lib`.
- Confirmed imports: `USER32`, `ADVAPI32`, `WS2_32`, `KERNEL32`, `MSVCP140`,
  `VCRUNTIME140`, UCRT. The x86 VC++ 2015–2022 runtime is required.
- `Fallback\d3d9-mt.dll` is the same source rebuilt `/O2 /MT` and imports only
  `USER32`, `ADVAPI32`, `WS2_32`, `KERNEL32`; use it if the dynamic runtime is
  missing (`29D264B3...`).
- The desktop flavour was compile-checked (`/c`) to ensure the
  `FindTdEngineIniCandidate` refactor did not break it.
- `tools/check-wxrmod-overlay.ps1` validates the overlay hashes, required
  `mevr.ini` keys, the performance keys, the x86 PE machine, and (with
  `-GameDirectory`) the target exe version. It passes 29 checks against this
  overlay and the GOG staging copy.
- The DLL and game files were **not launched** and **not headset-tested**.
  This is a new candidate, not an approved release.

## Caveats

- The installer overwrites the user `TdEngine.ini` on every launch. That is the
  intended "performance is king" behavior; `WinlatorXrInstallConfig = off`
  stops it, and the original is kept once as `.mevr-backup`.
- The release sets `Resolution = 1280x720`, `FrameCap = 60` and
  `WinlatorXrStereo = mono`.
  Mono VR is implemented in this build; AER and SBS remain selectable with
  `WinlatorXrStereo = aer|sbs`.
- The patched `MirrorsEdge.exe` is from the GOG copy. Do not mix it with Steam
  files. Keep it paired with the modified `DefaultHudEffects.ini`.
- Audio is no longer modified. The WXR mod ships no `OpenAL32.dll` and the
  bundled `TdEngine.ini` uses the game's default `Generic Hardware` device.
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

The next successful run (SecondAttempt) confirmed the read-only fix and the
mode logging: the config installed, `UDP mode: MODE_VR 1, MODE_3D 0` (mono)
and `MODE_VR 2, MODE_3D 0` (cutscene) appear, and there is no AER and no
`MODE_VR 0`. The game still stalls at the same pawn/level transition, around
frame 2800 / 62.75 s. One launch in that set also hit `CreateDeviceEx`
`0x8876086A` before any frame; that is a separate startup failure, not the
transition hang.

A native-Windows PC test with the same overlay loaded past the intro video and
reached the tutorial (`frames presented 3861`, clean summary). It had no
control because the WinlatorXR flavour could not find `Z:\tmp\xr\system`, so
XR never started and no pad was synthesised. That is now fixed the way
HWXR/Shogo do it: if `Z:\tmp` does not exist, use `D:\xrtemp`, write
`version`/`vr` there, and start the UDP listener even without `system`. The PC
result also indicates the compressed packages, patched exe, config and mod load
past the intro; the Quest transition hang is more likely specific to the
WinlatorXR/Box64 environment or its XR/presentation path.

The main overlay now uses the **original compressed** `Engine.u`, `TdGame.u`
and `Ts_LOC_int.upk` for the first stability test; the tweak-tool decompressed
versions are in `Optional\Decompressed`. The remaining suspects, in test order:
PhysX still enabled in-game; mono presentation (`WinlatorXrStereo=aer` is the
known-good fallback); the patched exe/config-hash patch; the bundled
config/profile. OpenAL is no longer a variable: it was removed from the WXR
mod, so it is not a suspect. The `memcpy` bad read in the previous run makes a
package/exe issue more likely than the mod's rendering path, but the isolation
steps in `Release/WXRMOD/README.txt` are the test.

## Next checks

1. Install the overlay in the Quest game folder, with the container screen at
   1280x720 for mono. Launch once,
   quit, relaunch so the installed config is read. In `mevr.log`, confirm
   `[wxr] config: installed bundled TdEngine.ini`,
   `[wxr] graphics: Quest performance profile`,
   `[cfg] WinlatorXrInstallConfig = on`, and `[cfg] WinlatorXrStereo = mono`.
2. Confirm the 1280x720 image is not white-screened and the game reaches
   gameplay. If it fails, restore the untouched exe/config pair first.
3. Compare fps and chapter-load time against the previous AER build.
4. Compare mono at 1280x720 against `WinlatorXrStereo = aer` and `sbs` at
   the same resolution. If mono is stable but the image is too soft, raise
   Resolution or test AER.
