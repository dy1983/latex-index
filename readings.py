"""
Reading utilities: compute pinyin for Chinese text with polyphone overrides,
and build Chinese sort keys that consider pinyin and stroke counts.

Polyphone file format (YAML):
# single characters
京: jing1
重: chong2
# words (preferential)
重庆: chong2 qing2
"""
from collections import defaultdict
import hashlib
import logging
from typing import Dict, Iterable, List, Optional, Tuple
import yaml
from pypinyin import lazy_pinyin, Style
import re
from hanzipy.decomposer import HanziDecomposer

CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
PINYIN_TOKEN_RE = re.compile(r"[a-zv:]+[1-5]?")
DEFAULT_STROKE_COUNT = 9999

_HANZI_DECOMPOSER = None


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


def is_chinese_char(ch: str) -> bool:
    return bool(CHINESE_CHAR_RE.fullmatch(ch))


def _get_hanzi_decomposer() -> HanziDecomposer:
    global _HANZI_DECOMPOSER
    if _HANZI_DECOMPOSER is None:
        previous_disable = logging.root.manager.disable
        logging.disable(logging.INFO)
        try:
            _HANZI_DECOMPOSER = HanziDecomposer()
        finally:
            logging.disable(previous_disable)
    return _HANZI_DECOMPOSER


def chinese_stroke_count(ch: str) -> int:
    if not is_chinese_char(ch):
        return DEFAULT_STROKE_COUNT

    try:
        info = _get_hanzi_decomposer().decompose(ch)
    except Exception:
        return DEFAULT_STROKE_COUNT

    graphical = info.get('graphical') if isinstance(info, dict) else None
    if isinstance(graphical, list) and graphical:
        return len(graphical)
    return DEFAULT_STROKE_COUNT


def _split_pinyin_tokens(value: str) -> List[str]:
    raw = value.strip().lower()
    if not raw:
        return []

    if ' ' in raw:
        return [normalize_pinyin(part) for part in raw.split() if part.strip()]

    parts = PINYIN_TOKEN_RE.findall(raw)
    if parts and ''.join(parts) == raw:
        return [normalize_pinyin(part) for part in parts]

    return [normalize_pinyin(raw)]


def _single_char_pinyin(ch: str, poly: PolyphoneDict) -> str:
    override = poly.lookup_char(ch)
    if override:
        tokens = _split_pinyin_tokens(override)
        if tokens:
            return tokens[0]

    pinyin = lazy_pinyin(ch, style=Style.TONE3, errors='default')
    if pinyin:
        return normalize_pinyin(pinyin[0])
    return ch


def text_to_pinyin_tokens(text: str, poly: PolyphoneDict = None) -> List[str]:
    poly = poly or PolyphoneDict({})
    i = 0
    text_length = len(text)
    out: List[str] = []

    while i < text_length:
        matched = False
        for seg_length in range(min(4, text_length - i), 0, -1):
            segment = text[i:i + seg_length]
            override = poly.lookup_word(segment)
            if not override:
                continue

            tokens = _split_pinyin_tokens(override)
            if len(tokens) != seg_length:
                continue

            out.extend(tokens)
            i += seg_length
            matched = True
            break

        if matched:
            continue

        ch = text[i]
        if is_chinese_char(ch):
            out.append(_single_char_pinyin(ch, poly))
        else:
            out.append(normalize_text(ch))
        i += 1

    return out


def text_to_pinyin(text: str, poly: PolyphoneDict = None) -> str:
    """Convert text to a pinyin key (tone numbers)."""
    return ' '.join(text_to_pinyin_tokens(text, poly))


def _stable_fallback_rank(ch: str) -> str:
    return hashlib.sha1(ch.encode('utf-8')).hexdigest()


def char_sort_token(ch: str, pinyin_token: Optional[str] = None) -> Tuple[str, int, int, str]:
    if is_chinese_char(ch):
        return (
            pinyin_token or ch,
            1,
            chinese_stroke_count(ch),
            _stable_fallback_rank(ch),
        )

    normalized = normalize_text(ch)
    return (normalized, 0, -1, normalized)


def text_to_sort_key(text: str, poly: PolyphoneDict = None) -> Tuple[Tuple[str, int, int, str], ...]:
    tokens = text_to_pinyin_tokens(text, poly)
    return tuple(char_sort_token(ch, tokens[idx]) for idx, ch in enumerate(text))


def collect_text_sort_warnings(texts: Iterable[str], poly: PolyphoneDict = None) -> List[str]:
    poly = poly or PolyphoneDict({})
    buckets = defaultdict(set)

    for text in texts:
        if not text:
            continue
        pinyin_tokens = text_to_pinyin_tokens(text, poly)
        for idx, ch in enumerate(text):
            if not is_chinese_char(ch):
                continue
            buckets[(idx, pinyin_tokens[idx], chinese_stroke_count(ch))].add(ch)

    warnings = []
    for (position, pinyin, strokes), chars in sorted(buckets.items()):
        if len(chars) < 2:
            continue
        warning = (
            f"第 {position + 1} 个字存在同拼音同笔画候选：{'、'.join(sorted(chars))}"
            f"（{pinyin}，{strokes} 画），当前使用稳定伪随机回退；"
            "后续可扩展为笔画顺序比较"
        )
        warnings.append(warning)

    return warnings


def normalize_pinyin(s: str) -> str:
    # normalize mixed strings like 'zhong1' or 'zhong' -> keep digits if present
    s = s.strip()
    return s.lower()


def normalize_text(s: str) -> str:
    return s.lower()
