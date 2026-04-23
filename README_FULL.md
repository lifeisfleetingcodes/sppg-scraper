# SPPG Data Scraper

Complete production-ready scraper for BGN (Badan Gizi Nasional) SPPG operational data.

**Version:** 1.2  
**Website:** https://www.bgn.go.id/operasional-sppg

---

## Features

✓ **Dynamic target detection** — reads expected count from website, no hardcoded values  
✓ **Incremental updates** — detects NEW/REMOVED/MODIFIED records across runs  
✓ **Duplicate detection** — strict + fuzzy matching with confidence scores  
✓ **Checkpoint/resume** — survives interruptions, resumes automatically  
✓ **Rate limiting** — anti-blocking with delays, cooling periods, user-agent rotation  
✓ **CAPTCHA detection** — pauses for manual intervention when needed  
✓ **Full logging** — page-level CSV logs + run summary JSON  
✓ **Data validation** — 8 automated checks against PRD requirements  

---

## Requirements

- **Python:** 3.8 or higher
- **Dependencies:** See `requirements.txt`
- **Network:** Access to `bgn.go.id`
- **Disk space:** 200 MB minimum (for multiple runs + master dataset)
- **Runtime:** Can run unattended for 2-4 hours

---

## Installation

### 1. Clone or download this directory

```bash
cd sppg_scraper
```

### 2. Create virtual environment (recommended)

```bash
# Create venv
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

### First Run (Baseline Scrape)

```bash
python scraper.py
```

**What happens:**
- Extracts target count from BGN website (e.g., 26,487 SPPG)
- Calculates expected pages dynamically
- Scrapes all pages with progress bar
- Saves raw data, deduplicated data, duplicates mapping
- Creates master dataset (all records status=ACTIVE)
- Generates run summary JSON

**Expected output:**
```
Extracting target count from website...
✓ Target: 26,487 SPPG
✓ Expected pages: 2,649

Scraping: 100%|██████████| 2649/2649 [2:19:34<00:00, 0.32page/s]
✓ Scraped 26,487 records
✓ Target match: 26,487/26,487 ✓

Detecting duplicates...
✓ Found 342 duplicates
  Strict: 215
  Fuzzy: 127

Computing delta from previous run...
✓ Master dataset created (26,487 ACTIVE records)

SCRAPE COMPLETE
Duration: 139.6 minutes
Records: 26,487
Clean records: 26,145
Success rate: 99.7%
```

**Directory structure after first run:**
```
sppg_data/
├── runs/
│   └── 2026-04-23_14-22-10/
│       ├── sppg_raw.csv
│       ├── sppg_clean.csv
│       ├── sppg_duplicates.csv
│       ├── scrape_log.csv
│       ├── run_summary.json
│       └── validation_report.txt
├── master/
│   ├── sppg_master.csv
│   └── sppg_changelog.csv
└── latest -> runs/2026-04-23_14-22-10
```

---

### Second Run (Incremental Update)

Run the same command weeks/months later:

```bash
python scraper.py
```

**What happens:**
- Extracts current target count (may have changed)
- Compares to previous run's target
- Scrapes all current data
- Computes delta: NEW/REMOVED/MODIFIED/REINSTATED
- Updates master dataset
- Appends changes to changelog

**Expected output:**
```
Extracting target count from website...
✓ Target: 26,510 SPPG
ℹ Target delta: +23 from previous run (+0.09%)

Scraping: 100%|██████████| 2651/2651 [2:21:12<00:00, 0.31page/s]
✓ Scraped 26,510 records

Delta Summary:
  NEW:        35 records
  REMOVED:    12 records
  MODIFIED:   0 records
  UNCHANGED:  26,460 records

✓ Master dataset updated (26,495 ACTIVE, 27 REMOVED)
✓ Changelog: +47 entries
```

---

### Resume After Interruption

If scraper stops (network issue, CTRL+C, power loss):

```bash
python scraper.py
```

Scraper automatically detects checkpoint and resumes from last completed page.

---

### Validate Output

After any run:

```bash
python validate_sppg.py \
  --input sppg_data/runs/2026-04-23_14-22-10/sppg_raw.csv \
  --target-count 26487
```

**Validation checks:**
- ✓ Row count matches target ± 2%
- ✓ Schema: 7 columns in correct order
- ✓ No null values in critical columns
- ✓ No duplicate row numbers
- ✓ Valid UTF-8 encoding
- ✓ Geographic hierarchy consistency
- ✓ Scrape completeness ≥ 50%

**Output:**
```
SPPG DATA VALIDATION REPORT
======================================================================
Generated: 2026-04-23 16:45:30
Input File: sppg_data/runs/2026-04-23_14-22-10/sppg_raw.csv
Target Count (from website): 26,487

CRITICAL CHECKS:
----------------------------------------------------------------------
✓ Scrape Completeness: ✓ Complete
✓ Row Count: Within tolerance
✓ Schema Columns: ✓ Correct
✓ Null Provinsi SPPG: ✓ No nulls
✓ Null Kab./Kota SPPG: ✓ No nulls
✓ Null Nama SPPG: ✓ No nulls

WARNING CHECKS:
----------------------------------------------------------------------
✓ Duplicate No: ✓ No duplicates
✓ Geographic Hierarchy: ✓ Consistent
✓ Encoding: ✓ Valid UTF-8

======================================================================
OVERALL STATUS: PASS
======================================================================
```

---

## File Outputs

### Per-Run Files (in `runs/{timestamp}/`)

**sppg_raw.csv**
- All scraped records exactly as found on website
- Semicolon-delimited, UTF-8
- 7 columns: No, Provinsi, Kab/Kota, Kecamatan, Kelurahan, Alamat, Nama

**sppg_clean.csv**
- Deduplicated dataset (duplicates removed)
- Use this for analysis/reporting

**sppg_duplicates.csv**
- Mapping of all duplicate records
- Columns: duplicate_id, original_row_no, duplicate_row_no, match_type, confidence_score, review_flag
- Match types: STRICT, FUZZY_HIGH, FUZZY_UNCERTAIN

**scrape_log.csv**
- Page-level event log
- Columns: timestamp, page, status, records_scraped, duration_seconds, error_type, error_message
- Use for debugging, performance analysis

**run_summary.json**
- Complete metadata for this run
- Target metrics, scrape metrics, deduplication stats, delta statistics
- Machine-readable format for automation

**failed_pages.txt** (if any failures)
- List of page numbers that failed after retry
- Manual intervention may be needed

**partial_pages.txt** (if any anomalies)
- Pages with unusually low record counts (< 8 records)
- May indicate data issues

---

### Master Files (in `master/`)

**sppg_master.csv**
- Consolidated historical dataset across all runs
- Contains ALL records ever seen (ACTIVE + REMOVED)
- Additional columns: record_hash, first_seen, last_seen, status
- **This is your source of truth**

**sppg_changelog.csv**
- Complete audit trail of all changes
- Columns: timestamp, change_type, record_hash, provinsi, kab_kota, nama_sppg, old_value, new_value, notes
- Change types: NEW, REMOVED, REINSTATED, MODIFIED_ADDRESS

---

## Configuration

Edit `config.json` to customize scraper behavior:

```json
{
  "delay_min": 1.5,           // Min delay between pages (seconds)
  "delay_max": 3.5,           // Max delay between pages (seconds)
  "cooling_interval": 100,    // Pause every N pages
  "cooling_duration": 20,     // Pause duration (seconds)
  "timeout": 10,              // Request timeout (seconds)
  "max_retries": 5,           // Max retries per page
  
  "nama_similarity_threshold": 0.85,     // Fuzzy match threshold for names
  "address_similarity_threshold": 0.70   // Fuzzy match threshold for addresses
}
```

**Rate limiting recommendations:**
- Increase delays if you encounter rate limiting (HTTP 429)
- Decrease delays if scraping too slowly and no blocking issues
- Current settings are conservative (tested safe)

---

## Troubleshooting

### CAPTCHA Detected

**Symptom:**
```
⚠ CAPTCHA DETECTED
Manual intervention required.
Please solve the CAPTCHA in your browser, then press Enter to continue...
```

**Solution:**
1. Open https://www.bgn.go.id/operasional-sppg in your browser
2. Solve the CAPTCHA
3. Return to terminal, press Enter
4. Scraper resumes automatically

---

### Target Extraction Failed

**Symptom:**
```
✗ Could not extract target count from website.
Searched for: 'Hasil Pencarian' and 'Total Seluruh SPPG Operasional'
HTML snippet saved to debug_html_snippet.txt
```

**Cause:** Website HTML structure changed

**Solution:**
1. Check `debug_html_snippet.txt` for actual HTML
2. Update regex patterns in `scraper.py` function `extract_target_count()`
3. Report issue if this is a recurring problem

---

### Validation Failed - Incomplete Scrape

**Symptom:**
```
✗ CRITICAL: Scrape appears incomplete
  Target: 26,487
  Scraped: 12,340
  Percentage: 46.6%
```

**Cause:** Scraper stopped early (network issue, blocking, error)

**Solution:**
1. Check `scrape_log.csv` for error patterns
2. Check `failed_pages.txt` for specific page failures
3. If many TIMEOUT errors → increase `timeout` in config
4. If HTTP_ERROR → check if IP was blocked, wait before retry
5. Resume scraper → it will retry failed pages

---

### High Duplicate Count

**Symptom:**
```
✓ Found 2,847 duplicates
  Strict: 215
  Fuzzy: 2,632
```

**Cause:** Fuzzy matching thresholds too low (false positives)

**Solution:**
1. Check `sppg_duplicates.csv`, filter by `match_type=FUZZY_UNCERTAIN`
2. Review `confidence_score` distribution
3. If many false positives → increase thresholds in `config.json`:
   - `nama_similarity_threshold`: 0.85 → 0.90
   - `address_similarity_threshold`: 0.70 → 0.80
4. Re-run deduplication on existing raw data (modify script to skip scraping)

---

## Performance Notes

**Expected runtime:**
- ~2,650 pages at 2.5s average delay = **~2 hours 20 minutes**
- Add ~10 minutes for retry pass
- Add ~5 minutes for deduplication + delta processing
- **Total: 2.5–3 hours** for typical run

**Network usage:**
- ~2,650 HTTP requests
- ~50–100 MB total data transfer
- Conservative rate limiting prevents blocking

**Disk usage:**
- Raw CSV: ~5 MB per run
- Master dataset: ~10 MB (grows slowly)
- Logs: ~1 MB per run
- **Total per run: ~15–20 MB**

---

## Advanced Usage

### Manual Delta Review

View recent changes:
```bash
# Last 50 changelog entries
tail -50 sppg_data/master/sppg_changelog.csv

# Filter for NEW records only
grep "NEW" sppg_data/master/sppg_changelog.csv

# Filter for REMOVED records
grep "REMOVED" sppg_data/master/sppg_changelog.csv

# Count changes by type
cut -d';' -f2 sppg_data/master/sppg_changelog.csv | sort | uniq -c
```

### View Currently Removed SPPG

```bash
# All SPPG currently marked as REMOVED
awk -F';' '$11=="REMOVED"' sppg_data/master/sppg_master.csv
```

### Export Active SPPG Only

```bash
# Python one-liner
python3 -c "
import pandas as pd
df = pd.read_csv('sppg_data/master/sppg_master.csv', sep=';')
active = df[df['status'] == 'ACTIVE']
active.to_csv('sppg_active_only.csv', sep=';', index=False)
print(f'Exported {len(active):,} active SPPG')
"
```

### Scheduled Runs (Cron)

Monthly scrape on 1st of month at 2 AM:
```bash
# Add to crontab
0 2 1 * * cd /path/to/sppg_scraper && /path/to/venv/bin/python scraper.py >> scraper_cron.log 2>&1
```

---

## Data Dictionary

### Raw/Clean CSV Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| No | Integer | Row number from website | 1234 |
| Provinsi SPPG | String | Province name | DKI Jakarta |
| Kab./Kota SPPG | String | Regency/city name | Jakarta Selatan |
| Kecamatan SPPG | String | District name | Kebayoran Baru |
| Kelurahan/Desa SPPG | String | Village/subdistrict | Senayan |
| Alamat SPPG | String | Street address | Jl. Asia Afrika No. 8 |
| Nama SPPG | String | Kitchen name | Dapur MBG Senayan |

### Master Dataset Additional Columns

| Column | Type | Description |
|--------|------|-------------|
| record_hash | String | SHA256 hash of key fields (stable ID) |
| first_seen | ISO DateTime | When record first appeared |
| last_seen | ISO DateTime | When record last seen |
| status | Enum | ACTIVE / REMOVED / MODIFIED |

---

## Support & Maintenance

### Updating Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Testing After Python Upgrade

```bash
# Run validation on existing data
python validate_sppg.py \
  --input sppg_data/latest/sppg_raw.csv \
  --target-count $(jq '.target_metrics.target_count_from_website' sppg_data/latest/run_summary.json)
```

---

## License & Attribution

Built according to PRD v1.2 specifications.

**Data source:** Badan Gizi Nasional (BGN) - https://www.bgn.go.id  
**Purpose:** SPPG operational data tracking and analysis

---

## Changelog

**v1.2 (2026-04-23)**
- Dynamic target detection from "Hasil Pencarian" field
- Incremental update tracking (NEW/REMOVED/REINSTATED)
- Master dataset with change history
- Comprehensive validation script
- Full checkpoint/resume capability

**v1.1 (Draft)**
- Basic scraping + deduplication
- Static target count

---

## Quick Reference

```bash
# First-time setup
pip install -r requirements.txt

# Run scraper
python scraper.py

# Validate output
python validate_sppg.py --input sppg_data/latest/sppg_raw.csv --target-count {count}

# Check logs
tail -f sppg_data/latest/scrape_log.csv

# View run summary
cat sppg_data/latest/run_summary.json | python -m json.tool

# Count active SPPG
awk -F';' '$11=="ACTIVE"' sppg_data/master/sppg_master.csv | wc -l
```

---

**End of README**
