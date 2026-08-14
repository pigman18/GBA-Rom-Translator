import re

def is_valid_japanese(text: str, min_hiragana_ratio: float = 0.02) -> bool:
    if not text or len(text.strip()) < 2:
        return False

    # 去掉空白后统计
    cleaned = text.strip()

    # 平假名 + 片假名
    kana = re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', cleaned)
    kana_count = len(kana)

    # 非日文字符（拉丁字母、西里尔、阿拉伯等明显外语）
    non_jp = re.findall(r'[^\u3040-\u30FF\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\s]', cleaned)

    # 判定
    if kana_count == 0:          # 一个假名都没有 → 无效
        return False
    if len(non_jp) > len(cleaned) * 0.3:  # 超30%非日文 → 无效
        return False

    kana_ratio = kana_count / len(cleaned)
    return kana_ratio >= min_hiragana_ratio


# 一锤子调用
print(is_valid_japanese("たＦい ぃ  ：あゾあＡＡＡＡぎ９９ぃあたさＶそ  Ｒ Ｒ Ｒ\n"))        # True
print(is_valid_japanese("这是一个中文句子"))         # False
print(is_valid_japanese("æŸä¸ªæ··æ·"))            # False（乱码）
print(is_valid_japanese("日本経済新聞"))             # False（纯汉字，零假名）
