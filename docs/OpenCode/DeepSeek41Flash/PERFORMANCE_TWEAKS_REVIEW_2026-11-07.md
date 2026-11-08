# Mirror's Edge Tweaks vs untouched — what is worth carrying to Quest

Date: 2026-11-07. Compared:

- `<staging>\ME` — the copy with **Mirror's Edge Tweaks** applied.
- `<staging>\ME_Untouched` — the pristine copy.
- `%USERPROFILE%\Documents\EA Games\Mirror's Edge\TdGame\Config\TdEngine.ini`
  — the effective user config the tweak tool rewrote.

No game was launched and no headset test was performed for this note. The
performance conclusions are therefore a plan, not a measurement. The one
measured performance fact inherited from the previous work is that the Quest
port is **CPU draw-call bound**, not GPU-fill bound: the October notes measured
11–21 fps side-by-side, 35–42 fps alternate-eye, GPU around 45%, and no-stereo
25–37 fps. Keep that in mind before expecting graphics-setting cuts to raise
frame rate.

## 1. What the tweak tool actually changed

### 1.1 File tree

Only four files exist in `ME` but not `ME_Untouched`:

| File | Size | Purpose |
|---|---:|---|
| `Binaries\Macro` | 154 B | UnrealScript `exec` file for speedrun scroll macros. Not needed for normal play. |
| `Binaries\SpeedrunOff` | 309 B | UnrealScript `exec` file restoring the normal player controller/HUD. Not needed for normal play. |
| `metweaksconfig.ini` | 92 B | The tweak tool's own saved settings (`FOV=90`, empty user-folder override). Desktop tool state, not a game file. |
| `Mirror's Edge Tweaks.exe` | 13,016,459 B | The WPF tweak tool itself. Do not put this on the headset. |

Eighteen files differ in size or content: seventeen size changes plus the
same-size executable. Everything else retains the original install timestamp.
I did not byte-hash the ~11.5 GB of unchanged map/content packages; the
post-install timestamps and size scan identify the touched set.

| File | `ME` | `ME_Untouched` | What changed |
|---|---:|---:|---|
| `Binaries\MirrorsEdge.exe` | 31,596,544 | 31,596,544 | Same size, **patched** (see 1.2). |
| `Binaries\OpenAL32.dll` | 4,030,478 | 115,432 | Replaced with **OpenAL Soft 1.25.1** (`soft_oal.dll`). |
| `TdGame\Config\DefaultHudEffects.ini` | 5,017 | 5,018 | Speed streak effect disabled (4 lines changed). |
| `TdGame\CookedPC\Engine.u` | 6,109,562 | 1,662,824 | **Decompressed** (LZO removed). |
| `TdGame\CookedPC\TdGame.u` | 58,893,078 | 29,281,987 | **Decompressed** (LZO removed). |
| `TdGame\CookedPC\Ts_LOC_int.upk` | 3,452,562 | 658,608 | **Decompressed**. |
| 12 other `Ts_LOC_*.upk` | — | — | **Decompressed** (CHS, cht, CZE, DEU, ESN, FRA, HUN, ITA, jpn, kor, POL, RUS). |

Key hashes (SHA-256):

| File | `ME` | `ME_Untouched` |
|---|---|---|
| `Binaries\MirrorsEdge.exe` | `EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33` | `58DE3DF21F40E9953E00BE92F7749097832BAD02E5B657D8485CDB61F360A3DD` |
| `Binaries\OpenAL32.dll` | `0F8AC05ADF791904D6ECF74CDE08F6C0ED84411FC55DDC7B1B5E3EB106F34D4D` | `2B098EAB63649CF554D27B0E0C3EE933B5F5A7C5D601A780268324842E7F215C` |
| `TdGame\Config\DefaultHudEffects.ini` | `40A4E4E7A04865BC12E46CF5B082F09D7E884D88B1236542F2993F495CB9917B` | `1031AE527C93FD2C7F857E0EDAECC727B689F92947036D53200F2F93EBE05B50` |
| `TdGame\CookedPC\Engine.u` | `91C2D37C38361100831A682D88127FB30261FBF0F9751E3E7C1308D2964380EB` | `8C8A4C79FCFFCCC4882D27FFE522BC299B67D423595B921E0FAC518EF5B8E7FB` |
| `TdGame\CookedPC\TdGame.u` | `866F6F4AC7582F6B56B620FBEF452320757B21856905970707BE193A1E7017FB` | `AF4A5ADA7972E949DF1F0C6588617143C86B8EF027F7FBC206ECFF1AD97B0524` |

### 1.2 The executable patches

The executable changed by exactly **32 bytes**. PE headers, section sizes,
checksum, timestamp, entry point and image base are otherwise identical.

1. **One code byte at file offset `0x8E8B30`** (VA `0xCE8B30`):
   `0x75` (JNE rel8) → `0xEB` (JMP rel8). The tool itself names this the
   render-target patch site and expects `JNE 0x75`. This is the documented
   fix for white-screen at narrower-than-16:9 aspect ratios above 720p. It is
   relevant to 1440x1080 (4:3) and must stay with that resolution.
2. **Thirty-one bytes in `.rsrc`, `0x1C2D070…0x1C2D516`**: the first byte of
   32 config-file names in the resource table gets bit `0x80` set
   (for example `\xE2asecompat.ini`, `\xE4efaultengine.ini`). This is the
   tool's **Unlocked Configs** patch, which bypasses the "corrupted config"
   launch failure when game-directory config files such as
   `DefaultHudEffects.ini` have been edited.

Consequence: **copy the patched `MirrorsEdge.exe` and the modified
`DefaultHudEffects.ini` as a pair.** The config file alone is not safe, and the
executable's render-target fix is needed for the 4:3/high-resolution target.
The patch is a same-size in-place change; it does not move any code or alter
the engine/package ABI the mod reflects.

### 1.3 The package decompression is real, not a re-cook

The package headers were compared. Version, total header size, name/export/
import counts and offsets are identical. Only the compression markers changed:

| Package | CompressionFlags | Chunks | PackageFlags |
|---|---|---:|---|
| `Engine.u` untouched | 2 (LZO) | 5 | `0x02A80008` |
| `Engine.u` ME | 0 | 0 | `0x00A80008` |
| `TdGame.u` untouched | 2 (LZO) | 55 | `0x02A80009` |
| `TdGame.u` ME | 0 | 0 | `0x00A80009` |
| `Ts_LOC_int.upk` untouched | 2 (LZO) | 4 | `0x0288000D` |
| `Ts_LOC_int.upk` ME | 0 | 0 | `0x0088000D` |

`0x02000000` is `PKG_StoreCompressed`. This is exactly the transformation the
repo's own `tools/uedecompress3/uedecompress3.cpp` performs. It is a valid
decompressed package, not a different cooking or a modded script. It saves
load-time LZO decompression CPU under Box64; it does not change the in-memory
object layout the mod reflects.

## 2. What the tweak tool put in the user config

`%USERPROFILE%\Documents\EA Games\Mirror's Edge\TdGame\Config\TdEngine.ini`
(40,788 bytes) is the effective config. The important `[SystemSettings]` values:

| Setting | Value | Comment |
|---|---|---|
| `ResX` / `ResY` | 1440 / 1080 | 4:3 target; needs the render-target patch. Default was 1280x720. |
| `Fullscreen` | True | WinlatorXR pins the window borderless anyway. |
| `UseVsync` | False | Correct for VR. |
| `DynamicShadows` | True | The mod's Quest profile turns this off at startup. |
| `LightEnvironmentShadows` | True | Character shadows; the mod turns this off. |
| `StaticDecals` / `DynamicDecals` | True / True | Can be tested off for draw-call reduction. |
| `Bloom` / `QualityBloom` | False / False | The mod profile raises `QualityBloom` to True but leaves `Bloom` False. |
| `DepthOfField` | False | The mod profile re-enables it (`True`) — questionable in VR. |
| `AmbientOcclusion` | False | The mod profile keeps it False. |
| `MotionBlur` / `TdMotionBlur` | false / False | Both off. |
| `LensFlares` | False | The mod profile re-enables native flares (`True`). |
| `FogVolumes` | False | The mod profile re-enables them (`True`). |
| `Distortion` | True | Set False for a fill-rate test. The mod profile would force True. |
| `DetailMode` | 1 | The mod profile raises it to 2. |
| `MaxShadowResolution` | 1024 | The mod profile lowers it to 512. |
| `ShadowFilterQualityBias` | 2 | Not touched by the mod profile. |
| `MaxAnisotropy` | 0 | The mod profile raises it to 4. |
| `MaxMultisamples` | 1 | No MSAA. |
| `SkeletalMeshLODBias` / `ParticleLODBias` | 0 / 0 | The mod profile keeps both 0. |
| `FoliageDrawRadiusMultiplier` | 0.0 | The mod profile restores 1.0. |
| `EnableHighPolyChars` | False | Keep. |
| `TdSunHaze` | False | Removes a full-screen effect; keep off for VR. |
| `TdTonemapping` | False | Visual change; test. |
| `TdBicubicFiltering` | False | Keep off. |
| `PhysXEnhanced` | False | Keep off; also the stability workaround from the PhysX notes. |
| `bSmoothFrameRate` | FALSE | The mod's frame cap owns pacing. |
| `MaxSmoothedFrameRate` | 62 | The mod's `FrameCap` (72 default) is the intended control. |
| Texture groups | max 1024 (vehicle 2048, skybox 2048, light/shadow 4096, render target 4096) | This matches the tool's **Medium** texture preset. The tool's **Low** preset is max 256. |
| `ALAudio` | `OpenAL Soft`, `MaxChannels=256`, `UseEffectsProcessing=True` | 256 software voices can be expensive under Box64; test 64/128. |

The `TdEngine.ini` was last written at 15:09 and `TdInput.ini` at 15:10; the
game tree's only changed config is `DefaultHudEffects.ini`. The only
performance-irrelevant input change I found is `MouseSensitivity` 18 → 28
(the cm/360 setting); `LookRightScale` remains 12000, which is the baseline
the mod uses for smooth turning. VR input uses the mod's synthesised pad, so
the mouse sensitivity does not affect Quest play; keep it only for desktop
testing. The tweak tool's FOV=90 and DPI/cm-360 fields in `metweaksconfig.ini`
do not appear as a gameplay FOV change in the config; the observed executable
diff contains no other code patch, so do not assume a hidden exe FOV patch.

## 3. The mod's Quest graphics profile conflicts with these settings

`src/d3d9.cpp` (`WxrApplyQuestGraphics`, around lines 675–745) rewrites 20
`[SystemSettings]` keys in the user config before the engine reads it, unless
`WinlatorXrGraphics = game`. Its values are:

```
DynamicShadows=False              LightEnvironmentShadows=False
MotionBlur=False                  DepthOfField=True
AmbientOcclusion=False            Distortion=True
LensFlares=True                   DetailMode=2
MaxShadowResolution=512           MaxAnisotropy=4
SkeletalMeshLODBias=0             ParticleLODBias=0
UseVsync=False                    DynamicLights=True
CompositeDynamicLights=False      DynamicDecals=True
FogVolumes=True                   DirectionalLightmaps=True
QualityBloom=True                 FoliageDrawRadiusMultiplier=1.000000
```

This is deliberate: the October headset test found the wider "low" profile
looked worse and gained no frame rate because the render thread's draw calls
are the limit. It only keeps dynamic shadows off. But it also **re-enables
DepthOfField, native LensFlares, FogVolumes, DetailMode 2, anisotropy and
foliage**, which are poor defaults for a performance-first VR target.

Two ways to reconcile:

- **Recommended for this experiment:** set `WinlatorXrGraphics = game` in
  `mevr.ini` so the mod leaves the tuned config alone, then make sure the
  config itself has `DynamicShadows=False`, `LightEnvironmentShadows=False`,
  `UseVsync=False`, `PhysXEnhanced=False`. This is a config-only change, no
  rebuild. **Do not skip the two shadow keys:** the tweaked `TdEngine.ini`
  currently has both `True`; `game` mode will not turn them off for you, and
  they are the one graphics cut the previous headset test actually kept.
- Or change `WxrApplyQuestGraphics` so it stops forcing the visual-quality
  keys and only enforces dynamic/character shadows off. That is a code change
  and needs a new build; do it only if `game` mode proves too unmanaged.

`WinlatorXrGraphics` is parsed but is **not present in `mevr.ini.example`**.
Add it manually to the Quest `mevr.ini`; the parser accepts `quest` or `game`.
A minimal first-run block:

```ini
WinlatorXrGraphics = game
Resolution = 1440x1080
AlternateEye = on
FrameCap = 72
```

Confirm which file the mod found from `mevr.log`: `[wxr] graphics: TdEngine.ini
...` names the path it rewrote, and `[cfg] WinlatorXrGraphics = game` confirms
the profile is disabled. If the log says the file was not found, the tuned
config is in the wrong Wine user folder; fix that before judging performance.

## 4. What to copy to the Quest game folder

Strongly recommended:

1. `Binaries\MirrorsEdge.exe` — patched for 4:3/high-res and unlocked configs.
2. `TdGame\Config\DefaultHudEffects.ini` — streak off; keep paired with the
   patched exe.
3. `TdGame\CookedPC\Engine.u`, `TdGame\CookedPC\TdGame.u`, and at least
   `TdGame\CookedPC\Ts_LOC_int.upk` — decompressed, load-time CPU saving.
   Copying all 13 language packs is also fine; only the active language is
   loaded. Skipping unused languages saves ~100 MB on the headset.
4. The tuned `TdEngine.ini` into the Wine user config folder
   (`...\Documents\EA Games\Mirror's Edge\TdGame\Config\TdEngine.ini`), not the
   game's `TdGame\Config` defaults folder.
5. Quest install prep from the earlier WinlatorXR notes: copy
   `Binaries\PhysXCore.bak` to `Binaries\PhysXCore.dll` in the container's
   `Binaries` folder, and keep `PhysXEnhanced=False`. That is the workaround
   for the headset's missing system PhysX and for the Steam/PhysX chapter-load
   freeze. Install the mod's `d3d9.dll` and generated `mevr.ini` separately;
   the WinlatorXR flavour does not need `openxr_loader.dll`.

Optional / measure:

- `Binaries\OpenAL32.dll` (OpenAL Soft 1.25.1). It fixes the game's audio
  attack/transient issue and raises the source limit. But 256 software voices
  can cost CPU under Box64; start with 64 or 128 in `MaxChannels` and compare.
- `Binaries\Macro`, `Binaries\SpeedrunOff` only if using the speedrun/trainer
  tooling. They are not performance files.

Do not copy:

- `Mirror's Edge Tweaks.exe` or `metweaksconfig.ini` to the headset.
- Any game file into this repository. The packages and executable are
  game-derived; keep them in the staging/game folder and out of commits.

Keep a backup of the untouched `MirrorsEdge.exe`, `DefaultHudEffects.ini`,
`Engine.u`, `TdGame.u`, and `Ts_LOC_int.upk` beside the Quest install. If the
patched exe or config path is wrong, restore the pair and retest before
changing anything else.

## 5. The bigger lever: monocular VR

The XrAPI mode table is explicit (`docs/general_wxr/XRAPI_V0_4_DESC.md`,
section 5a):

| Mode | `MODE_VR` | `MODE_3D` | Scene cost | Per-eye rate |
|---|---|---|---|---|
| **Mono VR** | 1 | 0 | **1x** | full |
| SBS stereo | 1 | 1 | 2x | full |
| AER stereo | 1 | 2 | 1x | half |
| Non-VR flat | 2 | 0 | 1x | full |

At the time of this review, the WinlatorXR port had no mono-VR presentation.
`WxrUpdateFlatMode` (`src/winlatorxr_frame.inl`) set `g_stereoMode = 1` when
the player was in control, then chose side-by-side (`layout = 1`) or
alternate-eye (`layout = 2`). `layout = 0` was the flat/non-VR menu screen. The
only mono path was the engine's mono fallback, which was treated as flat. The
fork header said "monocular", but the port defaulted to stereo AER.

The 2026-11-07 WXRMOD build implements it: `WinlatorXrStereo = mono` is the
default, with `layout = 3` presenting `MODE_VR=1, MODE_3D=0` and no eye offset
or draw duplication. AER and SBS remain selectable. See
[the release note](WXRMOD_RELEASE_2026-11-07.md).

For a **monocular** target, the high-value change is:

- Add a `mono` choice (for example `AlternateEye = mono`, or a new
  `WinlatorXrStereo = mono`).
- While in control, keep `g_stereoMode = 0` (no eye offset, no draw
  duplication) but do **not** set the flat-screen flag.
- Present with `MODE_VR = 1`, `MODE_3D = 0`, the headset's native FOV, sync red
  as usual, blue = 0.
- Render one 1440x1080 view and show it to both eyes. The game still gets the
  mod's 6DOF head tracking; UI and the VR panel draw once, not per eye.
- In `xrEnumerateViewConfigurationViews` (`src/winlatorxr.inl`), use the full
  screen width (or the explicit resolution) for mono instead of the half-width
  SBS/AER calculation.

Implementation touch points in `src/winlatorxr_frame.inl`: the `layout` choice
around line 662, the `WxrDrawMenu(..., roomScreen ? 2 : layout, ...)` call
around line 726, the `wxr::Send(...)` mapping around lines 737–741 (mono needs
`Send(0, 0, 1, 0, fovX, fovY)`), and the `g_eyeInject`/`g_renderedEye` reset
around lines 799–810. `WxrUpdateFlatMode` around lines 398–412 currently uses
`g_wxrFlat` for "not in control"; mono needs a separate "in control but not
stereo" state so the flat-screen path is not entered.

This should be at least as fast as alternate-eye (1x draw calls) and avoids
AER's eye-alternation ghosting, at the cost of stereo depth. Given the measured
CPU draw-call limit, it is the most promising single performance change for a
monocular Quest target.

### Resolution reality check

- **Mono 1440x1080** means one 1.56 MP image to both eyes. Sensible for a
  monocular target and the easiest match to a 4:3 window.
- **SBS at 1440x1080** would give only 720x1080 per eye. If you want stereo at
  1440x1080 per eye, the backbuffer needs 2880x1080, or use AER (full 1440x1080
  per eye at half the per-eye rate).
- The WinlatorXR Auto-resolution code assumes a 16:9 screen and a half-width
  eye for SBS; an explicit 4:3 mode is not its default path. The tweak exe's
  render-target patch is what makes 4:3 above 720p viable. Test mono 1440x1080
  first; if the runtime or mod letterboxes it, fall back to a 16:9 screen and
  AER/mono.

## 6. Recommended experiment order

Change one thing per run; keep the log and the artifact hashes.

1. **Baseline:** untouched `ME_Untouched` + current mod, AER default. Record
   chapter-load time, in-level fps, and the `[perf]`/`[wxr]` lines.
2. **Tweak files, no mono:** patched exe + `DefaultHudEffects.ini` +
   decompressed `Engine.u`/`TdGame.u`/`Ts_LOC_int.upk` + tuned `TdEngine.ini`.
   Set `WinlatorXrGraphics = game`, `Resolution = 1440x1080`,
   `AlternateEye = on` (AER). Confirm the game launches, the white-screen fix
   holds at 4:3, and the config survives the mod's startup.
3. **Config cut test:** set `Distortion=False`, `DepthOfField=False`,
   `LensFlares=False`, `FogVolumes=False`, `QualityBloom=False`,
   `DetailMode=1`, `MaxAnisotropy=0`, `FoliageDrawRadiusMultiplier=0`, and
   `DynamicShadows=False`, `LightEnvironmentShadows=False`. Measure. If fps is
   unchanged, the CPU draw-call limit is confirmed again; keep the cuts only
   if they improve comfort or stability.
4. **Texture LOD:** medium (max 1024, current) vs low (max 256). Measure fps,
   visual clarity, and texture streaming hitches. Texture LODs reduce memory
   bandwidth more than draw calls.
5. **Decompressed packages:** compare chapter-load times against the untouched
   compressed tree. This should not change in-level fps.
6. **OpenAL:** default OpenAL vs OpenAL Soft; `MaxChannels` 64/128/256.
   Measure fps and listen for cut-off sounds. If audio is fine, default
   OpenAL is cheaper.
7. **Mono VR:** test the implemented `MODE_VR=1, MODE_3D=0` path against AER
   and SBS at 1440x1080. This is the run that matters most for the monocular
   target.
8. **Resolution:** 1440x1080 vs 1280x720 (mono and AER) to see the pixel-cost
   curve.

## 7. Bottom line

- Copy the patched executable, `DefaultHudEffects.ini`, the decompressed
  `Engine.u`/`TdGame.u`/`Ts_LOC_int.upk`, and the tuned user `TdEngine.ini`.
  They are legitimate, low-risk improvements for load time, 4:3 support, and
  visual/comfort cuts.
- Set `WinlatorXrGraphics = game` so the mod's "restore the game's defaults"
  profile does not undo the tuned `DepthOfField`/`LensFlares`/`FogVolumes`/
  `DetailMode`/`Foliage` values.
- Do not expect the graphics cuts alone to transform frame rate. The previous
  headset measurement says the render thread's draw calls are the limit.
  **Monocular presentation is the big lever**, followed by resolution and
  draw-call/state work.
- The 1440x1080 target is a quality choice (70% more pixels than 1280x720),
  not a performance win. It is most sensible as a mono image; for stereo,
  compare AER at 1440x1080 against SBS at 2880x1080.
- Keep the game-derived files out of the repository and out of the approved
  v0.2.2 release evidence. This is a new Quest candidate, not a change to the
  approved desktop ZIP.
