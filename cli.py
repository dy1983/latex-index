"""
Command-line interface for zhmakeindex_py
"""
import argparse
import os
from idx_parser import parse_idx
from readings import PolyphoneDict
from sorter import sort_entries
from writer import write_ind
from check_index import check_index, format_report


def main():
    parser = argparse.ArgumentParser(description='Simple zhmakeindex (Python)')
    parser.add_argument('idx', help='Input .idx file')
    parser.add_argument('-o', '--output', help='Output .ind file', default=None)
    parser.add_argument('--polyphone', help='YAML file for polyphone overrides', default=None)
    parser.add_argument('--no-check', action='store_true', help='Skip index verification')
    args = parser.parse_args()

    entries = parse_idx(args.idx)
    # Load polyphone dictionary (try built-in first, then custom if specified)
    built_in_path = os.path.join(os.path.dirname(__file__), 'poly.yaml')
    polyphone_file = args.polyphone or built_in_path
    poly = PolyphoneDict.load(polyphone_file)
    sorted_entries, sort_warnings = sort_entries(entries, poly, return_warnings=True)
    out = args.output or args.idx.rsplit('.',1)[0] + '.ind'
    write_ind(out, sorted_entries, poly)
    print(f"Wrote {out} with {len(sorted_entries)} entries")
    
    # Run index verification unless --no-check is specified
    if not args.no_check:
        print()
        report = check_index(out, poly)
        for warning in sort_warnings:
            if warning not in report['warnings']:
                report['warnings'].append(warning)
        print(format_report(report))
    elif sort_warnings:
        print()
        print(f"SORT WARNINGS ({len(sort_warnings)}):")
        for warning in sort_warnings[:10]:
            print(f"  ⚠ {warning}")
        if len(sort_warnings) > 10:
            print(f"  ... and {len(sort_warnings) - 10} more warnings")


if __name__ == '__main__':
    main()
