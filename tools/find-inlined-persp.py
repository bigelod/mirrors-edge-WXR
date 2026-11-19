"""Find inlined UE3 FPerspectiveMatrix copies in a 32-bit image.

The out-of-line constructor may be dead code, and then the projection the engine actually uses is
inlined at its call site. The discriminating fact is arithmetic, not addresses: the value stored
into M[2][2] (offset +0x28) is `MaxZ / (MaxZ - MinZ)`, i.e. a *division result*. No other matrix
fill stores a freshly divided register there.

So: sweep .text instruction by instruction (resynchronising past undecodable bytes), then for every
`movss [reg+0x28], xmmN` look back a short distance for the `divss` that produced xmmN. Each hit is
printed with its neighbourhood so the projection can be read off by eye.

  python tools/find-inlined-persp.py <exe>
"""
import sys

import capstone
import pefile

WINDOW = 28          # instructions to look back for the producing divide


def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    va, raw, size = text.VirtualAddress, text.PointerToRawData, text.SizeOfRawData
    buf = data[raw:raw + size]
    img_lo, img_hi = base + va, base + va + size

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    hits = []          # addresses of movss [reg+0x28], xmmN that follow a divide into xmmN
    total = 0
    off = 0
    while off < len(buf):
        got = 0
        for ins in md.disasm(buf[off:off + 0x4000], img_lo + off):
            got = ins.address - (img_lo + off) + ins.size
            ops = ins.op_str
            if ins.mnemonic == "movss" and "ptr" in ops and "," in ops:
                dst, src = [x.strip() for x in ops.split(",", 1)]
                if dst.endswith("+ 0x28]") and src.startswith("xmm"):
                    # does the same register come out of a divss just before?
                    lo = max(img_lo, ins.address - 96)
                    chunk = data[raw + (lo - img_lo): raw + (ins.address - img_lo)]
                    for prev in md.disasm(chunk, lo):
                        if prev.mnemonic.startswith("div") and prev.op_str.startswith(src + ","):
                            hits.append(ins.address)
                            break
                    total += 1
        if got == 0:
            off += 1
        else:
            off += got

    print("%d stores to [+0x28]  (%d follow a divide)" % (total, len(hits)))
    for at in hits:
        lo = max(img_lo, at - 140)
        chunk = data[raw + (lo - img_lo): raw + (at - img_lo) + 96]
        print("\n=== inlined projection candidate at 0x%08X ===" % at)
        for ins in md.disasm(chunk, lo):
            mark = ""
            if ins.mnemonic.startswith("div"):
                mark = "   <-- divide"
            if "+ 0x28]" in ins.op_str or "+ 0x38]" in ins.op_str or "+ 0x3c]" in ins.op_str:
                mark += "  <-- matrix slot"
            if ins.address == at:
                mark += "  <<< M[2][2]"
            print("  %08X  %-14s %-32s%s" % (ins.address, ins.bytes.hex(),
                                             ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
