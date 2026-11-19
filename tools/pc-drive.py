#!/usr/bin/env python3
"""Drive a full PC test run: fake XrAPI, the game, then an input plan.

PC-only test helper. Nothing here ships with the mod.

  python tools/pc-drive.py                      # launch, click, A, stick click
  python tools/pc-drive.py --plan 18:click,30:RA,70:LStick,78:LStick
  python tools/pc-drive.py --no-launch --pid 1234
  python tools/pc-drive.py --dry                # print the plan, touch nothing

Why this shape:

  * fake-xrapi must write D:\\xrtemp\\system BEFORE the game starts. The mod
    reads it at InitXR; without it there is no UDP tracking and no controller
    input, and an intro cutscene cannot be skipped.
  * The mod silences keyboard input in game, and passes mouse clicks only while
    the 2D screen is up. So "press any key" is a left click, and everything
    after it is XrAPI: A selects the first menu entry (Continue Story), and a
    left stick click skips the level intro after the 30-40 s load.
  * The game opens a small window and the mod resizes it to the full frame a
    few seconds later, so a click is mapped through the CURRENT client rect
    every time rather than through a stale one.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import replay_clicks  # noqa: E402

DEFAULT_EXE = r"E:\tmp\Q3Mods\MirrorsEdge\ME\Binaries\MirrorsEdge.exe"
DEFAULT_XR = r"D:\xrtemp"
DEFAULT_PLAN = "18:click,30:RA,70:LStick,78:LStick"


def log(msg):
    print(msg, flush=True)


def press(xr_dir, name, hold="0.25"):
    path = os.path.join(xr_dir, "press")
    # Write-then-rename: the driver may read the file at any moment, and a truncate-in-place can
    # hand it a half-written name.
    temp = path + ".tmp"
    with open(temp, "w", encoding="ascii") as f:
        f.write("%s:%s" % (name, hold))
    os.replace(temp, path)
    log("  -> XrAPI %s" % name)


def click(pid, hwnd, nx, ny, native=(1920, 1080)):
    # The game destroys its first window and the mod pins a new one at device
    # creation, so a handle cached earlier can be dead by the time we click.
    fresh = replay_clicks.find_window_by_pid(pid)
    if fresh:
        hwnd = fresh
    # The client starts at 648x373 and the mod resizes it to the full frame a few
    # seconds later. Clicking before that puts the pointer in a window whose
    # contents are not the menu yet, which silently does nothing.
    deadline = time.monotonic() + 40.0
    ox, oy, cw, ch = replay_clicks.geometry(hwnd)
    while cw < native[0] * 0.9 and time.monotonic() < deadline:
        time.sleep(0.5)
        ox, oy, cw, ch = replay_clicks.geometry(hwnd)
    if cw <= 0 or ch <= 0:
        log("  -> click skipped: no client rect (hwnd %s)" % hwnd)
        return hwnd
    px = int(round(ox + nx * cw / float(native[0])))
    py = int(round(oy + ny * ch / float(native[1])))
    replay_clicks.focus(hwnd)
    replay_clicks.user32.SetCursorPos(px, py)
    replay_clicks.user32.mouse_event(replay_clicks.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    time.sleep(0.06)
    replay_clicks.user32.mouse_event(replay_clicks.MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    log("  -> click %d,%d (hwnd %s client %dx%d)" % (px, py, hwnd, cw, ch))
    return hwnd


def log_hits(path, patterns, count=30):
    if not os.path.exists(path):
        return []
    hits = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            low = line.lower()
            if any(p in low for p in patterns):
                hits.append(line.rstrip())
    return hits[-count:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--xr-dir", default=DEFAULT_XR)
    ap.add_argument("--screen", default="1920x1080")
    ap.add_argument("--plan", default=DEFAULT_PLAN,
                    help="seconds:action, comma separated. Actions: click[:x,y], "
                         "or any XrAPI button name (RA, LStick, LTrigger, ...)")
    ap.add_argument("--click-x", type=int, default=960)
    ap.add_argument("--click-y", type=int, default=540)
    ap.add_argument("--offset", type=float, default=0.0,
                    help="seconds added to every plan time")
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--no-fake", action="store_true")
    ap.add_argument("--total", type=float, default=150.0)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    bindir = os.path.dirname(args.exe)
    logpath = os.path.join(bindir, "mevr.log")
    fake = None
    game = None

    plan = []
    for item in args.plan.split(","):
        item = item.strip()
        if not item:
            continue
        at_s, _, act = item.partition(":")
        plan.append((float(at_s) + args.offset, act))
    plan.sort()
    if not plan:
        log("empty plan")
        return 2

    if not args.dry and not args.no_fake:
        fake = subprocess.Popen(
            [sys.executable, "-u", os.path.join(HERE, "fake-xrapi.py"),
             "--dir", args.xr_dir, "--screen", args.screen,
             "--still", "--hz", "72", "--seconds", str(args.total + 60)],
            cwd=ROOT)

    if not args.no_launch:
        if args.dry:
            log("[dry] would launch %s" % args.exe)
        else:
            log("launch %s" % args.exe)
            game = subprocess.Popen([args.exe], cwd=bindir)
    launch = time.monotonic()
    pid = args.pid or (game.pid if game else 0)

    hwnd = None
    if not args.dry:
        deadline = launch + 120
        while time.monotonic() < deadline:
            hwnd = replay_clicks.find_window_by_pid(pid)
            if hwnd:
                break
            time.sleep(0.5)
        if not hwnd:
            log("no game window for pid %d; giving up" % pid)
            return 3
        ox, oy, cw, ch = replay_clicks.geometry(hwnd)
        log("window after %.1fs: client %dx%d at %d,%d"
            % (time.monotonic() - launch, cw, ch, ox, oy))

    for at, act in plan:
        wait = at - (time.monotonic() - launch)
        if args.dry:
            log("[dry] %6.1fs  %s" % (at, act))
            continue
        if wait > 0:
            time.sleep(wait)
        log("%6.1fs  %s" % (time.monotonic() - launch, act))
        if act.startswith("click"):
            parts = act.split(":", 1)
            x, y = args.click_x, args.click_y
            if len(parts) == 2 and "x" in parts[1]:
                x, y = (int(v) for v in parts[1].split("x", 1))
            hwnd = click(pid, hwnd, x, y)
        else:
            name, _, hold = act.partition(":")
            press(args.xr_dir, name, hold or "0.25")

    if args.dry:
        log("[dry] fake-xrapi would write %s\\system" % args.xr_dir)
        return 0

    remaining = args.total - (time.monotonic() - launch)
    if remaining > 0:
        time.sleep(remaining)

    log("")
    log("=== mevr.log highlights ===")
    for line in log_hits(logpath, ["[move] frame", "mono vr", "2d screen",
                                   "presenting", "udp mode", "hands-rig",
                                   "packets", "[level]", "[pad] buttons"]):
        log(line)

    if fake:
        fake.terminate()
    if game and game.poll() is None:
        log("game still running (pid %d)" % game.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
