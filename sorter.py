"""
Sorting module: generate sort keys and sort parsed index entries.
"""
from typing import Dict, List, Tuple, Union
from readings import collect_text_sort_warnings, PolyphoneDict, text_to_sort_key


def make_sort_key(level: Dict, poly: PolyphoneDict) -> Tuple:
    # Use key first; fallback to text
    key = level.get('key') or level.get('text')
    return text_to_sort_key(key, poly)


def collect_entry_sort_warnings(entries: List[Dict], poly: PolyphoneDict) -> List[str]:
    texts = []
    for entry in entries:
        for level in entry.get('levels', []):
            text = level.get('key') or level.get('text')
            if text:
                texts.append(text)
    return collect_text_sort_warnings(texts, poly)


def sort_entries(
    entries: List[Dict],
    poly: PolyphoneDict,
    return_warnings: bool = False,
) -> Union[List[Dict], Tuple[List[Dict], List[str]]]:
    # compute composite keys
    def entry_key(e):
        return tuple(make_sort_key(level, poly) for level in e['levels'])

    sorted_entries = sorted(entries, key=entry_key)
    if return_warnings:
        return sorted_entries, collect_entry_sort_warnings(entries, poly)
    return sorted_entries
