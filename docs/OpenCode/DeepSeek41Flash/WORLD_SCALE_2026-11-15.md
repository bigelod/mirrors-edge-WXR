# World scale: what the engine will and will not give us

Read after: `WXRMOD_RELEASE_2026-11-07.md`. This note records a single line of
investigation on 2026-11-15, with measurements, so nobody repeats it.

## The goal

The Interstellar Marines WXR port gets its performance from rendering the 3D
world at a reduced size, then drawing first-person hands and the HUD at full
size on top. Mirror's Edge is UE3 and has no Unity-style layers or culling
masks, so the question was what the engine itself can be made to do before
worth writing a render-target composite.

## Test 1 - `ScreenPercentage` is ignored (measured)

`TdEngine.ini` `[SystemSettings]` already carries:

```
UpscaleScreenPercentage=False
ScreenPercentage=100.000000
```

Written before launch (so the engine read it at startup, not after the mod's
DllMain install), with `ScreenPercentage=50.000000` and
`UpscaleScreenPercentage=True`, then a level was loaded at `Resolution =
1920x1080`.

Result: the scene targets stayed `1920x1080` - `[rt] 2027DC60 1920x1080 fmt 21
215130 draws`, `[rt] 2027D760 1920x1080 fmt 113 306547 draws`, and `[mode]
half-res this window: fp16 raw 0, scene-classified 0 (healthy)` every window.
This engine does not honour `ScreenPercentage` for the scene render target.

**Conclusion: there is no config-level resolution scale in this build.**

## Test 2 - a smaller display mode gives a smaller FRAME, not a smaller world

The engine sizes everything from the display mode it picks, not from
`ResX/ResY` in the file. Two things were measured here:

- Offering `[960x540, 1920x1080]` in the mode list made the engine pick
  `1920x1080` (`[requested] 1920x1080`) - it takes the largest offered mode.
- Offering only `960x540` made the engine request `[requested] 960x540`, and
  overriding `BackBufferWidth/Height` to `1920x1080` in `Hook_CreateDevice` did
  **not** make it upscale. It renders a 960x540 viewport into the top-left
  quarter of the 1920x1080 backbuffer and leaves the rest black (confirmed with
  a desktop screenshot of the main menu). The mod pinned the window to
  1920x1080 afterwards, and the picture stayed a 960x540 image in the corner.

So the "wider backbuffer just enlarges the upscale" note in `d3d9.cpp` does not
extend to a *smaller* engine mode with a hand-widened backbuffer: without the
engine's own upscale pass the extra pixels are simply never written.

**Conclusion: resolution is all-or-nothing per frame.** Lowering it lowers the
HUD with the world. That is exactly what the existing `Resolution` setting
already does, and it is why it is not the layered renderer.

## What the layered renderer actually needs

From the reference implementation (`VRWorldScaler.cs`, `VRGunCamera.cs`):

1. world camera renders into a small render texture
2. a composite camera blits that texture across the full backbuffer
3. the gun pass draws at full resolution with depth cleared
4. the HUD draws last at full resolution

The equivalent here has to be built inside `d3d9.cpp`, because the engine will
not do any of it:

- **Hook `CreateTexture` / `CreateDepthStencilSurface`** and create the
  scene-colour and scene-depth targets at `frame * WorldScale` instead of full
  size. `g_sceneW/g_sceneH` and `AdoptSceneTarget` already identify these
  surfaces by size and draw count.
- **Scale the viewport for the scene pass only.** The engine sets a
  full-size viewport; drawing into a smaller target without scaling the
  viewport clips rather than downsamples. `Hook_SetViewport` already exists.
  Restore the full viewport before the post chain / final blit.
- **Composite.** The engine's post chain ends with a full-screen pass into the
  backbuffer; that pass has to sample the reduced target, which is the natural
  place for the upscale. `Hook_StretchRect` (already instrumented as
  `[blit]`) is the fallback if the engine's own blit does not stretch.
- **HUD stays at full size** because canvas/user-pointer draws already land on
  the backbuffer (`[up] user-pointer draws ... 0 onto the scene target`), which
  is measured, not assumed.
- **Hands** need the draw classifier: suppress `Mesh1p`/weapon draws in the
  scaled scene pass, then re-issue them after the composite with the depth
  buffer cleared. This is the only genuinely unknown part and should be done
  last, after world + HUD is proven.

Order of work: draw-stream instrumentation first (tag world / 1P / HUD), then
the reduced scene target + composite, then the HUD at full size, then the 1P
pass.

## Test 3 - shrinking the scene render target blanks the frame (measured)

The engine will not split the world from the HUD (Test 1 and Test 2), so the split was moved
into the mod: every render target created at backbuffer size was created at 960x540 instead,
plus a virtual viewport (SetViewport scaled, GetViewport answering the full-size rectangle the
engine asked for) so the engine's full-size drawing landed correctly inside the smaller target.
Scissor rectangles and rect-limited clears were scaled the same way.

Result: a uniform blank frame at the game's clear colour, at full frame rate, in three variants:

| Variant | Result |
| --- | --- |
| every backbuffer-sized RT shrunk, virtual viewport on | blank |
| HDR (fmt 113) scene target only, virtual viewport on | blank |
| HDR scene target only, virtual viewport **off** | blank |

The third one is the important row: with no viewport trickery at all, merely handing the engine
a smaller scene target already breaks the picture. So the failure is not the virtual viewport or
a screen-space shader constant - the renderer's own post chain assumes its scene target is the
size it asked for, and a silent mismatch leaves the frame at the clear colour.

**Conclusion: an in-place resize of the engine's own scene target is not viable.** A world/HUD
split would have to stand up an independent render path (our own target and our own composite
pass), which is a much larger change than this mod's hook layer, and it would still have to
satisfy UE3's scene pass.

## What the draw stream actually looks like (measured, `LayerTrace = on`)

One 900-frame window in gameplay, 1920x1080 mono:

```
[layer]   1920x1080 indexed   c0scene=0 backbuffer=1   72000 draws 330879600 prims
[layer]   1920x1080 indexedUP c0scene=0 backbuffer=1    8660 draws    148920 prims
[layer]   1920x1080 prim      c0scene=0 backbuffer=1     148 draws       296 prims
[layer]    2048x2048 indexed  c0scene=0 backbuffer=0   13514 draws  29057465 prims
[layer]    depth-only clears this window: 5426; draw ordinals: 19, 827, 70, 5
```

Three things follow, and all three matter for any future attempt:

- The world is ~80 draws a frame and ~4600 primitives per draw - heavily batched, on the
  backbuffer-sized target. The 2D layer is ~10 `indexedUP` draws a frame, also on that target.
  So HUD and world share a target, and only the entry point separates them.
- `c0scene=0` on **every** bucket in mono. The scene-matrix classification the stereo path uses
  is not live here, so it cannot be reused as a 1P classifier.
- Six depth-only clears a frame. A mid-frame depth clear is therefore not the "first-person pass
  starts here" marker it looks like.

## Test 4 - the performance profile never reached the engine (fixed)

This is the finding that matters most, and it was hiding behind the shadow pass.

`WxrInstallBundledConfig` and `WxrApplyQuestGraphics` run from `DllMain`. The engine reads
`TdEngine.ini` during its own startup, **before** any of our code exists, and then writes its
in-memory copy back over the file a few seconds later. Measured on 2026-11-16: every run ended
with

```
DynamicShadows=True  LightEnvironmentShadows=True  DetailMode=2  MaxMultisamples=4
MaxShadowResolution=1024
```

while the bundled file said `False/False/1/1/512`. So the Quest performance profile has never
been in effect on this machine - not the shadows, not the DoF/bloom, not the MSAA setting.

The fix is to write again **after** that startup save. `WxrApplyConfigNow()` now runs from
`DllMain` and again at frames 900 / 2700 / 5400 / 9000. The file on disk is then ours when the
next launch reads it, and the engine's own save writes our values straight back, so the profile
sticks from the second launch onward. Verified: after one run the file reads
`DynamicShadows=False, DetailMode=1, MaxMultisamples=1, MaxShadowResolution=512` and stays there.

⚠️ Consequence worth knowing: the first launch after any change to the bundled profile still runs
the old one. That is the same one-launch-late rule `Resolution = auto` already lives with.

## Test 5 - the 2048x2048 pass is not a shadow-map setting

Even with the profile actually applied, one target still takes ~15 draws and ~32k primitives a
frame:

```
[layer]   2048x2048 indexed  c0scene=0 backbuffer=0   13500 draws  29025900 prims
```

Its format decodes to `MAKEFOURCC('N','U','L','L')` - a colourless render target, so this is a
depth-only pass. It is square and 2048x2048 regardless of:
`DynamicShadows=False`, `LightEnvironmentShadows=False`, and `MaxShadowResolution=16`. None of
the shadow keys move it, so it is not the configurable shadow map.

`SkipNullDepthPass = on` drops every draw while a square, >=1024 `NULL` target is bound. Measured
in gameplay: **13,513 draws per 900-frame window skipped**, the target drops out of the census
entirely, and the game keeps rendering at the same frame rate (45-48 fps on the PC, which is
CPU-bound at ~50 in that scene, so the PC cannot show the gain). The target is left at its clear
value, which is "nothing casts from this pass" rather than a corrupted frame.

Off by default, because the visual result has not been judged in the headset yet: the expected
effect is that dynamic casters stop throwing shadows while baked lightmaps are unaffected.

**2026-11-16: now ON by default** (`SkipNullDepthPass = off` restores the pass), dropped as the
PERFTEST build. Note the counter reads 0 outside a loaded level - the target only exists in
gameplay.

## Test 6 - the profile value that stopped the engine (fixed)

With the profile finally reaching the engine, the game stopped before
`CreateDevice` - a black window after the splash, every run. Bisected on the headset:

| Config the engine reads | Result |
| --- | --- |
| profile as shipped: `DetailMode=1`, `MaxMultisamples=1` | hang |
| A: `DetailMode=1`, `MaxMultisamples=0` | boots |
| B: `DetailMode=2`, `MaxMultisamples=0` | boots |

So the culprit was `MaxMultisamples=1`. D3D9 has no 1-sample member in
`D3DMULTISAMPLE_TYPE` (NONE=0, then 2, 3, 4...), the engine passes the configured number
straight to the device check, and DXVK stalls on it - between `Direct3D9Create` and the
display-mode pass, which is exactly where all three failing logs stopped.

The profile now ships `MaxMultisamples = 0`. `DetailMode` is back to 2, the game's own value:
it is not the cause, and although 1 boots, it has never been exercised in gameplay and it
decides which cooked content is eligible, so it is not a variable to carry into the first
working drop.

⚠️ Lesson worth keeping: because the profile never applied, **no value in it had ever been
tested on the device**. A key can be both harmless in the ini and fatal when the engine
finally reads it.

## Test 7 - cutscenes belong on the 2D screen (changed)

Mirror's Edge locks the look input during cutscenes (`bCinematicMode` /
`bCinemaDisableInputLook`), so head tracking does nothing and mono VR reads as being strapped to
a tripod. The presenter already sent flat frames for a CameraActor view target, a pause and a
level load; the missing case was the camera staying on the pawn while the script owns it.

`WxrNotInControlReason()` now also reports the same condition the head-look injection stands
down under (`CinematicHeadLookRequested()`), after 45 frames so the tutorial's brief toggles do
not flash 2D. Measured on the PC, an intro cutscene that used to stay in VR:

```
*** [wxr] mono VR:  at frame 1110
*** [wxr] 2D screen: cutscene: look input is locked at frame 1180
*** [wxr] mono VR:  at frame 2150
```

The log also shows the runtime being told, `MODE_VR 2` on the way in and `MODE_VR 1` on the way
out.

## Test 8 - the depth pass is 512x512 on the device, not 2048x2048

On the device the skip counter read zero in every window while the same build skipped 13,500 a
window on the PC. `LayerTrace` (on in PERFTEST4) named it in one line:

```
[layer] 512x512 indexed  c0scene=0 backbuffer=0   12503 draws  27097271 prims
```

512x512, not 2048x2048 - the same pass (the PC reports the same ~14 draws and ~2,100 primitives
per draw), with its size following `MaxShadowResolution`, which the profile now actually applies
(512). The PC only saw 2048x2048 because the profile was not reaching the engine there yet.

The skip's size gate was ">= 1024", so it silently matched nothing at the device's 512. It is now
">= 256", still square and still `D3DFMT_NULL`. Verified on the PC: 13,500 draws a window skipped
in gameplay, unchanged by the lower gate.

Worth knowing for the next one: a threshold that is right for one machine was wrong for the
other, and the only reason it was visible is that the counter is logged even when it is zero.

## Test 9 - DetailMode is not a view-distance lever here (measured, negative)

UE3 has no global view-distance setting; the two candidates are `DetailMode` (cull actors above
the current detail level) and per-primitive `CullDistance`. `DetailMode` was A/B'd on the PC in
the same spawn, with the engine confirmed to have read the value (it saved `DetailMode=1` back
into its own config):

| Config | World draws / 900 frames | Primitives |
| --- | --- | --- |
| `DetailMode=2` | 520,143 | 197,264,810 |
| `DetailMode=1` | 525,315 | 198,348,614 |
| `DetailMode=0` | 525,375 | 198,325,874 |

No change beyond noise at any value, and no frame-rate change. DetailMode=0 boots and renders
normally, so it is not a broken value - it simply culls nothing in this content. ME's static
meshes evidently sit at or below the threshold. The key stays configurable (`DetailMode` in
mevr.ini, 0-3) because it is the engine's own setting, but it should not be counted as a
draw-call lever at any value.

The remaining view-distance lever is per-primitive `CullDistance` / `MaxDrawDistance`, which
would need a reflection walk over the level's components - doable with the machinery already in
this mod, but it hides geometry by definition and needs per-level validation.

## Test 10 - per-primitive CullDistance is unreachable in this build (measured, negative)

Written and run on the PC: walk the object table, find every object whose class contains
`StaticMeshComponent`, and clamp `CullDistance` on it once per level.

It cannot even resolve the property. This cooked build has **stripped the property chains of its
native classes**:

```
[prop] TdPlayerCamera::ViewTarget at +0x04F0   (declared on TdPlayerCamera, 26 fields walked)
[cull]   Children read ok=1 raw=0x00000000
[prop] Actor has no readable Children pointer at +0x74
[prop] StaticMeshComponent has no readable Children pointer at +0x74
```

`TdPlayerCamera` (a script class) walks 26 fields; `Actor` and `StaticMeshComponent` (native)
report a null `Children`, so no property on them can be found by name. The same signature appears
in the existing log for `WorldInfo::bDropDetail` / `bAggressiveLOD` (+0xFFFFFFFF, i.e. not found) -
it was never a bug in the lookup, it is the cook.

So the one lever that removes draw calls is not reachable through reflection here. Config keys
tried and rejected before that: `CullDistance`, `MaxDrawDistance`, `DrawDistance` on
`PrimitiveComponent`, `StaticMeshComponent`, `TdStaticMeshComponent`, `MeshComponent`, `Actor`.

## Test 11 - the frame cap is loose, and not the limiter (measured)

`FrameCap` writes `MaxSmoothedFrameRate` plus the smooth-frame-rate flag. On the PC:

| FrameCap | Observed fps |
| --- | --- |
| 60 | 59-64 |
| unlimited | 60-73 |

So it does not hold exactly at 60, and the 48 fps seen in some earlier runs was the view (a
heavier window), not the cap - the same windows that read 48 in one run read 59-64 in another
with the same setting. On the Quest, gameplay is 19-28 fps, far below any cap, so the cap cannot
be what limits it: UE3's smoothing only ever sleeps to slow a frame DOWN.

## Test 12 - temporal draw splitting (the NES trick) and our own distance cull

Both built and measured; neither helps.

**Temporal split** (`TemporalSplit = 2`): world draws are submitted on alternating frames by draw
ordinal. Boots, renders, and in the window where the count was comparable it dropped 70,141 ->
31,801. The frame rate did not move (49-50 fps either way), and a screenshot at 1080p showed a
complete image - which suggests what was skipped was the depth/prepass half of a
twice-submitted stream rather than anything visible. In a headset the same trick would put every
object at half the refresh, and a skipped draw in a depth-tested frame is a hole, not a missing
sprite. Not viable for play, but kept behind `TemporalSplit` (default 0) because it is the
cheapest way to ask the headset whether draw submission is its bottleneck: if halving the world
draws does nothing there either, the frame is not submission-bound.

**Our own distance cull**: capture the translation of the last 4x4 uploaded before each world
draw and skip it beyond N units from the camera. The capture is wrong - the last upload before a
world draw is `(0,0,0)` on register 5, not an object origin - so every draw measured as
infinitely far:

```
[layer] own distance 6000 UU: 0 drawn, 1505456 culled (last origin 0,0,0 reg 5)
```

The world disappeared entirely (screenshot: sky and a lens flare). That is the useful result: the
draw stream does not carry a per-object position this process can reach. The mod sits BELOW the
engine's spatial decisions - it sees target, entry point, primitive count and shader constants,
none of which locate a draw in the world.

## What this rules out

| Lever | Result |
| --- | --- |
| `DetailMode` 0/1/2 | identical draws |
| per-primitive `CullDistance` | property chains stripped in this cook |
| our own distance cull | no per-draw position in the stream |
| temporal half-frame | halves submissions, no fps change, not viable in VR |
| frame cap | loose, and cannot bind at 19-28 fps |

UE3 does have occlusion culling - hardware occlusion queries, which this mod already hooks and can
force visible (`OcclusionMode`), and in mono it leaves them alone - but that decision is also made
above the hooks, so the mod cannot improve on it.

## Test 13 - near plane from the view-projection (attempted twice, dead end)

TWFC-VR's UE3 mod sets `NearClip` by patching the engine's perspective function and editing its
`MinZ` argument. ME's equivalent function has no symbol, so the same value was attempted at the
point the mod already owns: the view-projection uploaded to the scene-matrix register, where
`n = -b/a` and `F = a*n/(a-1)` are recoverable from the z column.

Two attempts, both rejected, and the second one explains why the whole route is closed:

1. **Loose gate** ("camera maps to w≈0"): applied to a MENU upload, whose matrix is not a
   projection at all -
   `a = 0.602, b = -29279 -> near 48624, far -73596`. That would have written garbage into a
   camera basis, and it sat in the per-upload hot path. Reverted.
2. **Structural gate** (`0.9 < a < 1.2`, the z scale of any real perspective; strict
   `SceneCameraMatches`; pose cached once per frame) plus a diagnostic if nothing ever validated.
   Result, in gameplay:

   ```
   *** [near] no scene matrix validated in 3235 frames - near clip inert
   ```

   So in MONO the register the mod scans for never carries the scene view-projection. That
   register belongs to the stereo injection path; mono steers the game's own camera fields and
   never uploads a matrix the mod can identify.

**Conclusion: the near plane cannot be reached from the shader-constant side in mono.** Doing it
properly means hooking the engine's view-setup / perspective function directly - the method
TWFC-VR uses - which needs that function's address in ME's exe: a disassembly task (identify the
function that fills the 4x4, read its `MinZ` argument, hook it). The addresses quoted from another
project's analysis (`0x4A3800` and friends) do not apply here: ME's image base is `0x00400000`
and TWFC's is `0x10900000`.

Nothing is left in the tree; the feature has no code, no config key and no documentation claim.

## Test 14 - cutscene detection: the camera-distance fallback (added)

TWFC-VR's rule, adopted: a scripted camera can walk away from the pawn without ever setting
`bCinematicMode` or `bCinemaDisableInputLook`, so the flag test alone misses those moments. Flat
when the game camera is more than 1500 UU from the pawn for 3 frames, staying flat until it is
back under 1000 - UE3 units, so the same 15 m / 10 m they used.

This runs after the look-lock test in `WxrNotInControlReason()`, so the flags still win when they
are set and the geometric test only catches what they miss.

## Test 15 - LODDistanceFactor (found here; disproved in Test 18)

> **Corrected.** The -6% draws below came from two different runs on different parts of the level.
> A controlled within-session A/B found no effect at all, and reading the field back shows the
> engine rewrites it every frame. See **Test 18**. The keyboard below is why the property was worth
> chasing; it is not a usable lever.

Native class property chains are stripped in this cook (that is why `Actor::MaxDrawDistance` and
`StaticMeshComponent::CullDistance` cannot be found). **Script** classes keep theirs. A probe over
the script classes - `ProbeProps = on`, one pass at frame 600 - listed everything clip/distance
shaped, and one entry matters:

```
[probe]   TdPlayerController::LODDistanceFactor +0x0318
```

That is UE3's own view-distance scalar, the field the video options scale, and it is writable the
same way `DesiredFOV` already is.
## Test 16 - static search for the far plane constant (dead end, resolved in Test 17)

`tools/find-far-plane.py` scans the exe for the usual UE3 far-plane values (65536, 131072,
1048576...) and disassembles around any hit in .text. 65536 has 7 occurrences, all in .rdata/.reloc;
131072 has 1250, all false positives from instruction immediates.

The far plane is not a stored constant. Test 17 finds where it actually comes from.

## Test 17 - the engine's FPerspectiveMatrix exists, is hookable, and is NEVER CALLED

This is the one that settles far-plane clipping for this build.

**Found.** `tools/find-row-fills.py` and a raw `E8 rel32` scan located UE3's perspective
constructor at **`0x007EF890`**, and its disassembly is unambiguous:

```
007EF890  fld   [esp+4]              ; arg1 HalfFOVX
007EF894  movss xmm0,[esp+0x14]      ; arg5 MaxZ
007EF89A  fptan                      ; tan(HalfFOVX)
007EF89C  movss xmm1,[esp+0x10]      ; arg4 MinZ
007EF8A7  subss xmm2,xmm1            ; MaxZ - MinZ
007EF8AB  divss xmm0,xmm2            ; MaxZ / (MaxZ - MinZ)
007EF8C5  movss [eax+0x28],xmm3      ; M[2][2]
007EF8CA  movss [eax+0x38],xmm2      ; M[3][2]
007EF92A  movss [eax+0x2c],xmm1      ; M[2][3] = 1.0
007EF93E  ret   0x14                 ; FIVE stack args, __thiscall
```

`-MinZ*MaxZ/(MaxZ-MinZ)` is confirmed by the constant at `0x01AA2E58` being `-0.0`, so the two
arguments really are MinZ (arg4) and MaxZ (arg5). `ret 0x14` also matters mechanically: a hook
must clean up five stack dwords, so a six-float signature would corrupt the caller's stack.

**Hooked.** MinHook, signature-checked on `D9 44 24 04` before patching, with the address in one
constant. Two runtime facts from the page-counting build:

```
*** [clip] hooked FPerspectiveMatrix at 007EF890 - far plane follows the engine's culling
*** [clip] patched bytes now E9 4B 54 D0 71 (E9 = jmp, so the hook is live)
```

So the patch is genuinely in place, and the hook body never runs: a caller log printing every
distinct return address once recorded **nothing** over 5,400 frames.

**And it cannot matter.** With `FarClip = 100` - one metre, which would erase the entire world if
the hook were live - the census was unchanged:

| | World draws / 900 frames | Primitives |
| --- | --- | --- |
| FarClip off | 506,715 | 194,493,226 |
| FarClip = 100 | 492,644 | 183,044,923 |

The world still renders. **`0x007EF890` is dead code in this build**: it has only three direct
callers (two in one helper at `0x7FCE..`, one at `0xF9B92D`), none of which execute during play, so
the projection the engine actually uses is produced somewhere else - and not by any of the shapes
searched for (no per-float `divss -> [base+0x28]`, no `movaps` row fills, no x87 `fdiv -> +0x28`;
only 29 `movaps` row stores exist in 23.6 MB of .text).

**Conclusion.** Far-plane clipping is not reachable by hooking this function, and the address is
patch-specific anyway. The feature is removed: no code, no `FarClip`/`NearClip` keys, and the
probe tools (`tools/find-*.py`) stay as the record of how it was ruled out. Together with Test 9,
10, 12 and 13, the whole "move the frustum" family is now closed for this binary. The only
reachable view-distance lever is `LODDistance` from Test 15.

## Test 18 - LODDistanceFactor is a COPY the engine rewrites every frame (so Test 15 was noise)

Test 15 claimed -6% draws from `TdPlayerController::LODDistanceFactor`. That was measured across two
separate runs, and the two runs had walked different parts of the level. Re-measured properly, it
does not hold.

**Within one session**, with the value changed from the in-headset panel and the panel then closed,
and with the camera swept left/right through the same arc in both phases (900-frame censuses):

| | World draws | Primitives |
| --- | --- | --- |
| 100% | 502,108 / 533,486 / 492,056 | 182.5M / 186.1M / 182.6M |
| 25% | 489,126 / 536,631 / 547,018 / 548,754 / 544,857 / 525,219 | 182.9M / 189.3M / 201.1M / 200.5M / 198.4M / 193.5M |

No reduction, and marginally more on average. The difference from Test 15 is the camera path, not
the setting.

**Why.** Reading the field back 30 frames after the write:

```
*** [lod] LODDistanceFactor = 0.25 written to controller 269CB600 (+0x0318)
*** [lod] 30 frames on, the engine holds 1.000 (wrote 0.250)  - ENGINE OVERWRITES THE FIELD
```

The engine recomputes that property every frame, so a write from outside is always gone before the
view is built. The offset is real - it is simply not the authoritative copy.

**Removed**, along with its `LODDistance` config key and its GRAPHICS AND PERFORMANCE row. Measured
by driving the panel: `adjust id=22` -> `settings save OK` -> the value persisted in `mevr.ini` and
was re-applied live, back to `1.00 (restored)` on the way up. The setting worked end to end; there
was simply nothing behind it to tune.

**Lesson recorded:** a draw/prims difference across two different runs is not evidence. Every
remaining draw-count claim in this document is either within one run or explicitly labelled.

## Test 19 - DRAW BUDGET: a dial that provably works, and what to use it for

Every distance lever in this document is inert, and the ones that are not reachable at all are
worse. That left no way to answer the one question that matters on the device: **does draw
submission cost anything here?** You cannot move the engine's frustum, but you can refuse to forward
the draws it already issued.

`DrawBudget = N` submits one world draw in N, with the phase rotating each frame so geometry thins
out instead of vanishing. It is exposed as **GRAPHICS AND PERFORMANCE -> DRAW BUDGET**, and it is
the only setting this project has that demonstrably changes submission on this build:

```
[menu] adjust id=42 delta=1 page=3 row=1
[menu] draw budget 1/2 (50% of world draws)
[menu] settings save OK
[layer] draw budget 1/2: 274059 submitted, 274067 skipped this window
```

Half, to the draw, live from the in-headset panel, saved back as `DrawBudget = 2` and restored by
the defaults path.

**How to use it.** Stand still somewhere busy, note the frame rate, set 50%, close the panel, note
it again in the same spot. It is deliberately ugly - that is the point, it is a measurement and not
a feature.

| Result | Meaning |
| --- | --- |
| No change | DXVK/GPU draw submission is not the wall. The remaining cost is the game's own traversal and per-frame CPU, which a far plane *would* help and a budget cannot. Leave it at 1. |
| A real gain | Draws are worth attacking at the source, and the frustum hunt in Test 17 is justified. |

**Honest limitation:** skipping in the D3D9 layer removes the DXVK call and the GPU work, but the
engine has already walked its draw list by then, so it does not remove whatever Box64 spends in
the game's own submission loop. A null result therefore does not fully exonerate the draw path; a
positive result definitely incriminates the D3D9/DXVK side.

## Device session 2026-11-20 - draws are not the wall; the frame is fixed-cost

Log: `E:\tmp\VRLogs\MirrorsEdge\mevr-20261020.log`, build `87BCEFE6`, 1080p, 15,000 frames.

**Draw budget, in the headset.** The panel was driven for real: 1/2, 1/3, 1/4, 1/10, back to 1/1.
Where a window sat on one setting long enough to read:

| Budget | Frame rate |
| --- | --- |
| 1/1 (100%) | 44.2, 44.6, 46.9, 47.1 |
| 1/10 (10%) | **45.4** |

Cutting nine tenths of the world draws changed nothing. Combined with the same result on the PC,
draw submission is not the limit on either machine, and the whole frustum/LOD line of work is
correctly closed (Tests 9-19). It also rules out our per-draw hook as a significant cost, since
90% of the calls (and their hook work) disappeared.

**What the device says about our own cost.** From the mod's own timers in the same log:

```
[perf] arm update over 600 calls: mod mean/max 0.88/14.62 ms, game mean 0.06 ms
[perf] arm phases ...: wrist rotations 0.31, detached shoulders 0.23, restore overrides 0.15,
        hand position IK 0.12, combat tick 0.12, game Update1pArms 0.07, pose read 0.03
[perf] memory reads: 4632-5584 per frame (page-checked direct), 0 faulted
```

So the mod costs ~1 ms a frame on the device - 3% at 30 fps - but with **10-15 ms spikes**, which
are worth fixing separately: a spike that long is half a frame. The read count (5,000 a frame) is
the obvious place that cost comes from.

**fp16 render targets: dead end.** `FloatingPointRenderTargets=False` is accepted by the engine
(the key survives a rewrite) but the scene targets stay `fmt 113` at 1920x1080, so the config flag
does not reach RT creation in this build. The device creates four to five 1080p fp16 targets.

**Resolution is now a real dial.** `Resolution = 1280x720` was verified end to end on the PC
(`scene 1280x720 frame 1280x720`, renders, presents, 49-50 fps) and the row is now in the headset
panel for the WXR build as well (it was PC-only). This is the experiment that decides whether the
device is fill-bound: if 720p is a large win, the engine is pixel-limited and a render-scale path
with an upscale is the feature to build; if it is not, the cost is the engine's own frame and no
amount of dial-turning in this mod will move it.

## Resolution belongs to the container, and now always follows it

A 720p container is the cleanest fill-rate experiment, but the size cannot be changed from inside
it. So the mod must ask the container, not the other way round.

`Resolution` now defaults to **auto** in both the shipped ini and the in-DLL defaults, and the
launcher resolves it before anything starts: `SCREEN_WIDTH`/`SCREEN_HEIGHT` if WinlatorXR exports
them, else `EnumDisplaySettings(ENUM_CURRENT_SETTINGS)`, else `GetSystemMetrics`. It then rewrites
`mevr.ini` **and** the engine's `TdEngine.ini` (`ResX`/`ResY` in
`%USERPROFILE%\Documents\EA Games\Mirror's Edge\TdGame\Config`), which is the copy the engine
actually reads.

Verified by simulating a 720p container with the environment variables:

```
desktop from SCREEN_WIDTH/HEIGHT: 1280x720
mevr.ini Resolution = 1280x720 (from the container desktop)
TdEngine.ini updated (41269 bytes) -> ...\Documents\EA Games\Mirror's Edge\TdGame\Config\TdEngine.ini
[cfg]   Resolution = 1280x720   [requested] 1280x720
ResX=1280  ResY=720
```

The panel's RESOLUTION row was removed from the headset build again: applying it needs a restart,
and the restart goes through the launcher, which would overwrite it with the container size. A
control that can never take effect is worse than no control. PC builds keep the row.

Also fixed: the launcher did not compile at all (a duplicate `ReadAll` from an earlier edit), so
the shipped `mevr-launcher.exe` was stale. It builds now and reports the container detection in its
log.

## FOV: the screen's aspect has to decide the frustum, not the eye's

Symptom: "too wide or too tall", and the picture swims as the head turns.

The device log had the numbers:

```
[fov] headset wants 103.4 deg vertical; targeting 108.9 x 103.4 at 1.78 aspect
```

`tan(108.9/2) / tan(103.4/2) = 1.105`, but the picture is 1920x1080 = **1.778**. A rectangular
image cannot be described by a frustum whose tangents ratio differs from its aspect without a
stretch: 1.778/1.105 = **1.61x horizontally**, or equivalently everything 1.35x too tall. The mono
layer is a flat screen, so that stretch rotates with the head - which is why it is only obvious
when looking around.

Cause: with both FOV values on auto, the WinlatorXR path took **both axes from the headset's
per-eye frustum**. A per-eye frustum is nearly square (~1.05); the picture is not.

Fix: keep the horizontal anchored (WinlatorXR clamps to its native width, so exceeding it gets
squeezed - the 132-degree alternate-eye failure), and derive the vertical from the aspect of what
is actually rendered. Auto now logs the invariant:

```
[fov] HMD H 0 (auto), HMD V 0 (auto) -> targeting 108.9 x 76.4
      (tan ratio 1.778 vs image 1.778, square pixels)
```

Explicit HMD H / HMD V still win, and setting one alone derives the other, but the log now says
`*** STRETCHED - aspect mismatch` when the pair cannot describe the picture, so a deliberate
experiment is distinguishable from a bug.

**The shape limit is real, and it is the remaining lever.** At a 16:9 container, anchoring 108.9
horizontal leaves 76.4 vertical out of the eye's ~103 - the rest is unused view, not distortion.
A container whose aspect is close to the per-eye aspect (~1.05) fills the view on both axes with no
stretch at all, because then the derived vertical lands on the headset's own value. That makes the
container resolution a *geometry* control, not only a performance one.

## State left behind







- `src/d3d9.cpp` and `src/vr_menu.inl` carry: the `LayerTrace` census (default off), the
  `SkipNullDepthPass` lever (default off), and the late config re-apply that finally makes the
  Quest performance profile reach the engine. The WorldScale render-target experiment is not in
  the tree.
- The PC test copy runs a local build of that source with `LayerTrace = off`,
  `SkipNullDepthPass = off`, `Resolution = 1920x1080`, and the engine config now correctly at
  `DynamicShadows=False / DetailMode=1 / MaxMultisamples=1`.
- `docs` note: the local build is MSVC, not the reproducible clang-cl one, so `Release/` has not
  been touched and a release build is still a separate step.

## PC input notes learned the hard way

- The game destroys its first window and the mod pins a new one at device
  creation, so a cached `HWND` goes stale within seconds. Re-resolve it before
  every click.
- The game opens a 648x373 client and the mod resizes it to 1920x1080 about two
  seconds later. Click coordinates recorded at 1920x1080 must be scaled through
  the *current* client rect.
- The game pauses when it loses focus, and taking a desktop screenshot or
  running a build does not steal focus - but the editor does. Re-focus before
  every input.
- Title to gameplay, mouse-only where possible:
  1. click (1140, 649) - past "press any key"
  2. wait ~10 s
  3. click (322, 529) - **CONTINUE GAME**, the first entry, already highlighted
  4. the level then loads in a few seconds
  The left stick *click* (`LStick` in XrAPI) maps to BACK in game: it opens the
  pause menu, it does not skip the intro.
