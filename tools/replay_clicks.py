#!/usr/bin/env python3
"""Replay the recorded mouse-only title sequence into MirrorsEdge.exe.

This is a PC-only test helper, not part of the shipped mod. The recording in
`title-clicks-1920x1080.jsonl` was captured at a 1920x1080 client, so the
coordinates replay 1:1. Right-click events are dropped: the owner confirmed
only the left clicks are needed.

  python tools/pc-drive.py            # launch + fake-xrapi + clicks + stick
  python tools/replay-clicks.py       # clicks only, game must already run

`t` in the recording is seconds since the recorder found the process, so the
replay treats t=0 as "process start" and sleeps to each event.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.IsWindow.argtypes = [wt.HWND]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                               ctypes.c_uint, ctypes.c_void_p]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
BTN_FLAG = {"left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)}


def load_events(path, buttons):
    out = []
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("button", "left") not in buttons:
                continue
            out.append(ev)
    return out


def find_window_by_pid(pid):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) > 0 and (r.bottom - r.top) > 0:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def focus(hwnd):
    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)


def origin_of(hwnd):
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def geometry(hwnd):
    """Client rect plus its screen origin. The mod presents the backbuffer
    scaled into whatever the window client is, so a click recorded against a
    1920x1080 client has to be scaled by the current client size."""
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    ox, oy = origin_of(hwnd)
    return ox, oy, max(0, r.right - r.left), max(0, r.bottom - r.top)


def replay(hwnd, events, speed=1.0, extra_delay=0.0, dry=False, ref=None,
           native=(1920, 1080)):
    focus(hwnd)
    time.sleep(0.3)

    # Wait until the client size stops changing: the game creates its window
    # small and the mod resizes it to the full frame a few seconds later.
    last = None
    stable_since = time.monotonic()
    while time.monotonic() - stable_since < 1.0:
        ox, oy, cw, ch = geometry(hwnd)
        if (cw, ch) != last:
            last = (cw, ch)
            stable_since = time.monotonic()
        time.sleep(0.2)
    ox, oy, cw, ch = geometry(hwnd)
    print("window client %dx%d at %d,%d (recorded %dx%d)"
          % (cw, ch, ox, oy, native[0], native[1]), flush=True)

    base = ref if ref is not None else time.monotonic()
    for ev in events:
        target = ev["t"] / speed + extra_delay
        delay = (base + target) - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        down, up = BTN_FLAG[ev.get("button", "left")]
        ox, oy, cw, ch = geometry(hwnd)
        sx, sy = cw / float(native[0]), ch / float(native[1])
        px = int(round(ox + ev["x"] * sx))
        py = int(round(oy + ev["y"] * sy))
        if not dry:
            user32.SetCursorPos(px, py)
            user32.mouse_event(down if ev["event"] == "down" else up, 0, 0, 0, None)
        print("%7.3fs  %-4s %-5s  %d,%d  (client %dx%d)"
              % (target, ev["event"], ev.get("button", "left"), px, py, cw, ch),
              flush=True)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(here, "title-clicks-1920x1080.jsonl"))
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--hwnd", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--buttons", default="left", help="comma list: left,right")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--delay", type=float, default=0.0,
                    help="extra seconds before the first event")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    pid = args.pid
    if not pid and not args.hwnd:
        print("need --pid or --hwnd", flush=True)
        return 2
    hwnd = args.hwnd or find_window_by_pid(pid)
    deadline = time.monotonic() + 30
    while (not hwnd or not user32.IsWindow(hwnd)) and time.monotonic() < deadline:
        time.sleep(0.5)
        hwnd = args.hwnd or find_window_by_pid(pid)
    if not hwnd:
        print("no window for pid %d" % pid, flush=True)
        return 3

    events = load_events(args.file, set(args.buttons.split(",")))
    print("%d events from %s" % (len(events), args.file), flush=True)
    replay(hwnd, events, args.speed, args.delay, args.dry)
    print("replay finished", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
