#!/usr/bin/env python3
"""Record mouse/keyboard input while MirrorsEdge.exe is the foreground process.

This is a PC-only test helper, not part of the shipped mod. It waits for the
game, then writes one JSONL event per mouse-button or key state change, with
screen coordinates for mouse events. The 1920x1080 desktop test is 1:1, so no
scaling is needed when replaying.

  python tools/pc-record-inputs.py --out tools/pc-launch-inputs-1920x1080.jsonl

Create tools/stop-recording.txt to stop early, or let --seconds expire.
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

user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wt.BOOL
kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]


def find_process(name):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return 0
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            return 0
        while True:
            if os.path.basename(pe.szExeFile).lower() == name.lower():
                return int(pe.th32ProcessID)
            if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                return 0
    finally:
        kernel32.CloseHandle(snap)


def foreground_pid():
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def cursor_pos():
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


VK_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x10: "Shift",
    0x11: "Ctrl", 0x12: "Alt", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up",
    0x27: "Right", 0x28: "Down", 0x2D: "Insert", 0x2E: "Delete",
    0x5B: "LWin", 0x5C: "RWin", 0x5D: "Menu",
    0x90: "NumLock", 0x91: "ScrollLock",
}
for _c in range(ord("0"), ord("9") + 1):
    VK_NAMES[_c] = chr(_c)
for _c in range(ord("A"), ord("Z") + 1):
    VK_NAMES[_c] = chr(_c)
for _c in range(0x60, 0x6A):
    VK_NAMES[_c] = "Num%d" % (_c - 0x60)
VK_NAMES.update({0x6A: "Num*", 0x6B: "Num+", 0x6D: "Num-", 0x6E: "Num.",
                 0x6F: "Num/"})
for _c in range(0x70, 0x7C):
    VK_NAMES[_c] = "F%d" % (_c - 0x6F)
VK_NAMES.update({0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
                 0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]",
                 0xDE: "'"})
for _c in range(0xA0, 0xA6):
    VK_NAMES[_c] = "Shift/Ctrl/Alt"


def key_name(vk):
    if vk == 0x01:
        return "MouseLeft"
    if vk == 0x02:
        return "MouseRight"
    if vk == 0x04:
        return "MouseMiddle"
    return VK_NAMES.get(vk, "VK_%02X" % vk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--name", default="MirrorsEdge.exe")
    ap.add_argument("--wait", type=float, default=900.0,
                    help="seconds to wait for the game to start")
    ap.add_argument("--seconds", type=float, default=1800.0,
                    help="seconds to record after the game starts")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "pc-launch-inputs-1920x1080.jsonl"))
    ap.add_argument("--stop", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "stop-recording.txt"))
    args = ap.parse_args()

    pid = args.pid
    if not pid:
        print("waiting for %s ..." % args.name, flush=True)
        deadline = time.monotonic() + args.wait
        while time.monotonic() < deadline:
            pid = find_process(args.name)
            if pid:
                break
            time.sleep(0.25)
        if not pid:
            print("timed out waiting for %s" % args.name, flush=True)
            return 2

    # The game may still be starting; wait until one of its windows is foreground
    # or until a short grace period expires, then record from the first event.
    print("game pid=%d; recording while it is foreground" % pid, flush=True)
    print("out: %s" % args.out, flush=True)
    print("stop file: %s" % args.stop, flush=True)

    events = []
    prev = {}
    start = time.monotonic()
    last_foreground = None
    with open(args.out, "w", encoding="ascii") as f:
        while time.monotonic() - start < args.seconds:
            if os.path.exists(args.stop):
                break
            fpid = foreground_pid()
            if fpid != last_foreground:
                last_foreground = fpid
                if fpid == pid:
                    print("foreground: game acquired", flush=True)
                elif fpid:
                    print("foreground changed to pid=%d (not the game)" % fpid,
                          flush=True)
            if fpid != pid:
                # Do not emit edges for input that happened while another
                # window owned the keyboard/mouse. Re-baseline the state so a
                # held key does not produce a false down when the game returns.
                for vk in range(1, 255):
                    prev[vk] = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                time.sleep(0.005)
                continue

            now = time.monotonic() - start
            for vk in range(1, 255):
                down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                was = prev.get(vk, False)
                if down == was:
                    continue
                prev[vk] = down
                ev = {"t": round(now, 4), "kind": "key",
                      "event": "down" if down else "up",
                      "vk": vk, "name": key_name(vk)}
                if vk in (0x01, 0x02, 0x04):
                    ev["x"], ev["y"] = cursor_pos()
                f.write(json.dumps(ev, separators=(",", ":")) + "\n")
                f.flush()
                events.append(ev)
                print(json.dumps(ev, separators=(",", ":")), flush=True)
            time.sleep(0.005)

    print("recorded %d events; %s" % (len(events), args.out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
