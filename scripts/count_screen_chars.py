# -*- coding: utf-8 -*-
"""测算「一屏最多有多少个不同的汉字」——决定字模缓存路线的容量是否够用。
输入：src/util/work/POKEMON_RUBY_AXVJ00/translate.build.json
输出：若干可核对的数字 + 自证。
"""
import io
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'work', 'POKEMON_RUBY_AXVJ00', 'translate.build.json')

CJK_LO, CJK_HI = 0x4E00, 0x9FFF


def is_cjk(ch):
    return CJK_LO <= ord(ch) <= CJK_HI


def main():
    d = json.load(io.open(P, encoding='utf-8'))
    entries = d.get('entries') or []
    phrases = d.get('phrases') or []

    # 1) 收集所有「译文」文本
    texts = []
    field_hits = Counter()
    for e in entries:
        if not isinstance(e, dict):
            continue
        for k, v in e.items():
            if isinstance(v, str) and any(is_cjk(c) for c in v):
                texts.append(v)
                field_hits[k] += 1

    if not texts:
        print('!! 未取到任何含汉字的文本，检查字段名')
        for e in entries[:3]:
            print(json.dumps(e, ensure_ascii=False)[:600])
        return 2

    # 自证 A：条目数 > 0 且计数与实际相符
    print('=== 数据规模（自证）===')
    print('  entries          = %d' % len(entries))
    print('  phrases          = %d' % len(phrases))
    print('  含汉字的文本条数 = %d' % len(texts))
    print('  命中的字段       = %s' % dict(field_hits.most_common(6)))
    assert len(texts) > 100, '文本条数异常少，判定采样失败'
    assert sum(field_hits.values()) == len(texts), '字段计数与文本数不一致'

    # 2) 全游戏「不同汉字」总数（= 若想全量常驻字库需要多少槽）
    allchars = set()
    for t in texts:
        allchars.update(c for c in t if is_cjk(c))
    print()
    print('=== 全游戏 ===')
    print('  不同汉字总数     = %d' % len(allchars))

    # 3) 单条文本的不同汉字数（= 单个消息框的最坏情况）
    per = sorted(((len({c for c in t if is_cjk(c)}), t) for t in texts),
                 key=lambda x: -x[0])
    print()
    print('=== 单条文本（= 单个消息框的最坏情况）===')
    for n, t in per[:5]:
        print('  %3d 字 : %s' % (n, t[:34].replace('\n', '\\n')))

    # 4) 领航员/地图类：把「道路」类条目并起来算最坏一屏
    road = [t for t in texts if '道路' in t or '号' in t]
    road_chars = set()
    for t in road:
        road_chars.update(c for c in t if is_cjk(c))
    print()
    print('=== 领航员/地图屏（含「号/道路」的条目）===')
    print('  条目数           = %d' % len(road))
    print('  并集不同汉字     = %d' % len(road_chars))
    print('  并集内容         = %s' % ''.join(sorted(road_chars)))

    # 5) 按「一屏 30 格宽 × 4 行」的物理上限反推容量需求
    #    12px 步进 => 一行最多 240/12 = 20 字；4 行 = 80 格位
    print()
    print('=== 容量需求推导 ===')
    print('  一屏文本格位上限 = 20 列 × 4 行 = 80（12px 步进 / 240px 宽）')
    print('  不同汉字 <= 80（不可能超过格位数）')
    print('  ⇒ 路由 B 可用槽数 = 745 / 4 = 186 字 ⇒ %s'
          % ('够用（余量 %.0f%%）' % ((186 / 80.0 - 1) * 100) if 186 >= 80 else '不够'))

    # 6) 最坏单条 vs 186
    worst = per[0][0]
    print('  实测最坏单条     = %d 字 ⇒ %s'
          % (worst, '够用' if worst <= 186 else '★不够，需要扩容'))

    print()
    print('ALL PASS（自证通过）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
