# Current state and next steps — 2026-11-07

This note is the orientation I would want at the start of the next session.
It is not a release record and not a substitute for a build or headset test.

## Repository state

- Branch/HEAD: `4ba0cfa` — "Docs re-arranged". The old notes moved from
  `docs/` to `docs/OldDocs/`; `docs/general_wxr/` and
  `docs/OpenCode/DeepSeek41Flash/` were added.
- Working tree at the time of writing:
  - `README.md` modified: a fork header was added above the original README
    ("Mirrors Edge VR for WinlatorXR", credits, OpenCode DeepSeek V4.1 Flash).
  - `AGENTS.md` deleted and `AGENTS_OLD.md` untracked: the agent guide was
    renamed during the session, so the old standing instructions are no longer
    the active file at the tracked path.
  - `docs/general_wxr/PC_INPUT.md` untracked.
  - `mirrors-edge-WXR.code-workspace` untracked.
- Newest source commits before the docs move are WinlatorXR performance work:
  per-eye frame pacing (`34ec0ec`), render-thread profiler off by default
  (`0b3925c`), yaw lock off by default (`8b2f646`), per-thread state filter
  (`22dff8a`), yaw correction experiments, and the reverted "low" graphics
  profile (`b183984`, `6c49b1c`, `9d8254d`).

## Build flavours

| Flavour | Build | Output | Transport |
|---|---|---|---|
| Desktop OpenXR | `src/build.ps1` (Windows, x86) | `d3d9.dll`, `openxr_loader.dll`, `mevr.ini` | Virtual Desktop + VDXR |
| WinlatorXR / Quest | `src/build_linux.py --winlatorxr` | `build/winlatorxr/d3d9.dll`, generated `mevr.ini` | XrAPI UDP 7872/7278, no OpenXR loader |

The two flavours share `src/d3d9.cpp` and most `.inl` modules. The WinlatorXR
path is compiled with `MEVR_WINLATORXR`; `winlatorxr.inl` implements the
OpenXR subset, `winlatorxr_frame.inl` owns Present/presentation,
`winlatorxr_input.inl` silences Wine keyboard/mouse, `winlatorxr_state.inl`
filters redundant D3D9 state, and `winlatorxr_cpu.inl` pins threads.

## Current shipped defaults (v0.2.2-alpha / source template)

From `mevr.ini.example` and `src/build_linux.py` (both flavours embed the same
defaults):

- MotionHands **on**
- ArmSwing **on**; ArmSwingJump **on**; ArmSwingCrouch **on**
- Resolution **auto**
- FrameCap **72**
- LensFlares **off**
- NativeLensFlareSuppression **off**
- StereoUI **on**
- GameUIScale **0.65**, GameUIHeight **0**
- ShowReticle **off**
- SmoothTurnSpeed **1.0**, SnapTurnAngle **45**
- Debug **off**
- Detailed Logging **on** (`MotionHandsDebug`, `ArmSwingDebug`,
  `ParkourDebug` on)

WinlatorXR-only knobs are parsed in `src/d3d9.cpp` but are **not documented in
`mevr.ini.example`**: `WinlatorXrGraphics`, `WinlatorXrFastWrite`,
`WinlatorXrPacing`, `WinlatorXrPaceMarginMs`, `WinlatorXrStateFilter`,
`WinlatorXrStateFilterMask`, `WinlatorXrProfile`, `WinlatorXrYawCorrection`,
`WinlatorXrPoseLag`, `WinlatorXrCpuPin`, `WinlatorXrReadCache`,
`WinlatorXrFastRead`, `WinlatorXrMenuScreen`, `WinlatorXrKeyboardMouse`,
`WinlatorXrGripPitch`, and `AlternateEye`. That is a documentation gap worth
closing before asking a tester to change them.

WinlatorXR defaults in source: **mono VR** (`WinlatorXrStereo = mono`; AER and
SBS remain selectable), pacing **on**, state filter **on**, profiler **off**,
yaw correction **off**, CPU pin **on**, menu screen **flat**, keyboard/mouse
**off**, grip pitch **40°**, graphics profile **quest**.

## Release state

- The published v0.2.2-alpha record in `docs/OldDocs/` says the approved ZIP is
  `900F408ED39487246522B228A421FA9243EB5D4639F90EA175163CAB6A5C789A`.
  The user accepted the unchanged original ZIP after a two-byte
  `SmoothTurnSpeed = 1` vs `1.0` formatting-only difference in the post-test
  INI.
- A later reproducible candidate with OpenXR startup diagnostics was prepared
  on 2026-09-20 (`05186AF1...` ZIP, `27600FE9...` DLL) and recorded as
  **awaiting headset approval**. I found no later document approving or
  publishing it. Do not assume it is the release artifact.
- Release policy remains exact-file: build 1 is tested, build 2 is packaged,
  both must match, and no post-approval rebuild or INI normalization is
  allowed. The PDB must come from the packaged build.

## New local Quest candidate (2026-11-07)

A separate local overlay now exists at `Release/WXRMOD/` (gitignored). It is
not a release and not headset-tested. It combines:

- a WinlatorXR `d3d9.dll` built from this tree with a new
  `WxrInstallBundledConfig()` that copies `mevr-TdEngine.ini` into the
  Documents config before the engine reads it;
- a performance `WxrApplyQuestGraphics()` profile that enforces the
  tweak-tool values instead of resetting them;
- the patched `MirrorsEdge.exe`, modified `DefaultHudEffects.ini`,
  decompressed packages, OpenAL Soft, and `PhysXCore.dll`.

See [WXRMOD_RELEASE_2026-11-07.md](WXRMOD_RELEASE_2026-11-07.md) for the file
list, hashes, build command, and caveats. The approved desktop v0.2.2-alpha
release is unchanged.

## WinlatorXR state and open issues

- The Oct 6 note's top status says "not yet verified in a headset", but later
  dated sections in the same note record real headset results. Treat the
  later sections as newer evidence.
- Headset performance: side-by-side 11–21 fps, alternate-eye ~35–42 fps,
  no-stereo 25–37 fps, GPU ~45%. CPU draw duplication is the limit; graphics
  quality cuts did not move it much. This is the key constraint for any
  performance work.
- The current Quest graphics profile only forces dynamic/character shadows
  off and resets 18 other `[SystemSettings]` keys to the game's defaults. That
  conflicts with an aggressive tuned `TdEngine.ini`; `WinlatorXrGraphics =
  game` is the config-only escape hatch. See
  [the tweak review](PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md).
- Alternate-eye has ghosting at low frame rate; the flat menu screen and
  per-eye pacing need/partly have headset checks.
- The missing rooftop smoke investigation is tabled: displaced particle
  vertices plus zero depth-fade opacity are established, the upstream cause is
  not. Steam with PhysX on can freeze chapter loads; the workaround is PhysX
  off, no mod fix.
- Glass reflections remain one image shared between the eyes.
- Motion hands at full physical reach saturate short of the controller; that
  is an open design question, not a regression.

## Documentation gaps / hygiene

1. The former `AGENTS.md` (renamed to `AGENTS_OLD.md` during this session) and
   the root `README.md` still say `docs/README.md`, but the index moved to
   `docs/OldDocs/README.md`. The root README's `[development notes]` link
   points at a missing file. Either add a small `docs/README.md` router or
   update both references.
2. `docs/OldDocs/README.md` is the real topic index; its link to
   `../README.md` still resolves. Its `../AGENTS.md` link no longer does after
   the rename to `AGENTS_OLD.md`.
3. `docs/general_wxr/PC_INPUT.md` and `mirrors-edge-WXR.code-workspace` are
   untracked; decide whether they belong in the repository before committing.
4. `mevr.ini.example` does not document the WinlatorXR-only settings, so a
   Quest tester cannot discover `WinlatorXrGraphics = game`,
   `AlternateEye`, pacing, or menu-screen options from the file.
5. The old notes reference local `.analysis/` captures that are intentionally
   ignored. A fresh clone cannot reproduce those observations; keep that
   distinction when citing them.

## Suggested next steps

1. Fix the documentation router (`docs/README.md`) or update the replacement
   agent guide (`AGENTS_OLD.md`, or whatever replaces it) and the root README
   links. This is cheap and prevents the next agent from concluding the notes
   are missing.
2. Run the Quest performance experiment in
   [PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md](PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md):
   baseline, tweak files with `WinlatorXrGraphics = game`, then the config cut
   test, then decompressed packages, then OpenAL. One change per run.
3. **Mono VR** (`MODE_VR=1, MODE_3D=0`) is implemented in the 2026-11-07
   WXRMOD build and is the default. Test it at 1440x1080 against
   `WinlatorXrStereo = aer` and `sbs`; the remaining work is measurement, not
   implementation.
4. Only after a headset result, decide whether the Quest graphics profile
   should stop resetting DepthOfField/LensFlares/FogVolumes/DetailMode/
   Foliage, or whether `WinlatorXrGraphics = game` is the permanent policy.
5. Keep the approved desktop release evidence untouched. Game-derived files
   from the tweak tree stay in the staging/game folder, not in commits.

## What I did and did not do

- Did: read all `docs/OldDocs/` notes, read the general WinlatorXR guidance,
  inspect the repo state, compare the two game trees, diff the executable at
  the PE/byte level, verify the decompressed package headers, inspect the
  tweaked user config, and read the mod's Quest-profile and presentation code.
- Did not: build either flavour, launch the game, run a regression harness,
  copy game files, or test a headset. No source or release files were changed.
