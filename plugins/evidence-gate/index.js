/**
 * evidence-gate — 阻止「没抓数据就改代码」，实现四条硬门槛。
 *
 * ## 背景（2026-11-18，52 轮未修好一个 4 字菜单 BUG）
 *
 * 1. 反复「猜公式 → 改 → 跑 bot → 看图 → 猜错」，从不用硬证据通道。
 * 2. 跑了 GDB，但只把 `textMode=0 fontNum=3` 当标签抄下来，没意识到
 *    **textMode 是决定落址算法的分派键** —— 而 `docs/POKEMON_RUBY_AXVJ00.md`
 *    §4「textMode：7 项分发表」写得清清楚楚。我是跳读文档才漏掉的。
 * 3. 错误假设会筛掉能纠正它的信息，且自己察觉不到。
 * 4. 没有「我修不了」的止损点，于是换假设试到 52 轮。
 *
 * ## 四条规则（与 scripts/evidence_gate.py 判定口径一致）
 *
 *   R1 三类证据齐全（static / gdb / bot），且都晚于上次成功构建
 *   R2 有已 PASS 的数字预测（改码前写下可证伪的值，构建后自动比对）
 *   R3 连续 3 次预测 FAILED → 强制停止，必须写出「我修不了」
 *   R4 读过机制文档：--toc 列过章节标题，且 --cite-doc 引用了结构类章节原文
 *
 * 证据与预测由 scripts/evidence_gate.py 写入 work/ 下的 jsonl 文件。
 */

import fs from 'node:fs'
import path from 'node:path'

const DEFAULTS = {
  workspace: '',
  guardedTools: ['edit', 'write', 'apply_patch'],
  protectedPrefixes: [],
  requiredKinds: ['static', 'gdb', 'bot'],
  maxConsecutiveFail: 3,
}

const KIND_LABEL = {
  static: '静态反汇编（objdump / ROM 字节 / tilemap 读回）',
  gdb: 'GDB 运行时探针（bot/run.py --gdb <probe>）',
  bot: 'bot 场景采集（bot/run.py <scene> + 帧比对）',
}

const KIND_HOWTO = {
  static: 'python scripts\\evidence_gate.py --record static --detail "objdump <addr>"',
  gdb: 'python scripts\\evidence_gate.py --record gdb --detail "bot --gdb InitTextPrinter"',
  bot: 'python scripts\\evidence_gate.py --record bot --detail "<scene> N pairs"',
}

function workPath(workspace, name) {
  return path.join(workspace, 'work', name)
}

function readJsonl(file) {
  let raw = ''
  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return []
  }
  const out = []
  for (const line of raw.split('\n')) {
    const t = line.trim()
    if (!t) continue
    try {
      out.push(JSON.parse(t))
    } catch {
      /* ignore malformed */
    }
  }
  return out
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    return null
  }
}

/** 上次成功构建时间：token 里的 built_at（不是 mtime）。 */
function lastBuildTime(workspace) {
  const tok = readJson(workPath(workspace, '.evidence_token'))
  const v = tok && tok.built_at
  return typeof v === 'number' ? v : 0
}

/** 从工具参数里取目标文件路径。 */
function targetPath(args) {
  if (!args || typeof args !== 'object') return ''
  const cand = args.file_path ?? args.path ?? args.filePath ?? args.target
  return typeof cand === 'string' ? cand : ''
}

export const name = 'evidence-gate'

export function apply(ctx, config) {
  const cfg = { ...DEFAULTS, ...(config || {}) }
  const workspace = cfg.workspace || process.cwd()
  const prefixes = cfg.protectedPrefixes.length
    ? cfg.protectedPrefixes
    : DEFAULTS.protectedPrefixes

  const isProtected = (absPath) => {
    const norm = absPath.replace(/\\/g, '/')
    return prefixes.some((pre) => norm.includes(pre.replace(/\\/g, '/')))
  }

  ctx.on('tools/pre-execute', async (execution, next) => {
    const toolName = execution?.name
    if (!cfg.guardedTools.includes(toolName)) return next()

    const tp = targetPath(execution.arguments)
    if (!tp) return next()

    const abs = path.isAbsolute(tp) ? tp : path.join(workspace, tp)
    if (!isProtected(abs)) return next()

    const problems = []

    // ---- R1：三类证据齐全，且晚于上次成功构建
    const since = lastBuildTime(workspace)
    const fresh = {}
    for (const r of readJsonl(workPath(workspace, '.evidence_log.jsonl'))) {
      if (typeof r.t !== 'number' || r.t <= since) continue
      if (cfg.requiredKinds.includes(r.kind)) fresh[r.kind] = r
    }
    const missing = cfg.requiredKinds.filter((k) => !fresh[k])
    if (missing.length) {
      problems.push(
        'R1 缺少证据：' + missing.map((k) => KIND_LABEL[k] || k).join('、'))
    }

    // ---- R2：预测已 PASS
    const pred = readJson(workPath(workspace, '.prediction.json'))
    if (!pred) {
      problems.push('R2 没有预测：改码前必须 --predict 写下可证伪的数字')
    } else if (pred.status !== 'PASS') {
      problems.push(
        `R2 预测未通过（status=${pred.status}）：「${pred.claim || '?'}」` +
        `预期 ${pred.expect || '?'}，实测 ${pred.actual ?? '未验证'}`)
    }

    // ---- R3：三连失败即停
    const ledger = readJsonl(workPath(workspace, '.prediction_ledger.jsonl'))
    let consec = 0
    for (let i = ledger.length - 1; i >= 0; i--) {
      if (ledger[i]?.status === 'FAILED') consec++
      else break
    }
    if (consec >= cfg.maxConsecutiveFail) {
      problems.push(
        `R3 连续 ${consec} 次预测失败 —— 必须停止换假设，` +
        '明确写出「我修不了」并交出已确认事实')
    }

    // ---- R4：读过机制文档（列过标题 + 引用过结构类章节原文）
    const docs = readJsonl(workPath(workspace, '.docs_read.jsonl'))
    const cited = docs.filter((d) => d && typeof d.quote === 'string' && d.quote.length >= 4)
    if (!cited.length) {
      problems.push(
        'R4 没有引用任何机制文档原文：先 --toc 列出章节标题，' +
        '再 --cite-doc 记录分发表等结构类章节的原文')
    }

    if (!problems.length) return next()

    const lines = [
      '改码被拒绝：以下硬门槛未满足。',
      '',
    ]
    for (const p of problems) lines.push(`  - ${p}`)
    lines.push(
      '',
      '这四条不是形式主义，每条都对应 2026-11-18 那次失败的具体环节：',
      '  R1 证据     → 我反复靠猜而不跑数据',
      '  R2 预测     → 我把错误猜想当成正确结果，没有可证伪的数字',
      '  R3 三连止损 → 我换假设试到 52 轮，没有「我修不了」的止损点',
      '  R4 读结构   → 我跳读文档，漏掉「textMode 7 项分发表」，',
      '                于是不知道 textMode 是决定落址算法的分派键',
      '',
      '补齐方式：',
    )
    for (const k of missing) lines.push('  ' + (KIND_HOWTO[k] || k))
    if (!pred || pred.status !== 'PASS') {
      lines.push('  python scripts\\evidence_gate.py --predict "第3个字的tile号" ' +
                 '--probe GridTile --field u --expect 0x009a')
      lines.push('  python scripts\\evidence_gate.py --verify <gdb_probe.log>')
    }
    if (!cited.length) {
      lines.push('  python scripts\\evidence_gate.py --toc docs/POKEMON_RUBY_AXVJ00.md')
      lines.push('  python scripts\\evidence_gate.py --cite-doc docs/POKEMON_RUBY_AXVJ00.md ' +
                 '--section "4. textMode" --quote "<原文一句>"')
    }

    return { kind: 'deny', reason: lines.join('\n') }
  })
}
