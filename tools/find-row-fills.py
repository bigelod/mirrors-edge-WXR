"""Find matrix fills done a whole row at a time (movaps), with a divide nearby.

If the perspective constructor was inlined and the compiler assembled each row in an XMM register,
the per-float store search misses it: rows 2 and 3 arrive as two 16-byte stores at +0x20 and +0x30.
The divide that produces MaxZ/(MaxZ-MinZ) is still in the neighbourhood, so a window with both row
stores and a divide is worth reading by eye.

  python tools/find-row-fills.py <exe>
"""
import sys

import capstone
import pefile


def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    va, raw, size = text.VirtualAddress, text.PointerToRawData, text.SizeOfRawData
    buf = data[raw:raw + size]
    lo_va = base + va

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    rows, divs = [], []
    off = 0
    while off < len(buf):
        got = 0
        for ins in md.disasm(buf[off:off + 0x4000], lo_va + off):
            got = ins.address - (lo_va + off) + ins.size
            if ins.mnemonic in ("movaps", "movups") and "[" in ins.op_str.split(",")[0]:
                dst = ins.op_str.split(",", 1)[0]
                mem = dst[dst.index("[") + 1:dst.index("]")]
                parts = [p.strip() for p in mem.split("+")]
                if len(parts) == 2 and parts[1].startswith("0x"):
                    try:
                        d = int(parts[1], 16)
                    except ValueError:
                        d = None
                    if d in (0x20, 0x30):
                        rows.append((ins.address, parts[0], d))
            if ins.mnemonic in ("divss", "divps", "fdiv", "fdivr", "fdivrp"):
                divs.append(ins.address)
        off += got if got else 1

    print("%d row stores, %d divides" % (len(rows), len(divs)))
    seen = set()
    shown = 0
    for addr, reg, d in rows:
        near = [x for x in rows if x[1] == reg and abs(x[0] - addr) <= 64]
        if {0x20, 0x30} - {x[2] for x in near}:
            continue
        if any(abs(dv - addr) > 200 for dv in divs) or not any(abs(dv - addr) <= 200 for dv in divs):
            continue
        key = addr // 64
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        if shown > 5:
            break
        start = min(x[0] for x in near) - 120
        end = max(x[0] for x in near) + 24
        print("\n=== rows fill at 0x%08X base %s ===" % (addr, reg))
        chunk = data[raw + (start - lo_va): raw + (end - lo_va)]
        for ins in md.disasm(chunk, start):
            mark = ""
            if ins.mnemonic.startswith("div") or ins.mnemonic.startswith("fdiv"):
                mark = "   <-- divide"
            if "+ 0x20]" in ins.op_str or "+ 0x30]" in ins.op_str:
                mark += "  <-- row"
            print("  %08X  %-14s %-34s%s" % (ins.address, ins.bytes.hex(),
                                             ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
