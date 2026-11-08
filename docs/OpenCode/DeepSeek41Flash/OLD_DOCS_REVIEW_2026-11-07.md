# Review of the previous work (`docs/OldDocs/`)

Date: 2026-11-07. This note summarises what the earlier notes establish. It
does not re-verify their claims. Where the notes themselves distinguish
automated checks from headset use, that distinction is kept.

## 1. Chronology

| Period | Main work |
|---|---|
| Before 2026-08 | Original PCVR mod by letsgosportsteam; early XrAPI conversion by SgtBilko76. |
| 2026-08-21…27 | Phase 1 motion hands; arm-swing metric study (AS.0) and the game's stick/speed curve (AS.1a). |
| 2026-09-09…20 | Stereo startup fix, combat/pickup, shader-specific stereo fixes, v0.2.0/0.2.1/0.2.2-alpha, exact-file release audit, OpenXR startup diagnostics. |
| 2026-10-06…13 | WinlatorXR standalone Quest flavour: XrAPI client, frame path, menus, Box64/PhysX workarounds, performance work. |
| 2026-11-07 | Documentation rearranged into `docs/OldDocs/`, `docs/OpenCode/`, `docs/general_wxr/`. |

The docs are deliberately dated evidence. Several early limitations were later
fixed, and several late limitations are only "fixed in code, headset check
pending".

## 2. Rendering and stereo

The mod is a D3D9 proxy. It duplicates eligible draws with per-eye matrices and
viewports; it does not replace the engine's renderer.

Established findings:

- **Startup mono fallback** was caused by a render-target census keyed on raw
  COM pointers. Address reuse made old 1280x720 descriptors describe new
  full-size surfaces, so `ShouldDuplicate` and the mono guard acted on stale
  metadata. The fix validates every live descriptor, keeps failed binds from
  changing the active target, grows the census beyond 16 entries, and clears
  state on Reset. `tools/test-render-targets.ps1 -SimulateStaleCache`
  reproduces the defect. Headset visual confirmation was still requested.
- **World scissor:** the engine's mono scissor rectangle was left active during
  per-eye draws, cutting surface detail. World draws now disable that mono
  optimization for their two stereo draws and restore it afterwards.
- **Dynamic `UP` geometry** (`DrawPrimitiveUP` / `DrawIndexedPrimitiveUP`) was
  previously outside world duplication. Eligible scene draws now use the same
  per-eye routine; occlusion-only, depth-disabled composite, foreign-transform,
  and reduced-scene draws stay excluded.
- **Shader-specific corrections** were added only for captured shader pairs:
  - distant sun/haze VS/PS pairs, reanchored to the original camera position
    where eye separation created false disparity;
  - projected shadow pixel shaders, rebased to per-eye screen-depth and
    shadow matrices;
  - glass VS `8A7B075B` / PS `4577ECC3`, whose reflection lookup still uses the
    original scene matrix while POSITION uses the per-eye matrix;
  - Canvas/menu UI paths, including the tutorial prompt group and the red pause
    panel, with per-eye viewport/scissor and grouping rules;
  - lighting-mask sampling (`ScreenPositionScaleBias`) for scene-sized
    `LightAttenuationTexture` / `SceneColorTexture` inputs.
- **Lens flares:** `LensFlares = off` filters the three captured flare
  materials plus the exact sun-dot atlas pair. `NativeLensFlareSuppression`
  remains a separate, default-off option for broad native component shutdown.
- **Glass reflections remain one image shared by both eyes.** The projection
  mismatch was fixed; per-eye reflection captures were not added.
- **Missing rooftop smoke:** the draw is present and duplicated, but its input
  vertices are displaced near the world origin and its previous-position field
  is zero. The shader's depth fade then hides it behind nearby scene depth.
  This is an immediate cause, not a cause of the displacement. Shared effect
  assets matched between installations; PhysX on/off changed which smoke draw
  appeared but did not restore the plume. Investigation is tabled at the user's
  request. It was also reported in flat mode; the working test install was GOG,
  the failing install Steam, but no storefront-specific root cause was proven.

## 3. Camera, head tracking, and input

- 6-DOF head tracking adds headset position/rotation to the engine camera.
  Engine animation remains authoritative; optional pitch/roll/yaw locks live
  under Comfort.
- Scripted/cinematic cameras needed special handling. The early correction ran
  at render time, after engine visibility selection, so geometry outside the
  authored frustum could be culled. The fix applies the same camera-local
  headset rotation at the return from `TdPlayerPawn.CalcCamera`, before
  culling, and avoids applying the offset twice.
- `bIgnoreLookInput` / `bIgnoreMoveInput` during ordinary "Walking" is a
  separate scripted case from `bCinematicMode`. The old cinematic gate ignored
  it, letting controller yaw and yaw-lag correction fight the script.
- Zipline `UpdateViewRotation` cancels automatic look-at only when
  `DeltaRot.Yaw` is nonzero. Headset writes bypass that delta, so the script
  hook cancels the target and temporarily disables the move's stick look
  constraint.
- Head yaw rejection scaled with elapsed pose time (up to 45°), because a fixed
  ~11° per-frame limit discarded valid slow-frame turns.
- Input is a synthesised XInput 360 pad. Auto/Quest/Gamepad source selection,
  smooth/snap turning, and per-eye native UI scaling were added. Snap yaw
  changes the world reference without entering the accumulated headset delta.
- The physical stick remains authoritative over arm-swing locomotion; stick-back
  is the emergency stop.

## 4. Motion hands and parkour

Phase 1 plan: drive the shipped `Mesh1p` limb IK and rotation controls from
OpenXR grip poses, with an explicit game/VR ownership arbiter. Grip pose is the
hand transform; aim pose is for diagnostics and future weapon work.

- The head-relative hand transform is composed with the rendered head world
  transform, so animation and head rotation do not double-apply.
- The conservative movement whitelist starts with Walking/Falling, then Crouch;
  parkour, weapons, melee, cinematics, death/respawn and unknown states remain
  game-owned.
- `Update1pArms` is the production write point; a post-update hook writes after
  the game's own arm update. `ControlStrength`, `StrengthTarget`, and
  `BlendTimeToGo` must be written together.
- Left hand followed the controller reliably once the hook was in place. At
  full extension the shipped arm saturates and falls short of the controller;
  the plan treats that as a stop/go question before adding wrist orientation.
- Parkour uses the game's authored data where possible. The pipe-exit rewrite
  resolves `TdLadderVolume.bCanExitAtTop`, `GetLastStep`, `GetLadderLocation`,
  and `GetClosestStep`, then calls the game's own `ExitAtTop`. It removes the
  old timed descent probe and the permanent "refused pipe" state.
- The first-grab stall was caused by unconditional verification calls doing
  full object-table lookups during a grab. Those calls now require
  `ParkourGeomCensus`.

### Arm-swing locomotion — the measured result

The scheme injects into the same synthesised pad, so `ArmSwing = off` leaves the
pad untouched.

- **Metric B won:** vertical speed of each grip relative to the head, in LOCAL
  room axes. Measurement over 22,404 samples: look-around 0.04 m/s, turn on the
  spot 0.03, crouch 0.18, gesture 0.42, walk-cadence swing 0.57, run-cadence
  swing 1.58. Metric A (full relative speed) also worked but had less margin;
  anti-phase metric D failed because a body turn reads as anti-phase and
  anti-phase weakens at running cadence.
- **Use predictedDisplayTime deltas**, reject dt outside 2…50 ms, and apply the
  same 0.25 m one-frame discontinuity guard as 6-DOF. On a rejected frame,
  hold the previous velocity rather than decaying.
- **Game curve (AS.1a):** the raw stick has a 0.280 dead band and renormalises
  the rest. Base speed is `400 × (raw − 0.280) / 0.720`, fitting to 400 UU/s at
  full deflection. The `InputMaxSprintRaduisLimit = 0.7` gate is in
  post-deadzone units, so the raw gate is **0.784**. Above it, deflection stops
  mattering and the speed ramps asymptotically to **~707 UU/s** over about five
  seconds; `SprintVelocity = 630` is passed through, not a cap.
- **Envelope:** hold-then-collapse. Slow decay bridges swing reversals; after
  ~250 ms without an above-deadband sample it collapses in ~120 ms. A sag below
  0.784 drops sprint and bleeds the energy accumulator, so the hold must clear
  the gate with margin.
- **Jump** is a rising edge of hand height above a fraction of standing head
  height, held up to ~400 ms (GBA_Jump is also vault/climb/pull-up), with
  hysteresis and OR with the grip. **Crouch** is head height below a slow-rising
  standing baseline, with hysteresis; slide falls out because the game picks
  crouch versus slide from pawn speed. Leaning must be separated from crouching
  (horizontal offset, or hands dropping too).
- Every failure path (focus loss, tracking loss, cinematic/ignore-input, pad
  disabled) ramps the vector to zero rather than freezing it.

## 5. Weapons, melee, and pickup

- Supported tracked pistols: **Colt1911 and Glock18c** only. Other weapons keep
  native handling.
- Firing overrides the results of `Pawn.GetWeaponStartTraceLocation` and
  `TdWeapon.GetAdjustedAim` through the shared script interpreter, using the
  first-person muzzle location and barrel rotation. Spread still comes from
  `Weapon.AddSpread`. The runtime validates function ownership, parameter
  offsets, dispatcher identity/ABI, and a live getter before enabling.
- Left-hand holding rebases the instance's `RightWeapon` bone onto `LeftHand`.
  Per-hand wrist trim is saved to `%LOCALAPPDATA%\MirrorsEdgeVR\mevr-gun.ini`
  (legacy) or `GunLeft...`/`GunRight...` keys in `mevr.ini`; position defaults to
  zero and is limited to ±200 mm; rotation to ±90°.
- Pickup: gaze within 2 m and a 15° cone with a 12 cm minimum tolerance, line of
  sight, state/cooldown, ammo and inventory checks. The visible pickup mesh or
  rigid-body transform is preferred over actor/component origins. A blue box is
  drawn by the mod into both eyes.
- Catching: either tracked hand with grip held, 25 cm radius, swept path test.
  Drop/throw passes controller linear/angular velocity into `DropFromEx`;
  implausible or untracked velocity becomes a plain drop.
- Indexed native calls (`GetStateName`, `FastTrace`) must call the resolved
  `exec` slot, not `ProcessEvent`, because `ProcessEvent` returns immediately
  for `iNative != 0`. The adapter validates the native flag, index, exec slot,
  and module address, poisons outputs first, and contains faults.
- The four-punch combo reset gap is **0.75 s**. Every fourth accepted attack
  requests the native two-hand shove. These are accepted attacks, not confirmed
  damage hits.
- Disarm: both hands forward, both grips within 0.25 s, distance/angle gates;
  the game still performs its own target/range checks.

## 6. VR settings panel

- **Hold Y for one second** opens/closes from any page; a short Y remains the
  game's weapon action, sent on release.
- Pages: Hands and movement; Comfort; Graphics and performance; Controllers and
  turning; Calibration and menu; Troubleshooting (Debug overlay, Detailed
  Logging, FastCapture, D3D9Ex).
- Pause is requested through a short Start pulse and confirmed via
  `WorldInfo.Pauser`; the mod only resumes a pause it created.
- Settings persist to the active `mevr.ini` (beside DLL first, then LocalAppData)
  through a flushed temporary file and atomic replace, preserving comments,
  unknown keys, and duplicate-key consistency.
- Defaults recorded for v0.2.2-alpha: MotionHands **on**, ArmSwing **on**
  (jump/crouch on), Resolution **auto**, frame cap **72**, Debug **off**,
  Detailed Logging **on** (MotionHandsDebug/ArmSwingDebug/ParkourDebug on),
  LensFlares **off**, StereoUI **on**, GameUIScale 0.65, reticle **off**.
- The panel is a 1200×1000 green bitmap font on black, 1.1 m wide at 1.5 m,
  adjustable.

## 7. WinlatorXR (standalone Quest)

This section describes the October 2026 state, when alternate-eye was the
default. The 2026-11-07 WXRMOD build adds mono VR and makes it the default;
see [the release note](WXRMOD_RELEASE_2026-11-07.md).

Architecture:

- `src/winlatorxr.inl` is an in-process implementation of the OpenXR subset the
  mod calls (instance/system/session, LOCAL/VIEW spaces, `xrLocateSpace`,
  `xrLocateViews`, action system), backed by XrAPI over UDP 7872/7278. One
  packet is latched per frame so the rendered pose, head tracking, and sync
  stamp agree.
- `src/winlatorxr_frame.inl` replaces `CaptureFrame` + `SubmitTestQuad` in
  Present. It chooses side-by-side, alternate-eye, or flat screen; draws the VR
  panel per eye; stamps the 10×10 `HMD_SYNC` block; sends the forced render FOV;
  pins the window borderless at (0,0) from the window's own thread; and waits
  up to 20 ms for a fresh pose.
- There is no swapchain/compositor layer. The window **is** the output.
- `src/winlatorxr_input.inl` silences WinlatorXR's emulated keyboard/mouse on
  three routes (window messages, DirectInput devices, `GetAsyncKeyState`/
  `GetKeyState` from game code) when `WinlatorXrKeyboardMouse = off` (default).
- `src/winlatorxr_state.inl` filters redundant D3D9 render/sampler/texture
  state before DXVK. `src/winlatorxr_cpu.inl` pins heavy threads to fast cores.

Quest behaviour:

- **Alternate-eye is the default** (`WinlatorXrAlternateEye = on`): one
  full-width eye per frame, blue sync channel = eye. Headset measurement was
  ~35–42 fps against 12–21 fps side-by-side; the trade is ghosting at low frame
  rate.
- **Flat menus** (`WinlatorXrMenuScreen = flat`, default): while the player is
  not in control (menu, loading, video, cutscene, pause) the game frame goes
  untouched to WinlatorXR's 2D screen. `room` restores the curved room-fixed
  screen.
- Forced FOV is the headset's native FOV on both axes (Quest 3: 108.9 × 103.4).
  With alternate-eye, Auto resolution renders 16:9 at 80% of screen height.
- `WinlatorXrGraphics = quest` (default) rewrites existing `[SystemSettings]`
  keys before the engine reads config: shadows, motion blur, DoF, AO,
  distortion, lens flares, VSync off; DetailMode 1; shadow resolution 256;
  anisotropy 2; skeletal/particle LOD bias 1. Bloom is left alone.
- `WinlatorXrGripPitch` default 40°: grip = aim pitched up, matching the mod's
  40° wrist-down pistol calibration.
- `WinlatorXrPacing` default on: each eye frame waits until WinlatorXR has taken
  the previous one. `WinlatorXrPoseLag = auto|0..3` selects the lag used for the
  sync stamp. `WinlatorXrYawCorrection` is **off** by default because it turned
  the view away from the running direction in the headset.
- Box64 requires strong memory ordering (`STRONGMEM=2`, STABILITY preset);
  PERFORMANCE ordering produced out-of-order thread writes, null vtable reads,
  and chapter-load hangs. `-ONETHREAD` does not remove the render thread.
- PhysX: copy `Binaries\PhysXCore.bak` to `PhysXCore.dll` on the headset; the
  GOG installer's system PhysX is not present in the container.
- Frame-rate findings: `ReadProcessMemory` is 1.2–1.8 µs/call on Quest,
  `WriteProcessMemory` 80–480 µs, `VirtualQuery` 2.2–3.0 µs, page-checked
  direct read 0.3 µs. Direct writes with a fallback and page-checked reads cut
  the arm update from 25 ms to 2.6 ms. Duplicated draw calls remained the
  limit; alternate-eye was the bigger win.

The Oct 6 note says the port was tested under desktop Wine + DXVK with a
simulated XrAPI host and was **not yet verified in a headset**. Later sections
in the same note record actual headset frame rates and user comments, so the
top-of-file status is stale. Treat the later dated sections as newer evidence.

## 8. Release history and rules

| Release | Substance |
|---|---|
| v0.2.0-alpha | First feature-complete alpha: motion hands, arm swing, parkour, pistols/melee, VR settings, stereo fixes. |
| v0.2.1-alpha | Corrected shipped defaults to the tested build (pistol 40° down / −10° right, left offset 40 mm, bar exit multiplier 1.5, bar hand travel 0.15 m). |
| v0.2.2-alpha | Auto resolution as the only display mode, bounded combat-init retries, motion punch sampling independent of arm-swing logging, Debug off / Detailed Logging on. Approved after Steam VR with PhysX off. |

Release policy:

- The install ZIP contains exactly `d3d9.dll`, `openxr_loader.dll`, `mevr.ini`.
- `tools/build-reproducible-candidate.ps1` compiles all sources twice
  (`/Z7 /Brepro`, no incremental linking, stable PDB name), packages build 2
  only after its three files match build 1, and rejects source drift or file
  mismatch.
- Build 1 is the test candidate. Approval applies to the exact tested files;
  do not rebuild for a version string, regenerate the INI, normalize settings,
  or append comments after approval.
- `tools/check-tested-package.ps1` verifies the local ZIP and the downloaded
  GitHub asset against the frozen manifest. A settings comparison is not
  enough.
- The approved v0.2.2 ZIP remains `900F408ED...`; the post-test INI differed
  only in `SmoothTurnSpeed = 1` versus `1.0` (two bytes), and the user accepted
  publishing the unchanged ZIP with that formatting-only exception.
- A later **OpenXR-diagnostics candidate** (`27600FE9...` DLL, `05186AF1...`
  ZIP, source identity `28DBB747...`) was prepared on 2026-09-20 and recorded as
  awaiting headset approval. I found no later approval/publish record.

## 9. Verification levels used by the notes

Keep these separate when reading or writing new evidence:

1. **Build + required static analysis** — compiles, no new analyzer warnings.
2. **Automated regression** — production code compiled into a standalone
   harness with mocked engine/device state. Strong for logic and ABI checks,
   not proof of real-device behavior.
3. **Desktop startup / Wine + DXVK with simulated XrAPI** — proves the game
   reaches gameplay and the hooks install; does not prove headset visuals,
   latency, or comfort.
4. **Headset use** — the only level that establishes usability. Several notes
   explicitly say "fixed in code, headset check pending" or "user confirmed"
   and should not be conflated.

## 10. Open / unresolved items inherited from the old notes

| Item | State in the notes |
|---|---|
| Missing rooftop smoke | Immediate cause (displaced particles + depth fade) found; upstream cause not; tabled. |
| Steam chapter-load freeze with PhysX on | Reproduced without the mod; PhysX-off workaround; no root cause or mod fix. |
| Glass reflections shared between eyes | Known limitation; projection fixed, no per-eye capture. |
| WinlatorXR headset verification | Newer Oct 13 changes (flat menus, per-eye pacing, yaw) still need/partly have headset checks; alternate-eye has ghosting. |
| WinlatorXR frame rate | ~35–42 fps alternate-eye on Quest 3; CPU draw duplication is the limit. |
| Tutorial popup / reticle / pipe exit | Automated coverage and some user confirmation; broader headset testing still wanted. |
| Motion hands at full reach | Shipped arm saturates before the controller; needs a hybrid/custom-hand decision if it matters. |
| OpenXR diagnostics candidate | Prepared; no recorded approval/publication. |
| PhysX smoke lead | Inconclusive; PhysX off removed the captured smoke draw rather than restoring it. |
