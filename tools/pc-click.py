#!/usr/bin/env python3
"""Click the running MirrorsEdge.exe at a recorded 1920x1080 coordinate.

PC test helper. Brings the game window forward first (it pauses when it loses
focus), then scales the coordinate through the current client rect.

  python tools/pc-click.py 1140 649
  python tools/pc-click.py 322 529 --double
  python tools/pc-click.py --focus          # just bring it forward
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import replay_clicks as r  # noqa: E402


def game_pid():
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process MirrorsEdge -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("x", nargs="?", type=int)
    ap.add_argument("y", nargs="?", type=int)
    ap.add_argument("--focus", action="store_true")
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--pid", type=int, default=0)
    args = ap.parse_args()

    pid = args.pid or game_pid()
    if not pid:
        print("MirrorsEdge is not running")
        return 2
    hwnd = r.find_window_by_pid(pid)
    if not hwnd:
        print("no game window for pid %d" % pid)
        return 3
    r.focus(hwnd)
    time.sleep(0.5)
    ox, oy, cw, ch = r.geometry(hwnd)
    print("hwnd %s client %dx%d at %d,%d foreground=%s"
          % (hwnd, cw, ch, ox, oy, r.user32.GetForegroundWindow()))
    if args.focus or args.x is None:
        return 0
    px = int(round(ox + args.x * cw / 1920.0))
    py = int(round(oy + args.y * ch / 1080.0))
    for i in range(2 if args.double else 1):
        r.user32.SetCursorPos(px, py)
        r.user32.mouse_event(r.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
        time.sleep(0.06)
        r.user32.mouse_event(r.MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
        time.sleep(0.15)
    print("clicked %d,%d" % (px, py))
    return 0


if __name__ == "__main__":
    sys.exit(main())
