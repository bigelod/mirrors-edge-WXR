"""Report every code window that fills a full 4x4 matrix row pair (M[2], M[3]).

A perspective projection is the only thing that writes all four of

    +0x28 M[2][2]   +0x2C M[2][3]   +0x38 M[3][2]   +0x3C M[3][3]

off one base register in one place. The out-of-line UE3 constructor is dead code in this build,
so the live one is an inlined copy - and a copy does the same four stores, only with the base in a
different register.

  python tools/find-matrix-fills.py <exe>
"""
import sys

import capstone
import pefile

SLOTS = (0x28, 0x2C, 0x38, 0x3C)


def disp_of(op_str):
    """(base_register, displacement) for a memory operand, or None."""
    if "ptr [" not in op_str or "]" not in op_str:
        return None
    mem = op_str[op_str.index("ptr [") + 5:]
    mem = mem[:mem.index("]")]
    for tok in mem.split("+"):
        tok = tok.strip()
        if tok.startswith("0x"):
            try:
                return None, int(tok, 16)
            except ValueError:
                return None
    return None


def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    va, raw, size = text.VirtualAddress, text.PointerToRawData, text.SizeOfRawData
    buf = data[raw:raw + size]
    lo_va, hi_va = base + va, base + va + size

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    stores = []        # (addr, base_reg, disp)
    off = 0
    while off < len(buf):
        got = 0
        for ins in md.disasm(buf[off:off + 0x4000], lo_va + off):
            got = ins.address - (lo_va + off) + ins.size
            if ins.mnemonic in ("movss", "mov", "movaps", "movups") and \
                    "[" in ins.op_str.split(",", 1)[0]:
                dst = ins.op_str.split(",", 1)[0]
                mem = dst[dst.index("[") + 1:dst.index("]")]
                parts = [p.strip() for p in mem.split("+")]
                if len(parts) == 2 and parts[1].startswith("0x"):
                    if parts[0].startswith("e") or parts[0].startswith("r"):
                        try:
                            stores.append((ins.address, parts[0], int(parts[1], 16)))
                        except ValueError:
                            pass
        if got == 0:
            off += 1
        else:
            off += got

    print("%d array stores decoded" % len(stores))
    by_addr = stores
    hits = []
    for i, (addr, reg, disp) in enumerate(by_addr):
        if disp != 0x28:
            continue
        window = [(a, r, d) for a, r, d in by_addr
                  if r == reg and addr - 96 <= a <= addr + 96]
        got = {d for _, _, d in window}
        if all(s in got for s in SLOTS):
            hits.append((addr, reg, window))

    print("%d windows fill the projection quartet" % len(hits))
    for addr, reg, window in hits:
        start = min(a for a, _, _ in window)
        end = max(a for a, _, _ in window)
        chunk = data[raw + (start - lo_va) - 32: raw + (end - lo_va) + 16]
        print("\n=== fill at 0x%08X base %s (0x%08X..0x%08X) ===" %
              (addr, reg, start, end))
        for ins in md.disasm(chunk, start - 32):
            mark = ""
            if ins.mnemonic.startswith("div") or ins.mnemonic.startswith("fdiv"):
                mark = "   <-- divide"
            for s in SLOTS:
                if "+ 0x%x]" % s in ins.op_str:
                    mark += "  <-- slot"
                    break
            print("  %08X  %-14s %-34s%s" % (ins.address, ins.bytes.hex(),
                                             ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
