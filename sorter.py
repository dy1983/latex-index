"""
Sorting module: generate sort keys and sort parsed index entries.
"""
from functools import cmp_to_key
from typing import Dict, List, Tuple, Union
from readings import (
    collect_text_sort_warnings,
    compare_text_sort_keys,
    PolyphoneDict,
    resolve_stroke_order_for_texts,
    StrokeOrderDict,
    text_to_sort_key,
)


def make_sort_key(level: Dict, poly: PolyphoneDict, stroke_order: StrokeOrderDict = None) -> Tuple:
    # Use key first; fallback to text
    key = level.get('key') or level.get('text')
    return text_to_sort_key(key, poly, stroke_order)


def compare_entry_sort_keys(left: Tuple[Tuple, ...], right: Tuple[Tuple, ...]) -> int:
    for left_level, right_level in zip(left, right):
        diff = compare_text_sort_keys(left_level, right_level)
        if diff:
            return diff
    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def collect_entry_sort_warnings(
    entries: List[Dict],
    poly: PolyphoneDict,
    stroke_order: StrokeOrderDict = None,
) -> List[str]:
    texts = []
    for entry in entries:
        for level in entry.get('levels', []):
            text = level.get('key') or level.get('text')
            if text:
                texts.append(text)
    return collect_text_sort_warnings(texts, poly, stroke_order)


def sort_entries(
    entries: List[Dict],
    poly: PolyphoneDict,
    stroke_order: StrokeOrderDict = None,
    return_warnings: bool = False,
) -> Union[List[Dict], Tuple[List[Dict], List[str]]]:
    texts = [
        level.get('key') or level.get('text')
        for entry in entries
        for level in entry.get('levels', [])
        if level.get('key') or level.get('text')
    ]
    active_stroke_order = resolve_stroke_order_for_texts(texts, poly, stroke_order)

    entry_keys = {
        id(entry): tuple(make_sort_key(level, poly, active_stroke_order) for level in entry['levels'])
        for entry in entries
    }

    def compare_entries(left: Dict, right: Dict) -> int:
        return compare_entry_sort_keys(entry_keys[id(left)], entry_keys[id(right)])

    sorted_entries = sorted(entries, key=cmp_to_key(compare_entries))
    if return_warnings:
        return sorted_entries, collect_entry_sort_warnings(entries, poly, stroke_order)
    return sorted_entries
