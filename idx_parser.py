"""
IDX parser for LaTeX .idx files.

Parses lines like: \indexentry{一级!二级@显示内容}{12}
"""
import re
from typing import List, Dict, Tuple

def parse_idx(path: str) -> List[Dict]:
    """Parse an .idx file and return list of entries.

    Each entry is a dict: {'raw': raw_entry, 'levels': [level1, level2...], 'pages': [pageStr,...], 'encap': None}
    Manually parse to handle nested braces correctly (instead of using regex).
    """
    # Aggregate entries by full key (levels tuple) so duplicates merge pagelists
    aggregated = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith('\\indexentry{'):
                continue
            # Manually parse to handle nested braces correctly
            # Format: \indexentry{key}{page}
            # Find the matching closing brace for key
            i = 12  # len('\\indexentry{')
            brace_depth = 1
            while i < len(line) and brace_depth > 0:
                if line[i] == '{':
                    brace_depth += 1
                elif line[i] == '}':
                    brace_depth -= 1
                i += 1
            if brace_depth != 0:
                continue  # malformed entry
            key = line[12:i-1]  # exclude the braces
            # Now parse page (should be {page} after key})
            if i >= len(line) or line[i] != '{':
                continue
            page_start = i + 1
            page_end = line.rfind('}')
            if page_end <= page_start:
                continue
            page = line[page_start:page_end]
            # split levels and detect encap/range markers
            levels, page_rangetype, page_encap = split_levels(key)
            # pages may be comma-separated; usually one
            page_tokens = [p.strip() for p in page.split(',') if p.strip()]
            # create page dicts with rangetype from key (if present)
            pagelist = []
            for p in page_tokens:
                pagelist.append({'num': p, 'rangetype': page_rangetype, 'encap': page_encap})

            # key signature for aggregation
            sig = tuple([lv['key'] for lv in levels])
            if sig not in aggregated:
                aggregated[sig] = {'raw': key, 'levels': levels, 'pages': []}
            aggregated[sig]['pages'].extend(pagelist)
    # convert aggregated to list
    return list(aggregated.values())


def split_levels(key: str) -> (List[Dict], str, str):
    """Split key by levels using '!' as separator and handle '@' (display) and encap.

    Return list of level dicts: {'key': keystring, 'text': displaytext}
    Properly handles escaped '!' (e.g., in \"! sequences) by not treating them as separators.
    """
    parts = []
    # Smart split on '!' that respects TeX escaping
    items = []
    current = []
    i = 0
    while i < len(key):
        # Check if we hit a plain '!' (not preceded by backslash or in an escape sequence)
        if key[i] == '!':
            # Look back to see if this is part of an escape sequence
            # If preceded by \" or similar, it's part of content, not a separator
            if i > 0 and key[i-1] == '"' and i > 1 and key[i-2] == '\\':
                # This is \"!, keep as content
                current.append(key[i])
                i += 1
            else:
                # This is a separator
                items.append(''.join(current))
                current = []
                i += 1
        else:
            current.append(key[i])
            i += 1
    if current:
        items.append(''.join(current))
    
    # default page markers (no encap)
    page_rangetype = 'normal'
    page_encap = ''
    for it in items:
        # detect encap '|' in this level
        if '|' in it:
            left, right = it.split('|', 1)
            # if right startswith '(' or ')' we consider it a range marker
            if right.startswith('('):
                page_rangetype = 'open'
                page_encap = right
            elif right.startswith(')'):
                page_rangetype = 'close'
                page_encap = right
            else:
                # other encap commands (see, etc.) treat as normal encap text
                page_encap = right
            it = left
        if '@' in it:
            k, text = it.split('@', 1)
        else:
            k, text = it, it
        # use a cleaned key for sorting but preserve original display text (keep LaTeX commands)
        sort_key = strip_tex(k)
        display_text = text
        # remove one layer of surrounding braces for nicer display, but keep LaTeX commands
        if display_text.startswith('{') and display_text.endswith('}'):
            display_text = display_text[1:-1]
        parts.append({'key': sort_key, 'text': display_text})
    return parts, page_rangetype, page_encap


TEX_CMD_RE = re.compile(r"\\[a-zA-Z@]+(?:\s*\{.*?\})*")
BRACE_RE = re.compile(r"\{(.*?)\}")


def strip_tex(s: str) -> str:
    """Remove TeX commands for sorting, but carefully preserve content inside braces.
    
    Handles nested braces, preserves special chars like \!, and keeps formula content.
    """
    result = []
    i = 0
    while i < len(s):
        # Handle backslash commands
        if s[i] == '\\':
            if i + 1 < len(s):
                # Skip single-char commands like \!, \~, \', etc.
                if not s[i+1].isalpha():
                    # These are special TeX chars; skip the backslash but keep the char
                    result.append(s[i+1])
                    i += 2
                    continue
                # Multi-char commands like \textbf, \text
                j = i + 1
                while j < len(s) and s[j].isalpha():
                    j += 1
                cmd = s[i:j]
                # Skip the command name
                i = j
                # If followed by {, extract the braced content
                if i < len(s) and s[i] == '{':
                    # Find matching close brace
                    brace_count = 1
                    i += 1
                    content_start = i
                    while i < len(s) and brace_count > 0:
                        if s[i] == '{':
                            brace_count += 1
                        elif s[i] == '}':
                            brace_count -= 1
                        i += 1
                    # Extract content (excluding final close brace)
                    content = s[content_start:i-1] if brace_count == 0 else s[content_start:]
                    # Recursively strip TeX from content
                    result.append(strip_tex(content))
                continue
            i += 1
        # Handle regular braces (strip them but keep content)
        elif s[i] == '{':
            j = i + 1
            brace_count = 1
            while j < len(s) and brace_count > 0:
                if s[j] == '{':
                    brace_count += 1
                elif s[j] == '}':
                    brace_count -= 1
                j += 1
            # Extract content
            content = s[i+1:j-1] if brace_count == 0 else s[i+1:]
            result.append(strip_tex(content))
            i = j
        elif s[i] == '}':
            # Unmatched close brace, skip
            i += 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result).strip()
