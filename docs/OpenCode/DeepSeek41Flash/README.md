# DeepSeek V4.1 Flash — working notes

Started 2026-11-07. These are my own orientation notes after reading the
previous work in [`docs/OldDocs/`](../../OldDocs/README.md) and the general
WinlatorXR guidance in [`docs/general_wxr/`](../../general_wxr/README.md).
They are a reading summary, not a replacement for the source, the engine notes,
or newer logs.

## What I read

- All 34 files in `docs/OldDocs/` (feature plans, investigations, release
  records, and release workflow).
- [`docs/general_wxr/README.md`](../../general_wxr/README.md) and
  [`CLAUDE.md`](../../general_wxr/CLAUDE.md) for the WinlatorXR standing
  choices (XrApi 0.4/0.5, keep the 32-bit renderer, sync pixel, borderless
  window, per-pose conversion, measure on-device).
- Repository state: `git status`, recent commits, `src/` layout,
  `mevr.ini.example`, and the shipped-defaults path in `src/build_linux.py`.
- I did **not** build, launch the game, run a regression harness, or test a
  headset for these notes.

## Files here

| Note | Contents |
|---|---|
| [OLD_DOCS_REVIEW_2026-11-07.md](OLD_DOCS_REVIEW_2026-11-07.md) | What the previous notes establish, by subsystem, with dates and verification status. |
| [CURRENT_STATE_AND_NEXT_STEPS_2026-11-07.md](CURRENT_STATE_AND_NEXT_STEPS_2026-11-07.md) | Current repository/build/release state, documentation gaps, and a prioritised next-step list. |
| [PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md](PERFORMANCE_TWEAKS_REVIEW_2026-11-07.md) | Comparison of the Mirror's Edge Tweaks tree against the untouched game: patched exe, decompressed packages, config changes, Quest tuning, and the mono-VR lever. |
| [WXRMOD_RELEASE_2026-11-07.md](WXRMOD_RELEASE_2026-11-07.md) | The implemented WinlatorXR performance build: bundled-config installer, enforced profile, hashes, and the `Release/WXRMOD` overlay. |

## The short version

1. This is a fork of **letsgosportsteam/mirrors-edge-vr-mod**, with a
   WinlatorXR/XrAPI port path derived from SgtBilko76's conversion. The desktop
   OpenXR flavour and the standalone Quest flavour share almost all game code.
2. The implementation is a D3D9 proxy plus runtime reflection into the shipped
   32-bit Unreal Engine 3 game. There is no custom game package and no game
   asset replacement.
3. The last published release recorded in the notes is **v0.2.2-alpha**
   (approved after Steam VR testing with PhysX disabled). Its ZIP SHA-256 is
   `900F408ED39487246522B228A421FA9243EB5D4639F90EA175163CAB6A5C789A`.
   Release policy is exact-file: preserve the approved DLL, loader, and INI
   byte for byte.
4. A later reproducible candidate with richer OpenXR startup diagnostics
   (`05186AF1...` ZIP) was prepared on 2026-09-20 and recorded as **awaiting
   headset approval**. I found no later document that approves or publishes it.
5. The newest work (October–November 2026) is the WinlatorXR flavour: in-process
   OpenXR subset over XrAPI, mono/alternate-eye/side-by-side presentation,
   flat/room menus, Quest graphics profile, Box64 workarounds, and frame pacing.
   Headset verification and frame-rate tuning are the main open threads.
6. The two long-running tabled issues are **missing rooftop smoke** (confirmed
   displaced particle geometry, cause not established) and **Steam chapter-load
   freezes with PhysX enabled** (workaround only, no mod fix).
7. Documentation routing currently has a hole: the former `AGENTS.md` (now
   `AGENTS_OLD.md`) and the root `README.md` still point at `docs/README.md`,
   but the index moved to `docs/OldDocs/README.md` in commit `4ba0cfa`
   ("Docs re-arranged").

## Reading rule for future sessions

Treat `docs/OldDocs/` as dated evidence. A statement written in September may
have been superseded by an October WinlatorXR note or by current source. Before
acting, check the newest note for the topic, then `mevr.ini.example` /
`src/build_linux.py` for shipped defaults, then the source. Keep the four
verification levels separate: build/static analysis, automated regression,
desktop startup, and actual headset use. The old notes are careful about this;
my notes try to preserve that distinction.
