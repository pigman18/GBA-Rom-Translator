import struct
from capstone import *
from capstone.arm import *

def is_execute(rom_path, address, addressList, rom_base=0x08000000, max_trace=64):
    """
    判断 ROM 中某个地址（字符串/数据）是否被 addressList 中的任一函数"消费"。

    核心思路：
    1. 在 ROM 中搜索所有等于 target_addr 的 32-bit 值（literal pool 中的指针）
    2. 对每个 pool 地址，向前反汇编，找到 ldr rx, [pc, #imm] 指令
    3. 验证该 ldr 指令加载的地址确实等于 target_addr
    4. 从该 ldr 指令向后追踪指令流，检查是否在 max_trace 条指令内
       调用了 addressList 中的任一地址

    参数:
        rom_path:   ROM 文件路径
        address:    目标数据地址（字符串在 ROM 中的位置），可传字符串如 "0x08456789"
        addressList:消费函数地址列表，如 [0x08012345, "0x080abcde"]
        rom_base:   ROM 加载基址，默认 0x08000000（GBA 标准）
        max_trace:  从 ldr 指令向后追踪的最大指令数

    返回:
        (bool, dict) - (是否被消费, 详细信息)
    """

    with open(rom_path, 'rb') as f:
        rom = f.read()

    return _is_execute_bytes(rom, address, addressList, rom_base, max_trace)


def _is_execute_bytes(rom, address, addressList, rom_base=0x08000000, max_trace=64):
    """接受 bytes 的内部实现，方便复用。"""

    def addr2off(addr):
        return addr - rom_base

    def off2addr(off):
        return rom_base + off

    target_addr = int(address, 0) if isinstance(address, str) else int(address)
    consumers = set(int(a, 0) if isinstance(a, str) else int(a) for a in addressList)

    # === 第一步：搜索 ROM 中所有等于 target_addr 的 32-bit 值 ===
    target_bytes = struct.pack('<I', target_addr)
    pool_addrs = []
    off = 0
    while True:
        idx = rom.find(target_bytes, off)
        if idx == -1:
            break
        pool_addrs.append(off2addr(idx))
        off = idx + 4

    if not pool_addrs:
        return False, {"reason": "ROM 中未找到对该地址的 32-bit 引用"}

    # 初始化 Capstone
    md_thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_LITTLE_ENDIAN)
    md_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM + CS_MODE_LITTLE_ENDIAN)
    md_thumb.detail = True
    md_arm.detail = True

    # === 第二步：对每个 pool，寻找加载它的 ldr 指令 ===
    for pool_addr in pool_addrs:
        pool_off = addr2off(pool_addr)

        # 在 pool 之前 512 字节内搜索 ldr rx, [pc, #imm]
        search_start = max(0, pool_off - 512)

        for mode_name, md, align in [("thumb", md_thumb, 2), ("arm", md_arm, 4)]:
            for start_off in range(search_start, pool_off - 1, align):
                if start_off + 2 > len(rom):
                    continue

                try:
                    code = rom[start_off:min(start_off + 256, len(rom))]
                    for insn in md.disasm(code, off2addr(start_off)):
                        # 只检查到 pool 地址之前
                        if insn.address >= pool_addr:
                            break

                        # 必须是 ldr 且基址是 PC
                        if not insn.mnemonic.startswith('ldr'):
                            continue

                        has_pc_base = False
                        mem_disp = 0
                        for op in insn.operands:
                            if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                                has_pc_base = True
                                mem_disp = op.mem.disp
                                break

                        if not has_pc_base:
                            continue

                        # 计算该 ldr 实际加载的 pool 地址
                        if mode_name == "thumb":
                            pc_val = (insn.address + 4) & ~0x3
                        else:
                            pc_val = insn.address + 8

                        calculated_pool = pc_val + mem_disp

                        if calculated_pool != pool_addr:
                            continue

                        # === 第三步：从 ldr 向后追踪到 consumer ===
                        trace = _trace_forward(
                            rom, rom_base, insn.address, consumers,
                            mode_name, md, max_trace
                        )

                        if trace:
                            return True, {
                                "consumer": hex(trace["consumer"]),
                                "call_insn_addr": hex(trace["call_addr"]),
                                "ldr_insn": f"{insn.mnemonic} {insn.op_str}",
                                "ldr_addr": hex(insn.address),
                                "pool_addr": hex(pool_addr),
                                "trace_distance": trace["distance"],
                                "mode": mode_name
                            }

                except Exception:
                    continue

    return False, {
        "reason": "找到 literal pool 引用但未追踪到消费函数",
        "pool_addrs_found": [hex(a) for a in pool_addrs]
    }


def _trace_forward(rom, rom_base, start_addr, consumers, mode, md, max_trace):
    """
    从 start_addr 向后（地址增加方向）追踪指令流，
    看是否在 max_trace 条指令内调用了 consumers 中的任一地址。

    返回: {"consumer": addr, "call_addr": addr, "distance": int} 或 None
    """

    def addr2off(addr):
        return addr - rom_base

    off = addr2off(start_addr)
    count = 0

    while count < max_trace and off < len(rom):
        chunk = rom[off:min(off + 32, len(rom))]

        try:
            insns = list(md.disasm(chunk, rom_base + off))
        except:
            off += 2 if mode == "thumb" else 4
            count += 1
            continue

        if not insns:
            off += 2 if mode == "thumb" else 4
            count += 1
            continue

        for insn in insns:
            count += 1
            if count > max_trace:
                return None

            # 检查函数调用：bl / blx
            if insn.mnemonic in ('bl', 'blx'):
                target = None
                if insn.operands:
                    op = insn.operands[0]
                    if op.type == ARM_OP_IMM:
                        target = op.imm

                if target and target in consumers:
                    return {
                        "consumer": target,
                        "call_addr": insn.address,
                        "distance": count
                    }

            # 函数返回：停止追踪
            if insn.mnemonic == 'bx' and insn.operands:
                return None

            if insn.mnemonic == 'pop' and 'pc' in insn.op_str:
                return None

            # 无条件跳转（非函数调用）：停止追踪
            if insn.mnemonic == 'b':
                return None

            off += insn.size
            break
        else:
            off += 2 if mode == "thumb" else 4

    return None

# 假设你已知打印函数地址
print_funcs = [0x08061CF4, 0x08061D1C, 0x08002CFC]
# 检查某个字符串地址是否被打印
result, info = is_execute("C:\\code\\GBA-Rom-Translator\\roms\\origin\\POKEMON_RUBY_AXVJ00.gba", "0x08161FC8", print_funcs)
print(result)  # True / False
print(info)
# {'consumer': '0x801234', 'call_insn_addr': '0x80453210',
#  'ldr_insn': 'ldr r0, [pc, #0x4c]', 'ldr_addr': '0x80453200', ...}
