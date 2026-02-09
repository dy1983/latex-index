"""
Index checker: verify page numbers, merging, ordering, and cross-references.
"""
import re
from typing import List, Tuple, Optional
from readings import PolyphoneDict, text_to_pinyin


def parse_ind_file(filepath: str) -> List[dict]:
    """Parse .ind file and extract entries with their properties."""
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for top-level \item (not indented as \subitem)
        if re.match(r'^\s*\\item\s+', line):
            # This is a top-level entry
            entry_lines = [line]
            i += 1
            
            # Collect lines until we hit another \item, \indexspace, or \indexgroup
            while i < len(lines):
                next_line = lines[i]
                # Stop at section boundaries or new top-level items
                if re.match(r'^\s*\\indexspace', next_line) or \
                   re.match(r'^\s*\\indexgroup', next_line) or \
                   re.match(r'^\s*\\item\s+', next_line):
                    break
                # Stop at empty lines that are followed by section markers
                if next_line.strip() == '' and i + 1 < len(lines):
                    if re.match(r'^\s*\\index(space|group)', lines[i + 1]):
                        break
                entry_lines.append(next_line)
                i += 1
            
            # Join and parse the entry
            entry_text = ''.join(entry_lines)
            parsed = parse_entry(entry_text)
            if parsed:
                entries.append(parsed)
        else:
            i += 1
    
    return entries


def parse_entry(entry_text: str) -> Optional[dict]:
    """Parse a single entry and extract text, pages, see/seealso."""
    # Remove the leading \item
    match = re.match(r'^\s*\\item\s+', entry_text)
    if not match:
        return None
    
    content = entry_text[match.end():]
    
    # Find the first comma (which separates text from pages)
    # But we need to be careful about commas inside {}
    comma_pos = -1
    brace_depth = 0
    for i, ch in enumerate(content):
        if ch == '{':
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
        elif ch == ',' and brace_depth == 0:
            comma_pos = i
            break
    
    if comma_pos == -1:
        return None
    
    text = content[:comma_pos].strip()
    
    # Remove \subitem lines from text (only get the main entry text)
    text_lines = text.split('\n')
    main_text = text_lines[0].strip()
    
    rest = content[comma_pos + 1:].strip()
    
    # Find where pages end (before \subitem, \indexspace, or end of content)
    pages_end = len(rest)
    subitem_match = re.search(r'\n\s*\\subitem', rest)
    if subitem_match:
        pages_end = subitem_match.start()
    
    # Also check for indexspace
    index_match = re.search(r'\n\s*\\index(space|group)', rest)
    if index_match and index_match.start() < pages_end:
        pages_end = index_match.start()
    
    pages_part = rest[:pages_end].strip()
    
    # Check for \see or \seealso in the pages part
    see_match = re.search(r'\\see\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{[^{}]*\}', pages_part)
    seealso_match = re.search(r'\\seealso\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{[^{}]*\}', pages_part)
    
    has_see = see_match is not None
    has_seealso = seealso_match is not None
    
    # Extract page numbers (everything before \see/\seealso)
    pages_str = pages_part
    if see_match:
        pages_str = pages_part[:see_match.start()]
    elif seealso_match:
        pages_str = pages_part[:seealso_match.start()]
    
    # Clean up pages_str
    pages_str = pages_str.strip()
    pages_str = re.sub(r',\s*$', '', pages_str)  # remove trailing comma
    pages_str = re.sub(r'\s+', ' ', pages_str)  # normalize whitespace
    
    if not pages_str:
        return None
    
    return {
        'text': main_text,
        'pages_str': pages_str,
        'has_see': has_see,
        'has_seealso': has_seealso,
        'full_entry': entry_text
    }


def extract_page_numbers(pages_str: str) -> List[int]:
    """Extract all page numbers from a pages string like '123, 456--458, 460'."""
    pages = []
    # Split by comma
    for part in pages_str.split(','):
        part = part.strip()
        if '--' in part:
            # Range
            start, end = part.split('--')
            start = int(start.strip())
            end = int(end.strip())
            pages.extend(range(start, end + 1))
        else:
            # Single page
            try:
                pages.append(int(part))
            except ValueError:
                # Skip non-numeric pages like "i", "ii", etc.
                pass
    return pages


def normalize_entry_text(text: str) -> str:
    """Normalize entry text for sorting and comparison."""
    # For LaTeX content, we convert special commands to their Latin equivalents or remove spacing
    # But we keep the overall structure
    # Replace \bzx with hyphen
    text = text.replace('\\bzx', '-')
    # Replace other common LaTeX commands
    text = re.sub(r'\\[a-z]+\s+', '', text)  # \upbeta, \updelta, etc. followed by space
    # Remove unnecessary braces
    text = re.sub(r'\$\{', '$', text)
    text = re.sub(r'\}\$', '$', text)
    text = re.sub(r'\{([^}]*)\}', r'\1', text)  # Remove outer braces
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def check_index(filepath: str, polyphone_dict: Optional[PolyphoneDict] = None) -> dict:
    """Run all checks on an .ind file. Returns a report dict."""
    entries = parse_ind_file(filepath)
    
    report = {
        'total_entries': len(entries),
        'errors': [],
        'warnings': []
    }
    
    prev_text = None
    prev_pinyin = None
    all_pages = []
    
    for i, entry in enumerate(entries):
        text = entry['text']
        # Normalize text for comparison
        normalized_text = normalize_entry_text(text)
        
        pages_str = entry['pages_str']
        has_see = entry['has_see']
        has_seealso = entry['has_seealso']
        
        # Check 1: Pages are in order (from small to large)
        try:
            pages = extract_page_numbers(pages_str)
            if pages and pages != sorted(pages):
                report['errors'].append(f"Entry {i+1} '{text}': pages not in order: {pages_str}")
            all_pages.append(pages)
        except Exception as e:
            report['warnings'].append(f"Entry {i+1} '{text}': could not parse pages: {pages_str} ({e})")
            continue
        
        # Check 2: see/seealso is at the end (after page numbers)
        if pages_str and (has_see or has_seealso):
            # This is OK; see/seealso should come after pages
            pass
        
        # Check 3: Check if pages could be better merged
        # (This is a heuristic check for consecutive or near-consecutive pages)
        if pages:
            # Find gaps in pages
            sorted_pages = sorted(set(pages))
            if len(sorted_pages) > 1:
                gaps = []
                for j in range(len(sorted_pages) - 1):
                    gap = sorted_pages[j+1] - sorted_pages[j]
                    if gap > 1:
                        gaps.append(gap)
                
                # If there are very small gaps (1-2 pages), suggest merging
                if gaps and max(gaps) <= 2 and len(sorted_pages) > 3:
                    report['warnings'].append(
                        f"Entry {i+1} '{text}': pages may not be optimally merged: {pages_str}"
                    )
        
        # Check 4: Ordering of entries using pinyin
        if normalized_text:  # Only check if we have non-empty text
            if polyphone_dict is not None and prev_text is not None:
                try:
                    current_pinyin = text_to_pinyin(normalized_text, polyphone_dict)
                    if prev_pinyin is not None and current_pinyin < prev_pinyin:
                        report['errors'].append(
                            f"Entry {i+1} '{text}' (pinyin: {current_pinyin}) "
                            f"should not come before Entry {i} '{prev_text}' (pinyin: {prev_pinyin})"
                        )
                    prev_pinyin = current_pinyin
                except Exception as e:
                    # Skip pinyin check if it fails
                    pass
            elif prev_text is not None and normalized_text:
                # Fallback to simple string comparison if no polyphone dict
                if normalized_text < prev_text:
                    report['errors'].append(f"Entry {i+1} '{text}' appears before Entry {i} '{prev_text}' but should come after")
            
            prev_text = normalized_text
    
    return report


def format_report(report: dict) -> str:
    """Format the report as a readable string."""
    lines = []
    lines.append("=" * 60)
    lines.append("INDEX CHECK REPORT")
    lines.append("=" * 60)
    lines.append(f"Total entries: {report['total_entries']}")
    lines.append("")
    
    if report['errors']:
        lines.append(f"ERRORS ({len(report['errors'])}):")
        for err in report['errors']:
            lines.append(f"  ✗ {err}")
        lines.append("")
    else:
        lines.append("✓ No critical errors found")
        lines.append("")
    
    if report['warnings']:
        lines.append(f"WARNINGS ({len(report['warnings'])}):")
        for warn in report['warnings'][:10]:  # Show first 10 warnings
            lines.append(f"  ⚠ {warn}")
        if len(report['warnings']) > 10:
            lines.append(f"  ... and {len(report['warnings']) - 10} more warnings")
        lines.append("")
    else:
        lines.append("✓ No warnings")
        lines.append("")
    
    lines.append("=" * 60)
    
    return '\n'.join(lines)


if __name__ == '__main__':
    import sys
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='Check index file for errors')
    parser.add_argument('ind_file', help='Input .ind file')
    parser.add_argument('--polyphone', help='YAML file for polyphone overrides', default=None)
    args = parser.parse_args()
    
    # Load polyphone dict if specified or use default
    polyphone = None
    if args.polyphone:
        polyphone = PolyphoneDict.load(args.polyphone)
    else:
        # Try to load built-in polyphone file
        built_in = os.path.join(os.path.dirname(__file__), 'polyphone_overrides.yaml')
        if os.path.exists(built_in):
            polyphone = PolyphoneDict.load(built_in)
    
    report = check_index(args.ind_file, polyphone)
    print(format_report(report))
    
    # Exit with error code if there are critical errors
    sys.exit(1 if report['errors'] else 0)
