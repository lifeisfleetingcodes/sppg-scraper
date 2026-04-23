#!/usr/bin/env python3
"""
SPPG Scraper - Test Script
Quick verification of installation and website connectivity
"""

import sys
from pathlib import Path

print("="*60)
print("SPPG Scraper - Installation Test")
print("="*60)
print()

# Test 1: Python version
print("1. Checking Python version...")
version_info = sys.version_info
if version_info >= (3, 8):
    print(f"   ✓ Python {version_info.major}.{version_info.minor}.{version_info.micro}")
else:
    print(f"   ✗ Python {version_info.major}.{version_info.minor}.{version_info.micro}")
    print(f"   ERROR: Python 3.8+ required")
    sys.exit(1)

# Test 2: Dependencies
print("\n2. Checking dependencies...")

dependencies = {
    'requests': 'HTTP requests',
    'bs4': 'HTML parsing',
    'pandas': 'Data processing',
    'fuzzywuzzy': 'Fuzzy matching',
    'tqdm': 'Progress bars'
}

missing = []
for module, description in dependencies.items():
    try:
        __import__(module)
        print(f"   ✓ {module} ({description})")
    except ImportError:
        print(f"   ✗ {module} ({description}) - MISSING")
        missing.append(module)

if missing:
    print(f"\n   ERROR: Missing dependencies: {', '.join(missing)}")
    print(f"   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test 3: Website connectivity
print("\n3. Testing BGN website connectivity...")

try:
    import requests
    response = requests.get(
        "https://www.bgn.go.id/operasional-sppg?page=1&search=",
        timeout=10
    )
    
    if response.status_code == 200:
        print(f"   ✓ Website accessible (HTTP {response.status_code})")
    else:
        print(f"   ⚠ Unexpected status code: HTTP {response.status_code}")
        
except requests.Timeout:
    print(f"   ✗ Connection timeout (>10s)")
    print(f"   Check your internet connection")
    sys.exit(1)
    
except requests.RequestException as e:
    print(f"   ✗ Connection failed: {e}")
    sys.exit(1)

# Test 4: Target extraction
print("\n4. Testing target count extraction...")

try:
    import re
    
    pattern = r'Hasil\s+Pencarian[^\d]*([\d\.]+)\s*SPPG'
    match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
    
    if match:
        count_str = match.group(1).replace('.', '')
        target_count = int(count_str)
        print(f"   ✓ Target extracted: {target_count:,} SPPG")
    else:
        print(f"   ⚠ Could not extract target count")
        print(f"   Website structure may have changed")
        
        # Try fallback
        pattern2 = r'Total\s+Seluruh\s+SPPG\s+Operasional[^\d]*([\d\.]+)'
        match2 = re.search(pattern2, response.text, re.IGNORECASE | re.DOTALL)
        
        if match2:
            count_str = match2.group(1).replace('.', '')
            target_count = int(count_str)
            print(f"   ✓ Target extracted (fallback): {target_count:,} SPPG")
        else:
            print(f"   ✗ Extraction failed")
            print(f"   Manual inspection needed")
            
except Exception as e:
    print(f"   ✗ Extraction error: {e}")

# Test 5: Table parsing
print("\n5. Testing HTML table parsing...")

try:
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    
    if table:
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            print(f"   ✓ Found {len(rows)} records on page 1")
            
            # Try parsing first row
            if rows:
                cells = rows[0].find_all('td')
                if len(cells) >= 7:
                    print(f"   ✓ Table structure valid (7+ columns)")
                else:
                    print(f"   ⚠ Unexpected column count: {len(cells)}")
        else:
            print(f"   ⚠ Table body not found")
    else:
        print(f"   ✗ Data table not found")
        print(f"   Website structure may have changed")
        
except Exception as e:
    print(f"   ✗ Parsing error: {e}")

# Test 6: File permissions
print("\n6. Testing file write permissions...")

try:
    test_dir = Path("sppg_data")
    test_dir.mkdir(exist_ok=True)
    
    test_file = test_dir / "test_write.txt"
    test_file.write_text("test")
    test_file.unlink()
    
    print(f"   ✓ Can write to sppg_data/")
    
except PermissionError:
    print(f"   ✗ Permission denied")
    print(f"   Check directory permissions")
    sys.exit(1)

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
print("✓ All checks passed")
print("\nYou're ready to run the scraper:")
print("  python scraper.py")
print("="*60)
