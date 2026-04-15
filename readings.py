"""
Reading utilities: compute pinyin for Chinese text with polyphone overrides,
manage a small stroke-order template that grows on demand, and build Chinese
sort keys that consider pinyin, authoritative total stroke counts, optional
stroke-order metadata, and stable fallback ordering.

Polyphone file format (YAML):
# single characters
京: jing1
重: chong2
# words (preferential)
重庆: chong2 qing2
"""
from collections import defaultdict
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import urllib.parse
import urllib.request
import yaml
from pypinyin import Style, lazy_pinyin
import re

CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
PINYIN_TOKEN_RE = re.compile(r"[a-zv:]+[1-5]?")
DEFAULT_STROKE_COUNT = 9999
DATA_DIR = Path(__file__).with_name('data')
UNIHAN_TOTAL_STROKES_PATH = DATA_DIR / 'unihan_total_strokes.json'
DEFAULT_POLYPHONE_PATH = DATA_DIR / 'poly.yaml'
DEFAULT_STROKE_ORDER_PATH = DATA_DIR / 'stroke_order.yaml'
STROKE_ORDER_PROVIDER_URLS = (
    'https://cdn.jsdelivr.net/npm/hanzi-writer-data@latest/{quoted}.json',
    'https://unpkg.com/hanzi-writer-data@latest/{quoted}.json',
)
DEFAULT_STROKE_ORDER_TEMPLATE = {
    '一': {
        'sequence': ['H'],
        'source': 'seed',
    },
    '二': {
        'sequence': ['H', 'H'],
        'source': 'seed',
    },
}
MIN_STROKE_SEGMENT_LENGTH = 12.0
SHORT_DOT_THRESHOLD = 90.0
STROKE_ORDER_ALIASES = {
    'H': 'H',
    'h': 'H',
    '横': 'H',
    '一': 'H',
    'S': 'S',
    's': 'S',
    '竖': 'S',
    '丨': 'S',
    'P': 'P',
    'p': 'P',
    '撇': 'P',
    '丿': 'P',
    'N': 'N',
    'n': 'N',
    '捺': 'N',
    '㇏': 'N',
    '乀': 'N',
    'D': 'D',
    'd': 'D',
    '点': 'D',
    '丶': 'D',
    '、': 'D',
    'T': 'T',
    't': 'T',
    '提': 'T',
    '㇀': 'T',
    'Z': 'Z',
    'z': 'Z',
    '折': 'Z',
    '㇄': 'Z',
    '㇅': 'Z',
    '㇆': 'Z',
    '㇇': 'Z',
    '㇈': 'Z',
    '㇉': 'Z',
    '㇋': 'Z',
    '㇌': 'Z',
    '㇍': 'Z',
    '㇎': 'Z',
    '㇕': 'Z',
    '㇖': 'Z',
    '㇗': 'Z',
    '㇙': 'Z',
    '㇚': 'Z',
    'G': 'G',
    'g': 'G',
    '钩': 'G',
    '钩': 'G',
}
STROKE_ORDER_TOKENS = ('H', 'S', 'P', 'N', 'D', 'T', 'Z', 'G')
STROKE_ORDER_PRIORITY = {token: idx for idx, token in enumerate(STROKE_ORDER_TOKENS)}
StrokeSignature = Tuple[int, ...]
StrokeOrderKey = Tuple[StrokeSignature, ...]
CharSortToken = Tuple[str, int, int, Optional[StrokeOrderKey], str]


def _compare_values(left, right) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def serialize_stroke_order(sequence: StrokeOrderKey) -> List[str]:
    serialized = []
    for stroke in sequence:
        serialized.append(''.join(STROKE_ORDER_TOKENS[idx] for idx in stroke))
    return serialized


def _stroke_order_value_payload(value: object) -> object:
    if isinstance(value, dict):
        return value.get('sequence') or value.get('strokes') or value.get('stroke_order')
    return value


def _canonical_stroke_entry(value: object, sequence: StrokeOrderKey, default_source: str) -> Dict[str, object]:
    entry: Dict[str, object] = {
        'sequence': serialize_stroke_order(sequence),
        'source': default_source,
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'sequence', 'strokes', 'stroke_order'}:
                continue
            entry[str(key)] = item
        if value.get('source'):
            entry['source'] = value['source']
    return entry


class StrokeOrderDict:
    def __init__(self, mapping: Optional[Dict[str, object]] = None, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else DEFAULT_STROKE_ORDER_PATH
        self.mapping: Dict[str, StrokeOrderKey] = {}
        self.raw_mapping: Dict[str, Dict[str, object]] = {}
        self.last_auto_added: List[str] = []
        self.auto_added_chars: List[str] = []
        for key, value in (mapping or {}).items():
            text = str(key)
            if len(text) != 1:
                continue
            sequence = normalize_stroke_order(value)
            if sequence:
                self.mapping[text] = sequence
                self.raw_mapping[text] = _canonical_stroke_entry(value, sequence, default_source='manual')

    @classmethod
    def load(cls, path: Optional[str]):
        resolved_path = Path(path) if path else DEFAULT_STROKE_ORDER_PATH
        if not resolved_path.exists():
            cls._write_template_file(resolved_path, DEFAULT_STROKE_ORDER_TEMPLATE)
            data = DEFAULT_STROKE_ORDER_TEMPLATE
        else:
            suffix = resolved_path.suffix.lower()
            with open(resolved_path, 'r', encoding='utf-8') as f:
                if suffix == '.json':
                    data = json.load(f) or {}
                else:
                    data = yaml.safe_load(f) or {}

        data = {str(k): v for k, v in data.items()}
        return cls(data, resolved_path)

    @staticmethod
    def _write_template_file(path: Path, data: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == '.json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write('\n')
            return

        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def save(self) -> None:
        self._write_template_file(self.path, self.raw_mapping)

    def lookup_char(self, ch: str) -> Optional[StrokeOrderKey]:
        return self.mapping.get(ch)

    def ensure_for_texts(self, texts: Iterable[str], poly: Optional['PolyphoneDict'] = None) -> List[str]:
        poly = poly or PolyphoneDict({})
        missing = [
            ch
            for ch in sorted(collect_ambiguous_chinese_chars(texts, poly))
            if self.lookup_char(ch) is None
        ]
        added: List[str] = []
        for ch in missing:
            sequence = fetch_stroke_order_sequence(ch)
            if not sequence:
                continue
            self.mapping[ch] = sequence
            self.raw_mapping[ch] = {
                'sequence': serialize_stroke_order(sequence),
                'source': 'hanzi-writer-data',
            }
            added.append(ch)

        if added:
            self.save()
            for ch in added:
                if ch not in self.auto_added_chars:
                    self.auto_added_chars.append(ch)
            self.last_auto_added = added
        return added


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


@lru_cache(maxsize=1)
def _load_unihan_total_strokes() -> Dict[str, int]:
    if not UNIHAN_TOTAL_STROKES_PATH.exists():
        raise FileNotFoundError(
            f"Bundled Unihan stroke table not found: {UNIHAN_TOTAL_STROKES_PATH}"
        )

    with open(UNIHAN_TOTAL_STROKES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {str(k): int(v) for k, v in data.items()}


def normalize_stroke_order(value: object) -> StrokeOrderKey:
    raw_value = _stroke_order_value_payload(value)
    if raw_value is None:
        return ()

    if isinstance(raw_value, (list, tuple)):
        raw_strokes = list(raw_value)
    else:
        raw_text = str(raw_value).strip()
        if not raw_text:
            return ()
        raw_strokes = raw_text.split('/') if '/' in raw_text else [raw_text]

    strokes: List[StrokeSignature] = []
    for raw_stroke in raw_strokes:
        if isinstance(raw_stroke, dict):
            raw_stroke = _stroke_order_value_payload(raw_stroke)
        if raw_stroke is None:
            continue
        if isinstance(raw_stroke, (list, tuple)) and raw_stroke and all(isinstance(item, int) for item in raw_stroke):
            strokes.append(tuple(int(item) for item in raw_stroke))
            continue

        if isinstance(raw_stroke, (list, tuple)):
            raw_text = ''.join(str(part) for part in raw_stroke)
        else:
            raw_text = str(raw_stroke)

        signature: List[int] = []
        for ch in raw_text:
            if ch.isspace() or ch in {',', '，', ';', '；', '|', '-', '_', '>', '→'}:
                continue
            token = STROKE_ORDER_ALIASES.get(ch)
            if token is None:
                raise ValueError(f"Unsupported stroke-order token: {ch}")
            signature.append(STROKE_ORDER_PRIORITY[token])
        if signature:
            strokes.append(tuple(signature))

    return tuple(strokes)


def _stroke_segment_token(dx: float, dy: float) -> str:
    adx = abs(dx)
    ady = abs(dy)
    if adx >= ady * 2.2:
        return 'H'
    if ady >= adx * 2.2:
        return 'S'
    if dx > 0 and dy < 0:
        return 'N'
    if dx < 0 and dy < 0:
        return 'P'
    if dx > 0 and dy > 0:
        return 'T'
    return 'Z'


def _stroke_signature(points: List[List[float]]) -> StrokeSignature:
    segments: List[str] = []
    total_length = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < MIN_STROKE_SEGMENT_LENGTH:
            continue
        total_length += length
        token = _stroke_segment_token(dx, dy)
        if not segments or segments[-1] != token:
            segments.append(token)

    if not segments:
        return (STROKE_ORDER_PRIORITY['D'],)

    if len(segments) == 1 and segments[0] in {'N', 'P'} and total_length < SHORT_DOT_THRESHOLD:
        return (STROKE_ORDER_PRIORITY['D'],)

    return tuple(STROKE_ORDER_PRIORITY[token] for token in segments)


def _fetch_remote_stroke_data(ch: str) -> Optional[Dict[str, object]]:
    quoted = urllib.parse.quote(ch)
    for url_template in STROKE_ORDER_PROVIDER_URLS:
        url = url_template.format(quoted=quoted)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return json.load(resp)
        except Exception:
            continue
    return None


def fetch_stroke_order_sequence(ch: str) -> StrokeOrderKey:
    if not is_chinese_char(ch):
        return ()

    data = _fetch_remote_stroke_data(ch)
    if not data:
        return ()

    medians = data.get('medians')
    if not isinstance(medians, list) or not medians:
        return ()

    sequence = tuple(_stroke_signature(points) for points in medians if isinstance(points, list))
    expected_count = chinese_stroke_count(ch)
    if expected_count != DEFAULT_STROKE_COUNT and len(sequence) != expected_count:
        return ()
    return sequence


def collect_ambiguous_chinese_chars(texts: Iterable[str], poly: Optional['PolyphoneDict'] = None) -> List[str]:
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

    chars = set()
    for bucket_chars in buckets.values():
        if len(bucket_chars) > 1:
            chars.update(bucket_chars)
    return sorted(chars)


def resolve_stroke_order_for_texts(
    texts: Iterable[str],
    poly: Optional['PolyphoneDict'],
    stroke_order: Optional[StrokeOrderDict],
) -> Optional[StrokeOrderDict]:
    if stroke_order is None:
        return None

    text_list = [text for text in texts if text]
    stroke_order.ensure_for_texts(text_list, poly)
    return stroke_order


def compare_char_sort_tokens(left: CharSortToken, right: CharSortToken) -> int:
    for idx in range(3):
        diff = _compare_values(left[idx], right[idx])
        if diff:
            return diff

    left_order = left[3]
    right_order = right[3]
    if left_order and right_order:
        diff = _compare_values(left_order, right_order)
        if diff:
            return diff

    return _compare_values(left[4], right[4])


def compare_text_sort_keys(
    left: Tuple[CharSortToken, ...],
    right: Tuple[CharSortToken, ...],
) -> int:
    for left_token, right_token in zip(left, right):
        diff = compare_char_sort_tokens(left_token, right_token)
        if diff:
            return diff
    return _compare_values(len(left), len(right))


def compare_texts(
    left: str,
    right: str,
    poly: Optional['PolyphoneDict'] = None,
    stroke_order: Optional[StrokeOrderDict] = None,
) -> int:
    return compare_text_sort_keys(
        text_to_sort_key(left, poly, stroke_order),
        text_to_sort_key(right, poly, stroke_order),
    )


def chinese_stroke_count(ch: str) -> int:
    if not is_chinese_char(ch):
        return DEFAULT_STROKE_COUNT

    return _load_unihan_total_strokes().get(ch, DEFAULT_STROKE_COUNT)


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


def char_sort_token(
    ch: str,
    pinyin_token: Optional[str] = None,
    stroke_order: Optional[StrokeOrderDict] = None,
) -> CharSortToken:
    if is_chinese_char(ch):
        return (
            pinyin_token or ch,
            1,
            chinese_stroke_count(ch),
            stroke_order.lookup_char(ch) if stroke_order else None,
            _stable_fallback_rank(ch),
        )

    normalized = normalize_text(ch)
    return (normalized, 0, -1, None, normalized)


def text_to_sort_key(
    text: str,
    poly: PolyphoneDict = None,
    stroke_order: Optional[StrokeOrderDict] = None,
) -> Tuple[CharSortToken, ...]:
    tokens = text_to_pinyin_tokens(text, poly)
    return tuple(
        char_sort_token(ch, tokens[idx], stroke_order)
        for idx, ch in enumerate(text)
    )


def collect_text_sort_warnings(
    texts: Iterable[str],
    poly: PolyphoneDict = None,
    stroke_order: Optional[StrokeOrderDict] = None,
) -> List[str]:
    poly = poly or PolyphoneDict({})
    text_list = [text for text in texts if text]
    active_stroke_order = resolve_stroke_order_for_texts(text_list, poly, stroke_order)
    buckets = defaultdict(set)

    for text in text_list:
        pinyin_tokens = text_to_pinyin_tokens(text, poly)
        for idx, ch in enumerate(text):
            if not is_chinese_char(ch):
                continue
            buckets[(idx, pinyin_tokens[idx], chinese_stroke_count(ch))].add(ch)

    warnings = []
    for (position, pinyin, strokes), chars in sorted(buckets.items()):
        if len(chars) < 2:
            continue

        if not active_stroke_order:
            reason = "当前未启用笔顺模板，使用稳定伪随机回退"
        else:
            stroke_groups = defaultdict(set)
            for ch in chars:
                stroke_groups[active_stroke_order.lookup_char(ch)].add(ch)

            has_missing = None in stroke_groups
            all_unique = (not has_missing) and len(stroke_groups) == len(chars)
            if all_unique:
                continue

            reason = (
                "模板和自动补全仍未取得部分字的笔顺键，使用稳定伪随机回退"
                if has_missing
                else "当前笔顺键仍无法区分，使用稳定伪随机回退"
            )

        warning = (
            f"第 {position + 1} 个字存在同拼音同笔画候选：{'、'.join(sorted(chars))}"
            f"（{pinyin}，{strokes} 画），{reason}"
        )
        warnings.append(warning)

    return warnings


def normalize_pinyin(s: str) -> str:
    # normalize mixed strings like 'zhong1' or 'zhong' -> keep digits if present
    s = s.strip()
    return s.lower()


def normalize_text(s: str) -> str:
    return s.lower()
