#!/usr/bin/env python3
"""
SPPG Data Validation Script
Version: 1.2

Validates scraped data against PRD requirements.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


def validate_row_count(df: pd.DataFrame, target_count: int, tolerance: float = 0.02) -> Dict:
    """Validate scraped row count matches target."""
    scraped_count = len(df)
    delta = abs(scraped_count - target_count)
    max_delta = target_count * tolerance
    
    passed = delta <= max_delta
    
    return {
        'check': 'Row Count',
        'rule': f'{target_count:,} ± {tolerance:.0%}',
        'actual': f'{scraped_count:,}',
        'passed': passed,
        'severity': 'CRITICAL',
        'message': f'Delta: {scraped_count - target_count:+,} ({delta/target_count:.2%})' if not passed else 'Within tolerance'
    }


def validate_schema(df: pd.DataFrame) -> Dict:
    """Validate CSV has correct column structure."""
    expected_columns = [
        'No', 'Provinsi SPPG', 'Kab./Kota SPPG', 'Kecamatan SPPG',
        'Kelurahan/Desa SPPG', 'Alamat SPPG', 'Nama SPPG'
    ]
    
    actual_columns = list(df.columns)
    passed = actual_columns == expected_columns
    
    return {
        'check': 'Schema Columns',
        'rule': '7 columns in correct order',
        'actual': f'{len(actual_columns)} columns',
        'passed': passed,
        'severity': 'CRITICAL',
        'message': f'Columns: {actual_columns}' if not passed else '✓ Correct'
    }


def validate_null_values(df: pd.DataFrame) -> List[Dict]:
    """Validate no null values in critical columns."""
    critical_columns = ['Provinsi SPPG', 'Kab./Kota SPPG', 'Nama SPPG']
    
    results = []
    for col in critical_columns:
        null_count = df[col].isna().sum()
        passed = null_count == 0
        
        results.append({
            'check': f'Null {col}',
            'rule': '0 null values',
            'actual': f'{null_count} nulls',
            'passed': passed,
            'severity': 'CRITICAL',
            'message': f'{null_count} rows missing {col}' if not passed else '✓ No nulls'
        })
    
    return results


def validate_duplicate_no(df: pd.DataFrame) -> Dict:
    """Check for duplicate 'No' values (primary key violation)."""
    duplicates = df['No'].duplicated().sum()
    passed = duplicates == 0
    
    return {
        'check': 'Duplicate No',
        'rule': 'No duplicate row numbers',
        'actual': f'{duplicates} duplicates',
        'passed': passed,
        'severity': 'WARNING',
        'message': f'{duplicates} duplicate No values found' if not passed else '✓ No duplicates'
    }


def validate_encoding(file_path: Path) -> Dict:
    """Validate file is UTF-8 encoded."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read()
        passed = True
        message = '✓ Valid UTF-8'
    except UnicodeDecodeError as e:
        passed = False
        message = f'Encoding error: {str(e)[:100]}'
    
    return {
        'check': 'Encoding',
        'rule': 'Valid UTF-8',
        'actual': 'UTF-8' if passed else 'Invalid',
        'passed': passed,
        'severity': 'WARNING',
        'message': message
    }


def validate_completeness(scraped_count: int, target_count: int, threshold: float = 0.50) -> Dict:
    """Validate scrape appears complete (not aborted early)."""
    min_count = target_count * threshold
    passed = scraped_count >= min_count
    
    return {
        'check': 'Scrape Completeness',
        'rule': f'≥ {threshold:.0%} of target',
        'actual': f'{scraped_count/target_count:.1%}',
        'passed': passed,
        'severity': 'CRITICAL',
        'message': f'Only {scraped_count:,}/{target_count:,} scraped' if not passed else '✓ Complete'
    }


def validate_geographic_hierarchy(df: pd.DataFrame) -> Dict:
    """
    Validate geographic hierarchy consistency.
    
    Note: This is a simplified check. Full validation would require
    a reference database of Kecamatan-Kab/Kota mappings.
    """
    # Check for obviously invalid data (empty after non-empty levels)
    issues = []
    
    for idx, row in df.iterrows():
        if pd.notna(row['Kecamatan SPPG']) and pd.isna(row['Kab./Kota SPPG']):
            issues.append(f"Row {idx}: Kecamatan present but Kab/Kota missing")
        
        if pd.notna(row['Kelurahan/Desa SPPG']) and pd.isna(row['Kecamatan SPPG']):
            issues.append(f"Row {idx}: Kelurahan present but Kecamatan missing")
    
    passed = len(issues) == 0
    
    return {
        'check': 'Geographic Hierarchy',
        'rule': 'Consistent hierarchy levels',
        'actual': f'{len(issues)} issues',
        'passed': passed,
        'severity': 'WARNING',
        'message': f'{len(issues)} hierarchy issues found' if not passed else '✓ Consistent'
    }


def print_validation_report(results: List[Dict], output_path: Path, 
                           input_file: Path, target_count: int):
    """Generate and print validation report."""
    
    # Separate by severity
    critical_checks = [r for r in results if r['severity'] == 'CRITICAL']
    warning_checks = [r for r in results if r['severity'] == 'WARNING']
    
    critical_passed = all(r['passed'] for r in critical_checks)
    warnings_exist = not all(r['passed'] for r in warning_checks)
    
    # Determine overall status
    if critical_passed and not warnings_exist:
        overall_status = "PASS"
    elif critical_passed and warnings_exist:
        overall_status = "PASS (with warnings)"
    else:
        overall_status = "FAIL"
    
    # Build report
    report_lines = [
        "="*70,
        "SPPG DATA VALIDATION REPORT",
        "="*70,
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Input File: {input_file}",
        f"Target Count (from website): {target_count:,}",
        "",
        "CRITICAL CHECKS:",
        "-"*70
    ]
    
    for result in critical_checks:
        status = "✓" if result['passed'] else "✗"
        report_lines.append(f"{status} {result['check']}: {result['message']}")
    
    report_lines.extend([
        "",
        "WARNING CHECKS:",
        "-"*70
    ])
    
    for result in warning_checks:
        status = "✓" if result['passed'] else "⚠"
        report_lines.append(f"{status} {result['check']}: {result['message']}")
    
    report_lines.extend([
        "",
        "="*70,
        f"OVERALL STATUS: {overall_status}",
        "="*70
    ])
    
    report_text = "\n".join(report_lines)
    
    # Print to console
    print(report_text)
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\nValidation report saved to: {output_path}")
    
    # Return exit code
    return 0 if critical_passed else 2


def main():
    parser = argparse.ArgumentParser(
        description='Validate SPPG scraped data against PRD requirements'
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to sppg_raw.csv file'
    )
    parser.add_argument(
        '--target-count',
        type=int,
        required=True,
        help='Expected target count from website'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for validation report (default: validation_report.txt in same dir as input)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / "validation_report.txt"
    
    # Load data
    print(f"Loading data from {input_path}...")
    
    try:
        df = pd.read_csv(input_path, sep=';', encoding='utf-8')
    except Exception as e:
        print(f"Error loading CSV: {e}")
        sys.exit(1)
    
    print(f"Loaded {len(df):,} records\n")
    
    # Run all validation checks
    results = []
    
    # Critical checks
    results.append(validate_completeness(len(df), args.target_count))
    results.append(validate_row_count(df, args.target_count))
    results.append(validate_schema(df))
    results.extend(validate_null_values(df))
    
    # Warning checks
    results.append(validate_duplicate_no(df))
    results.append(validate_geographic_hierarchy(df))
    results.append(validate_encoding(input_path))
    
    # Generate report
    exit_code = print_validation_report(results, output_path, input_path, args.target_count)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
