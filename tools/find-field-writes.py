"""Find the code that writes a known field offset, so its SOURCE can be identified.

`TdPlayerController::LODDistanceFactor` lives at +0x0318 and the engine rewrites it every frame,
which means our write is to a copy. Whatever writes it holds (or computes) the authoritative value,
and that is the thing worth changing.

0x318 needs a disp32, so a float store is `F3 0F 11 <modrm> 18 03 00 00` with modrm mod=10. This
prints every store to that offset with a window of code before it, which is enough to see whether
the value comes from a constant, from a global, or from another object's field.

  python tools/find-field-writes.py <exe> 0x318
"""
import sys

import capstone
import pefile


def main():
    path = sys.argv[1]
    off = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x318
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    va, raw, size = text.VirtualAddress, text.PointerToRawData, text.SizeOfRawData
    buf = data[raw:raw + size]
    lo_va = base + va

    disp = off.to_bytes(4, "little")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    sites = []
    # movss [reg+disp32], xmm  and  movss xmm, [reg+disp32]  both end in the displacement.
    at = buf.find(disp)
    while at != -1:
        start = max(0, at - 8)
        for ins in md.disasm(buf[start:at + 4], lo_va + start):
            if ins.address + ins.size == lo_va + at + 4:
                ops = ins.op_str
                if "[e" in ops and ins.mnemonic in ("movss", "mov", "movaps", "movups"):
                    writes = "[" in ops.split(",")[0]
                    sites.append((ins.address, ins.mnemonic, ops, writes))
                break
        at = buf.find(disp, at + 1)

    writes = [s for s in sites if s[3]]
    reads = [s for s in sites if not s[3]]
    print("%d writes, %d reads of +0x%X" % (len(writes), len(reads), off))

    for addr, mnem, ops, _ in writes[:12]:
        start = max(lo_va, addr - 90)
        print("\n=== write at 0x%08X : %s %s ===" % (addr, mnem, ops))
        chunk = data[raw + (start - lo_va): raw + (addr - lo_va) + 16]
        for ins in md.disasm(chunk, start):
            mark = "  <== WRITE" if ins.address == addr else ""
            print("  %08X  %-16s %s%s" % (ins.address, ins.bytes.hex(),
                                          ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
