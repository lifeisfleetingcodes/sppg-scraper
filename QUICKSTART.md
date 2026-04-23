# SPPG Scraper - Quick Start Guide

Get up and running in 5 minutes.

---

## Step 1: Install Dependencies

```bash
cd sppg_scraper
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed requests-2.31.0 beautifulsoup4-4.12.0 pandas-2.0.0 ...
```

---

## Step 2: Run First Scrape

```bash
python scraper.py
```

**What you'll see:**
```
============================================================
SPPG Data Scraper v1.2
BGN Website - Dynamic Target Detection + Incremental Updates
============================================================

Extracting target count from website...
✓ Target: 26,487 SPPG
✓ Expected pages: 2,649

Starting scrape...
Scraping: 0%|          | 0/2649 [00:00<?, ?page/s]
```

**Duration:** ~2.5 hours (runs unattended)

---

## Step 3: Check Results

After scrape completes:

```bash
# View directory structure
ls -la sppg_data/

# Check run summary
cat sppg_data/latest/run_summary.json

# Count records
wc -l sppg_data/latest/sppg_raw.csv
```

---

## Step 4: Validate Data

```bash
python validate_sppg.py \
  --input sppg_data/latest/sppg_raw.csv \
  --target-count $(python -c "import json; print(json.load(open('sppg_data/latest/run_summary.json'))['target_metrics']['target_count_from_website'])")
```

**Expected:**
```
OVERALL STATUS: PASS
```

---

## Important Files

**Your main outputs:**
- `sppg_data/latest/sppg_raw.csv` — All scraped data
- `sppg_data/latest/sppg_clean.csv` — Deduplicated data (use for analysis)
- `sppg_data/master/sppg_master.csv` — Historical dataset (all runs)

**Diagnostics:**
- `sppg_data/latest/scrape_log.csv` — Page-by-page log
- `sppg_data/latest/run_summary.json` — Complete metadata

---

## Common Issues

### Installation fails on fuzzywuzzy

```bash
# Install build tools first
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### "No module named 'requests'"

Virtual environment not activated:
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### Scraper stops midway

**It will resume automatically:**
```bash
python scraper.py
```

Output:
```
Resuming from page 1234
```

---

## Next Steps

1. **Run second scrape** (weeks/months later) → Detects changes
2. **Review changelog** → `sppg_data/master/sppg_changelog.csv`
3. **Analyze data** → Use `sppg_clean.csv` for your analysis
4. **Read full docs** → See `README.md`

---

## Need Help?

Check `README.md` section "Troubleshooting" for detailed solutions.

---

**You're ready to go!**
