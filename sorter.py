"""
Sorting module: generate sort keys and sort parsed index entries.
"""
from typing import List, Dict
from readings import text_to_pinyin, PolyphoneDict


def make_sort_key(level: Dict, poly: PolyphoneDict) -> str:
    # Use key first; fallback to text
    key = level.get('key') or level.get('text')
    return text_to_pinyin(key, poly)


def sort_entries(entries: List[Dict], poly: PolyphoneDict) -> List[Dict]:
    # compute composite keys
    def entry_key(e):
        # produce tuple of level keys; shorter lists are padded
        keys = []
        for lv in e['levels']:
            keys.append(make_sort_key(lv, poly))
            # also append raw text as tiebreaker
            keys.append((lv.get('text') or '').lower())
        return tuple(keys)

    return sorted(entries, key=entry_key)
