"""Second pass: look for the perspective build written as whole ROWS (movaps), not per float.

UE3's FMatrix is 64 bytes and MSVC happily writes it row at a time, so the per-float `movss`
search in find-perspective.py misses a compiler that assembles each row in a register first.
This looks for stores of 16 bytes at +0x20 and +0x30 (rows 2 and 3) preceded by divides.

  python tools/find-perspective-rows.py <exe>

A hit is a function that writes rows 2 and 3 of a matrix with at least two divides in the
surrounding window - the projection signature. Verified by eye from the disassembly it prints.
"""
import sys

import capstone
import pefile

# 0F 29 /r : movaps [reg+disp8], xmm   (mod=01)
MOVAPS = b"\x0F\x29"
# 0F 11 /r : movups [reg+disp8], xmm
MOVUPS = b"\x0F\x11"


def find_all(buf, pat):
    out, at = [], buf.find(pat)
    while at != -1:
        out.append(at)
        at = buf.find(pat, at + 1)
    return out


def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    va, raw, size = text.VirtualAddress, text.PointerToRawData, text.SizeOfRawData
    buf = data[raw:raw + size]

    rows = []
    for prefix in (MOVAPS, MOVUPS):
        for at in find_all(buf, prefix):
            modrm = buf[at + 2]
            if (modrm >> 6) != 1:
                continue
            disp = buf[at + 3]
            if disp in (0x20, 0x30, 0x00, 0x10):
                rows.append((at, disp))
    print("%d 16-byte stores at row offsets" % len(rows))

    cand = []
    for at, disp in rows:
        if disp not in (0x20, 0x30):
            continue
        window = [d for a, d in rows if abs(a - at) <= 64]
        if 0x20 in window and 0x30 in window:
            cand.append(at)
    cand = sorted(set(cand))
    print("%d windows writing both rows 2 and 3" % len(cand))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    shown = 0
    for at in cand:
        start = max(0, at - 160)
        chunk = buf[start:at + 96]
        divs = sum(1 for ins in md.disasm(chunk, base + va + start)
                   if ins.mnemonic.startswith("div"))
        if divs < 2:
            continue
        shown += 1
        if shown > 6:
            break
        print("\n=== rows candidate at 0x%08X (%d divides in window) ===" %
              (base + va + at, divs))
        for ins in md.disasm(chunk, base + va + start):
            mark = ""
            if ins.mnemonic.startswith("div"):
                mark = "   <-- divide"
            if "+ 0x20]" in ins.op_str or "+ 0x30]" in ins.op_str:
                mark = "  <-- matrix row"
            print("  0x%08X  %-10s %-30s%s" %
                  (ins.address, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str, mark))
    if not shown:
        print("no window with rows 2+3 and two divides - the function is likely inlined")


if __name__ == "__main__":
    main()
