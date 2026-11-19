"""Find far-plane candidates in a 32-bit UE3 executable.

The engine builds its view frustum from FPerspectiveMatrix(HalfFOVX, HalfFOVY, MultFOVX,
MultFOVY, MinZ, MaxZ), so the far plane is either a constant pushed at the call site or a
global. Locating those constants narrows the disassembly to a handful of addresses.

  python tools/find-far-plane.py <exe>

Reports every occurrence of the common UE3 far-plane values, and - for each one in an
executable section - disassembles the bytes around it so a projection-shaped sequence is
recognisable by eye.
"""
import struct
import sys

import capstone
import pefile

FAR_CANDIDATES = [
    65536.0, 131072.0, 262144.0, 524288.0, 1048576.0, 2097152.0,
    32768.0, 16384.0, 8192.0,
]


def sections(pe):
    out = []
    for s in pe.sections:
        name = s.Name.rstrip(b"\x00").decode("latin1")
        out.append((name, s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData,
                    s.SizeOfRawData))
    return out


def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    data = open(path, "rb").read()
    secs = sections(pe)
    print("image base 0x%08X" % base)
    for name, va, vsize, raw, rsize in secs:
        print("  %-8s VA 0x%08X size 0x%08X raw 0x%08X" % (name, va, vsize, raw))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False

    for value in FAR_CANDIDATES:
        pat = struct.pack("<f", value)
        hits = []
        at = data.find(pat)
        while at != -1:
            hits.append(at)
            at = data.find(pat, at + 1)
        if not hits:
            continue
        print("\n%g (%s): %d raw hits" % (value, "0x%08X" % struct.unpack('<I', pat)[0],
                                          len(hits)))
        for raw in hits[:6]:
            sec = next((s for s in secs if s[3] <= raw < s[3] + s[4]), None)
            if not sec:
                continue
            name, va, vsize, sraw, rsize = sec
            rva = va + (raw - sraw)
            print("  %s 0x%08X" % (name, base + rva))
            if name == ".text":
                start = max(0, raw - 48)
                chunk = data[start:raw + 48]
                for ins in md.disasm(chunk, base + va + (start - sraw)):
                    mark = " <--" if (start + (ins.address - (base + va) - (start - sraw))) == raw else ""
                    print("      0x%08X  %-24s %s%s" % (ins.address, ins.bytes.hex(),
                                                         ins.mnemonic + " " + ins.op_str, mark))


if __name__ == "__main__":
    main()
