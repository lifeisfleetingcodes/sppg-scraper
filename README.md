# SPPG Data Scraper

Production-ready web scraper for [Badan Gizi Nasional (BGN)](https://www.bgn.go.id/operasional-sppg) SPPG operational data.

**Key Features:** Dynamic target detection • Incremental updates • Duplicate detection • Auto-resume • Change tracking

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/sppg-scraper.git
cd sppg-scraper

# Install dependencies
pip install -r requirements.txt

# Test installation (optional)
python test_installation.py

# Run scraper
python scraper.py
```

**Runtime:** ~2.5 hours for full scrape

---

## What It Does

Scrapes all SPPG (MBG kitchen) records from the BGN website and:

✅ **Adapts automatically** — Reads target count from website, no hardcoded values  
✅ **Tracks changes** — Detects NEW/REMOVED/REINSTATED records across runs  
✅ **Finds duplicates** — Strict + fuzzy matching with confidence scores  
✅ **Never loses data** — Checkpoint/resume survives interruptions  
✅ **Respects servers** — Rate limiting, user-agent rotation, CAPTCHA handling  
✅ **Full audit trail** — Page-level logs + run summaries + change history  

---

## Output Files

After first run:

```
sppg_data/
├── runs/2026-04-23_14-22-10/
│   ├── sppg_raw.csv              # All scraped records
│   ├── sppg_clean.csv            # Deduplicated dataset (use this!)
│   ├── sppg_duplicates.csv       # Duplicate mapping
│   ├── scrape_log.csv            # Page-level events
│   └── run_summary.json          # Complete metadata
├── master/
│   ├── sppg_master.csv           # Historical dataset across all runs
│   └── sppg_changelog.csv        # Change audit trail
└── latest -> runs/2026-04-23_14-22-10
```

---

## Features

### Dynamic Target Detection
Reads "Hasil Pencarian" field from website — adapts when BGN adds/removes records.

### Incremental Updates
Run the scraper monthly to track changes:
- **NEW** records added to BGN website
- **REMOVED** records no longer listed
- **REINSTATED** records that return after removal

### Duplicate Detection
Two-level matching:
- **Strict:** Exact name + address match
- **Fuzzy:** Same district + similar name (configurable thresholds)

### Resume Capability
Interrupted mid-scrape? Just restart:
```bash
python scraper.py  # Automatically resumes from checkpoint
```

### Production Logging
- `scrape_log.csv` — Page-by-page events with timestamps
- `run_summary.json` — Complete session metadata
- `sppg_changelog.csv` — All changes across runs

---

## Configuration

Edit `config.json` to customize:

```json
{
  "delay_min": 1.5,                      // Min delay between pages (seconds)
  "delay_max": 3.5,                      // Max delay between pages
  "nama_similarity_threshold": 0.85,     // Name fuzzy matching threshold
  "address_similarity_threshold": 0.70   // Address fuzzy matching threshold
}
```

---

## Data Validation

Built-in validation with 8 automated checks:

```bash
python validate_sppg.py \
  --input sppg_data/latest/sppg_raw.csv \
  --target-count 26487
```

**Checks:**
- ✓ Target count match (±2%)
- ✓ Schema correctness (7 columns)
- ✓ No null values in critical fields
- ✓ No duplicate row numbers
- ✓ Valid UTF-8 encoding
- ✓ Geographic hierarchy consistency
- ✓ Scrape completeness (≥50%)

---

## Requirements

- **Python:** 3.8+
- **Dependencies:** `requests`, `beautifulsoup4`, `pandas`, `fuzzywuzzy`, `tqdm`
- **Network:** Access to `bgn.go.id`
- **Disk:** 200 MB minimum (for multiple runs)
- **Time:** 2-4 hours per run

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** — 5-minute setup guide
- **[README_FULL.md](README_FULL.md)** — Complete reference (587 lines)
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** — Build details
- **Code comments** — Inline documentation throughout

---

## Project Structure

```
sppg-scraper/
├── scraper.py                  # Main scraping engine (893 lines)
├── validate_sppg.py            # Data validation script (241 lines)
├── test_installation.py        # Setup verification (176 lines)
├── requirements.txt            # Python dependencies
├── config.json                 # Runtime configuration
├── README.md                   # This file
├── QUICKSTART.md               # Quick setup guide
└── README_FULL.md              # Complete documentation
```

---

## Usage Examples

### First Run (Baseline)
```bash
python scraper.py
```

Output:
```
Extracting target count from website...
✓ Target: 26,487 SPPG
✓ Expected pages: 2,649

Scraping: 100%|██████████| 2649/2649 [2:19:34<00:00]
✓ Scraped 26,487 records
✓ Master dataset created (26,487 ACTIVE records)
```

### Second Run (Incremental Update)
Run again weeks/months later:
```bash
python scraper.py
```

Output:
```
✓ Target: 26,510 SPPG
ℹ Target delta: +23 from previous run (+0.09%)

Delta Summary:
  NEW:        35 records
  REMOVED:    12 records
  UNCHANGED:  26,460 records

✓ Master dataset updated (26,495 ACTIVE, 27 REMOVED)
```

### View Changes
```bash
# Recent changes
tail -50 sppg_data/master/sppg_changelog.csv

# Filter for NEW records only
grep "NEW" sppg_data/master/sppg_changelog.csv

# Count active SPPG
awk -F';' '$11=="ACTIVE"' sppg_data/master/sppg_master.csv | wc -l
```

---

## Troubleshooting

### CAPTCHA Detected
```
⚠ CAPTCHA DETECTED
Please solve the CAPTCHA in your browser, then press Enter to continue...
```
**Solution:** Solve in browser, press Enter, scraper resumes automatically.

### Scraper Interrupted
**Solution:** Just restart — checkpoint/resume is automatic.

### Target Extraction Failed
**Cause:** Website HTML structure changed  
**Solution:** Check `debug_html_snippet.txt`, update regex in `extract_target_count()`

See [README_FULL.md](README_FULL.md) "Troubleshooting" for detailed solutions.

---

## Performance

**Expected metrics for ~26,500 records:**

| Metric | Value |
|--------|-------|
| Runtime | 2.5–3.0 hours |
| Success rate | ≥99% (with retry) |
| Network requests | ~2,650 |
| Data transfer | 50–100 MB |
| Disk per run | ~15–20 MB |

---

## Data Schema

### Raw CSV Columns
| Column | Description | Example |
|--------|-------------|---------|
| No | Row number from website | 1234 |
| Provinsi SPPG | Province name | DKI Jakarta |
| Kab./Kota SPPG | Regency/city | Jakarta Selatan |
| Kecamatan SPPG | District | Kebayoran Baru |
| Kelurahan/Desa SPPG | Village/subdistrict | Senayan |
| Alamat SPPG | Street address | Jl. Asia Afrika No. 8 |
| Nama SPPG | Kitchen name | Dapur MBG Senayan |

### Master Dataset Additional Columns
| Column | Description |
|--------|-------------|
| record_hash | SHA256 hash (stable ID across runs) |
| first_seen | When record first appeared |
| last_seen | When record last seen |
| status | ACTIVE / REMOVED / MODIFIED |

---

## Contributing

This is a single-purpose scraper built to PRD specifications. If you find bugs or the website structure changes:

1. Check `debug_html_snippet.txt` for HTML changes
2. Update regex patterns in `scraper.py` → `extract_target_count()`
3. Update table selectors in `scraper.py` → `parse_table()`
4. Test with `test_installation.py`

---

## License

Built for operational data collection from public government website.

**Data source:** [Badan Gizi Nasional (BGN)](https://www.bgn.go.id)  
**Website:** https://www.bgn.go.id/operasional-sppg

---

## Changelog

**v1.2 (2026-04-23)**
- Dynamic target detection from website
- Incremental update tracking
- Master dataset with change history
- Comprehensive validation
- Full checkpoint/resume capability

---

## Support

**Self-service:**
- Run `test_installation.py` to verify setup
- Check `scrape_log.csv` for debugging
- See [README_FULL.md](README_FULL.md) Troubleshooting section

**Logs for diagnosis:**
- `sppg_data/latest/scrape_log.csv` — Page events
- `sppg_data/latest/run_summary.json` — Session metadata
- `failed_pages.txt` — Retry candidates
- `debug_html_snippet.txt` — If extraction fails

---

**Built:** 2026-04-23 | **PRD:** v1.2 | **Status:** ✓ Production Ready
