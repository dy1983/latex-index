"""
Reading utilities: compute pinyin for Chinese text with polyphone overrides.

Polyphone file format (YAML):
# single characters
京: jing1
重: chong2
# words (preferential)
重庆: chong2qing2
"""
from typing import Dict, Optional
import yaml
from pypinyin import lazy_pinyin, Style
import re

CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


class PolyphoneDict:
    def __init__(self, mapping: Optional[Dict[str, str]] = None):
        self.mapping = mapping or {}

    @classmethod
    def load(cls, path: Optional[str]):
        if path is None:
            return cls({})
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        # normalize keys to strings
        data = {str(k): str(v) for k, v in data.items()}
        return cls(data)

    def lookup_word(self, word: str) -> Optional[str]:
        # exact match for whole word
        return self.mapping.get(word)

    def lookup_char(self, ch: str) -> Optional[str]:
        return self.mapping.get(ch)


def text_to_pinyin(text: str, poly: PolyphoneDict = None) -> str:
    """Convert text to a pinyin key (tone numbers)."""
    poly = poly or PolyphoneDict({})
    # Try to match longer words from mapping first
    # Build result tokens
    i = 0
    N = len(text)
    out = []
    while i < N:
        # attempt longest match up to 4 chars
        matched = False
        for L in range(4, 0, -1):
            if i + L > N:
                continue
            seg = text[i:i+L]
            val = poly.lookup_word(seg)
            if val:
                out.append(normalize_pinyin(val))
                i += L
                matched = True
                break
        if matched:
            continue
        ch = text[i]
        if CHINESE_CHAR_RE.match(ch):
            override = poly.lookup_char(ch)
            if override:
                out.append(normalize_pinyin(override))
            else:
                # use pypinyin default first pronunciation
                p = lazy_pinyin(ch, style=Style.TONE3, errors='default')
                if p:
                    out.append(normalize_pinyin(p[0]))
                else:
                    out.append(ch)
        else:
            # non-chinese: lower and append
            out.append(normalize_text(ch))
        i += 1
    # join with separator to ensure correct comparisons
    return ' '.join(out)


def normalize_pinyin(s: str) -> str:
    # normalize mixed strings like 'zhong1' or 'zhong' -> keep digits if present
    s = s.strip()
    return s.lower()


def normalize_text(s: str) -> str:
    return s.lower()
