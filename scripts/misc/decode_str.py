def decode_thumb_str(h):
    # Thumb STR Rt,[Rn,#imm5*4]: 0110 0 imm5 Rn Rt
    if (h & 0xF800) == 0x6000:
        imm5 = (h >> 6) & 0x1F
        rn = (h >> 3) & 0x7
        rt = h & 0x7
        return f"str r{rt}, [r{rn}, #0x{imm5*4:X}]"
    # Thumb STR Rt,[Rn,Rm]: 0101 000 Rm Rn Rt
    if (h & 0xFE00) == 0x5000:
        rm = (h >> 6) & 0x7
        rn = (h >> 3) & 0x7
        rt = h & 0x7
        return f"str r{rt}, [r{rn}, r{rm}]"
    # Thumb STRH Rt,[Rn,#imm5*2]: 1000 0 imm5 Rn Rt
    if (h & 0xF800) == 0x8000:
        imm5 = (h >> 6) & 0x1F
        rn = (h >> 3) & 0x7
        rt = h & 0x7
        return f"strh r{rt}, [r{rn}, #0x{imm5*2:X}]"
    return f"? {h:04X}"

for h in (0x6226, 0x8286, 0x82C2, 0x8306, 0x7683, 0x76C1, 0x7704, 0x6020, 0x72A0):
    print(f'  {h:04X} -> {decode_thumb_str(h)}')
