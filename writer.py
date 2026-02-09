"""
Write .ind files from sorted entries.

This is a simple writer that groups by initial letter (pinyin initial) and
produces nested \item / \subitem lines.
"""
from typing import List, Dict, Optional
from readings import text_to_pinyin, PolyphoneDict
import re
from collections import OrderedDict

INITIAL_RE = re.compile(r"^([a-z]+)")


def cleanup_tex_escapes(text: str) -> str:
    """Convert TeX escape sequences from makeindex format to final format.
    
    E.g., \"! → \! (de-escape special sequences)
    """
    # In makeindex, \"! is used for \! (negative space)
    # We need to convert it back
    text = text.replace(r'\"!', r'\!')
    return text


def first_initial_of_pinyin(pinyin_key: str) -> str:
    # extract first ASCII initial
    if not pinyin_key:
        return '#'
    m = INITIAL_RE.match(pinyin_key)
    if m:
        return m.group(1)[0].upper()
    return '#'


def merge_pages(pages: List[dict]) -> str:
    """Merge pages considering |(  |) range markers.

    pages: list of dicts {'num': str, 'rangetype': 'normal'|'open'|'close', 'encap': str}
    
    Rules (matching Go zhmakeindex behavior):
    1. Pages marked with |( and |) form explicit ranges (output as start--end)
    2. Normal unmarked pages are output individually
    3. Range and adjacent normal page can merge (if adjacent number)
    4. \see and \seealso macros are placed at the end
    5. Duplicate pages are removed (same number + encap)
    """
    # Process pages: collect ranges from |( |) markers and individual pages
    parts = []  # Final output parts as [(start, end, is_marked), ...]
    encap_macros = []  # \see and \seealso for end placement
    seen_pages = set()  # To track (num, encap) combinations to avoid duplicates
    processed_close_nums = set()  # Track page numbers that were part of a range
    
    i = 0
    pages_list = pages or []
    
    # First pass: identify which page numbers appear in ranges
    for j, p in enumerate(pages_list):
        if p.get('rangetype') == 'open':
            # Find matching close
            for k in range(j + 1, len(pages_list)):
                if pages_list[k].get('rangetype') == 'close':
                    # Mark all pages in this range
                    for m in range(j, k + 1):
                        try:
                            num = int(pages_list[m]['num'])
                            processed_close_nums.add(num)
                        except:
                            pass
                    break
    
    while i < len(pages_list):
        p = pages_list[i]
        num = p.get('num', '').strip()
        rtype = p.get('rangetype', 'normal')
        encap = (p.get('encap') or '').strip()
        
        if rtype == 'open':
            # Find matching close marker
            close_idx = None
            for j in range(i + 1, len(pages_list)):
                if pages_list[j].get('rangetype') == 'close':
                    close_idx = j
                    break
            
            if close_idx is not None:
                # Collect all pages between |( and |)
                range_pages = []
                for j in range(i, close_idx + 1):
                    try:
                        range_pages.append(int(pages_list[j]['num']))
                    except:
                        pass  # Non-numeric, skip
                
                # Output as range from min to max, marked as from range marker
                if range_pages:
                    range_pages = sorted(set(range_pages))
                    page_start = range_pages[0]
                    page_end = range_pages[-1]
                    page_key = (page_start, encap)
                    if page_key not in seen_pages:
                        seen_pages.add(page_key)
                        # is_marked=True means this came from |( |) markers
                        parts.append((page_start, page_end, True))
                i = close_idx + 1
            else:
                # No matching close, treat as a single normal page
                try:
                    page_num = int(num)
                    page_key = (page_num, encap)
                    if page_key not in seen_pages:
                        seen_pages.add(page_key)
                        # is_marked=False
                        parts.append((page_num, page_num, False))
                except:
                    parts.append((num, num, False))
                i += 1
        elif rtype == 'close':
            # Already handled as part of open/close pair, skip
            i += 1
        else:
            # 'normal' page - list individually without merging
            if encap:
                # Macro like \see or \seealso - save for end
                page_key = (num, encap)
                if page_key not in seen_pages:
                    seen_pages.add(page_key)
                    encap_macros.append(f"\\{encap}{{{num}}}")
            else:
                # Regular page number - skip if it was part of a range
                try:
                    page_num = int(num)
                    # Skip if this page was part of a processed range
                    if page_num not in processed_close_nums:
                        page_key = (page_num, encap)
                        if page_key not in seen_pages:
                            seen_pages.add(page_key)
                            # is_marked=False for normal pages
                            parts.append((page_num, page_num, False))
                except:
                    page_key = (num, encap)
                    if page_key not in seen_pages:
                        seen_pages.add(page_key)
                        parts.append((num, num, False))
            i += 1
    
    # Second pass: merge adjacent ranges/pages
    # Merge if there's no gap (current.start <= last.end + 1)
    merged_parts = []
    for part in parts:
        if isinstance(part, tuple) and len(part) == 3:
            start, end, is_marked = part
            
            # Check if we can merge with the previous part
            if merged_parts and isinstance(merged_parts[-1], tuple) and len(merged_parts[-1]) == 3:
                last_start, last_end, last_marked = merged_parts[-1]
                
                # Merge if there's no gap between ranges
                if start <= last_end + 1:
                    # Merge: extend the previous range
                    merged_parts[-1] = (last_start, max(last_end, end), last_marked or is_marked)
                    continue
            
            merged_parts.append(part)
        else:
            merged_parts.append(part)
    
    # Convert to string output
    # Rules:
    # - If from range markers (is_marked=True): always output as range (--), even if 2 pages
    # - If from normal pages: only output as range if 3+ consecutive
    output_parts = []
    for part in merged_parts:
        if isinstance(part, tuple) and len(part) == 3:
            start, end, is_marked = part
            if start == end:
                # Single page
                output_parts.append(str(start))
            elif is_marked:
                # From range markers - always use range notation
                output_parts.append(f"{start}--{end}")
            elif end - start >= 2:
                # 3+ consecutive normal pages - use range notation
                output_parts.append(f"{start}--{end}")
            elif end - start == 1:
                # 2 consecutive normal pages - list separately
                output_parts.append(str(start))
                output_parts.append(str(end))
        elif isinstance(part, tuple) and len(part) == 2:
            start, end = part
            if start == end:
                output_parts.append(str(start))
            elif end - start >= 2:
                output_parts.append(f"{start}--{end}")
            else:
                # 2 pages
                output_parts.append(str(start))
                output_parts.append(str(end))
        else:
            output_parts.append(str(part))
    
    # Add encap macros at end
    output_parts.extend(encap_macros)
    
    return ', '.join(str(p) for p in output_parts)


def write_ind(path: str, entries: List[Dict], poly: Optional[PolyphoneDict] = None):
    poly = poly or PolyphoneDict({})
    # group entries by initial (use first/top-level for grouping)
    groups = OrderedDict()
    for e in entries:
        top = e['levels'][0]
        pinyin = text_to_pinyin(top.get('key') or top.get('text'), poly)
        initial = first_initial_of_pinyin(pinyin)
        groups.setdefault(initial, []).append(e)

    # write file with header and grouped structure similar to example.ind
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\\begin{theindex}\n")
        f.write("  \\def\\seename{见：}\n")
        f.write("  \\def\\alsoname{另见：}\n")
        f.write("  \\providecommand*\\indexgroup[1]{%\n")
        f.write("    \\indexspace\n")
        f.write("    \\item \\textbf{#1}\\nopagebreak}\n")
        f.write("  %\n")

        initials = sorted(groups.keys())
        for idx_i, initial in enumerate(initials):
            if idx_i != 0:
                f.write("  \\indexspace\n\n  %\n")
            f.write(f"  \\indexgroup{{{initial}}}\n")
            f.write("  %\n\n")
            # build parent -> subs mapping preserving order
            parents = OrderedDict()
            for e in groups[initial]:
                parent = e['levels'][0]
                parent_key = parent.get('text') or parent.get('key')
                if parent_key not in parents:
                    parents[parent_key] = {'parent_pages': None, 'subs': []}
                if len(e['levels']) == 1:
                    # this entry is the parent itself
                    parents[parent_key]['parent_pages'] = e['pages']
                else:
                    # subentry: use last level as display
                    sub = e['levels'][-1]
                    sub_display = sub.get('text') or sub.get('key')
                    parents[parent_key]['subs'].append((sub_display, e['pages']))

            # write parents and their subs
            for pkey, pdata in parents.items():
                clean_pkey = cleanup_tex_escapes(pkey)
                if pdata['parent_pages']:
                    page_str = merge_pages(pdata['parent_pages'])
                    f.write(f"  \\item {clean_pkey}, {page_str}\n")
                else:
                    f.write(f"  \\item {clean_pkey}\n")
                for (sdisp, spages) in pdata['subs']:
                    clean_sdisp = cleanup_tex_escapes(sdisp)
                    page_str = merge_pages(spages)
                    f.write(f"    \\subitem {clean_sdisp}, {page_str}\n")
            f.write("\n")

        f.write("\\end{theindex}\n")
