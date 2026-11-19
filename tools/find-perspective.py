"""Locate UE3's FPerspectiveMatrix in a 32-bit executable.

FMatrix is `float M[4][4]`, so the projection's z/w block lands at fixed offsets:

    M[2][2] +0x28   =  MaxZ / (MaxZ - MinZ)
    M[2][3] +0x2C   =  1.0
    M[3][2] +0x38   = -MinZ * MaxZ / (MaxZ - MinZ)
    M[3][3] +0x3C   =  0.0

No other matrix-building code writes that particular quartet with two divisions and the shared
denominator, so the search is: stores to +0x28 and +0x38 within a short window, then two `divss`
with the same divisor, then a disassembly for the eye.

  python tools/find-perspective.py <exe> [--all]

Prints every candidate window with its disassembly. `--all` loosens the filter to stores only.
"""
import struct
import sys

import capstone
import pefile

# F3 0F 11 /r : movss [reg+disp8], xmm  -> the store form a matrix fill uses
STORE_PREFIX = b"\xF3\x0F\x11"


def find_all(buf, pat):
    out = []
    at = buf.find(pat)
    while at != -1:
        out.append(at)
        at = buf.find(pat, at + 1)
    return out


def disp8_store(buf, at):
    """Return the disp8 of a `movss [reg+disp8], xmm` at `at`, or None."""
    if buf[at:at + 3] != STORE_PREFIX:
        return None
    if at + 4 >= len(buf):
        return None
    modrm = buf[at + 3]
    if (modrm >> 6) != 1:          # mod=01 -> [reg + disp8]
        return None
    return buf[at + 4]


def main():
    path = sys.argv[1]
    loose = "--all" in sys.argv
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()

    text = None
    for s in pe.sections:
        if s.Name.rstrip(b"\x00") == b".text":
            text = (s.VirtualAddress, s.PointerToRawData, s.SizeOfRawData)
    if not text:
        raise SystemExit("no .text")
    va, raw, size = text
    buf = data[raw:raw + size]
    print(".text 0x%08X..0x%08X (%.1f MB)" % (base + va, base + va + size, size / 1e6))

    stores = []          # (file offset in buf, disp)
    for at in find_all(buf, STORE_PREFIX):
        d = disp8_store(buf, at)
        if d is not None:
            stores.append((at, d))

    hits = []
    for at, d in stores:
        if d != 0x28:
            continue
        window = [(a, dd) for a, dd in stores if abs(a - at) <= (160 if loose else 96)]
        disps = {dd for _, dd in window}
        want = {0x28, 0x38} if loose else {0x28, 0x2C, 0x38, 0x3C}
        if want <= disps:
            hits.append(at)
    print("%d movss stores, %d candidate windows" % (len(stores), len(hits)))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False

    def perspective_shaped(at):
        """True when the window around a +0x28 store looks like a perspective build:
        two divides, M[2][3] = 1 and M[3][3] = 0 (an affine matrix writes 1 into both)."""
        start = max(0, at - 224)
        chunk = buf[start:at + 72]
        zeroed = set()
        divs = 0
        store_3c_src = None
        store_28_src = None
        store_2c_src = None
        for ins in md.disasm(chunk, base + va + start):
            m = ins.mnemonic
            if m == "xorps" or m == "pxor":
                regs = [r.strip() for r in ins.op_str.split(",")]
                if len(regs) == 2 and regs[0] == regs[1]:
                    zeroed.add(regs[0])
            elif m.startswith("div"):
                divs += 1
            elif m == "movss" and "ptr" in ins.op_str:
                try:
                    dst, src = ins.op_str.split(",")
                except ValueError:
                    continue
                dst, src = dst.strip(), src.strip()
                if "+ 0x38]" in dst:
                    store_3c_src = src
                elif "+ 0x28]" in dst:
                    store_28_src = src
                elif "+ 0x2c]" in dst:
                    store_2c_src = src
        return (divs >= 2 and store_28_src and store_2c_src and store_3c_src and
                store_3c_src in zeroed and store_28_src != store_3c_src and
                store_2c_src != store_3c_src)

    shaped = [at for at in hits if perspective_shaped(at)]
    print("%d candidate windows are perspective-shaped" % len(shaped))

    for at in shaped[:12]:
        start = max(0, at - 224)
        chunk = buf[start:at + 72]
        print("\n=== perspective candidate at 0x%08X ===" % (base + va + at))
        for ins in md.disasm(chunk, base + va + start):
            mark = ""
            if ins.mnemonic.startswith("div"):
                mark = "   <-- divide"
            if "+ 0x28]" in ins.op_str or "+ 0x38]" in ins.op_str or "+ 0x3c]" in ins.op_str:
                mark = "  <-- projection slot"
            print("  0x%08X  %-10s %-30s%s" %
                  (ins.address, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
