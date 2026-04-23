# Contributing to SPPG Data Scraper

This is a purpose-built scraper for BGN operational data. Contributions are welcome for bug fixes, website structure updates, and feature enhancements.

---

## Reporting Issues

If the scraper breaks or produces incorrect results:

1. **Check website first:** Visit https://www.bgn.go.id/operasional-sppg
   - Has the HTML structure changed?
   - Is the "Hasil Pencarian" field still present?
   - Does the table format match expectations?

2. **Run diagnostics:**
   ```bash
   python test_installation.py
   ```

3. **Check debug files:**
   - `debug_html_snippet.txt` (if target extraction failed)
   - `sppg_data/latest/scrape_log.csv` (page-level errors)
   - `sppg_data/latest/run_summary.json` (session metadata)

4. **Open issue with:**
   - Python version
   - OS (Windows/Mac/Linux)
   - Error message or unexpected behavior
   - Relevant log excerpts
   - `debug_html_snippet.txt` if available

---

## Code Contributions

### Setup Development Environment

```bash
git clone https://github.com/YOUR_USERNAME/sppg-scraper.git
cd sppg-scraper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Making Changes

**Common modification points:**

1. **Website structure changed** → Update `scraper.py`:
   - `extract_target_count()` — Regex patterns for target count
   - `parse_table()` — BeautifulSoup selectors for table data

2. **Need additional fields** → Extend schema:
   - Add column in `parse_table()`
   - Update validation in `validate_sppg.py`
   - Document in README.md Data Schema section

3. **Rate limiting issues** → Adjust `config.json`:
   - Increase delays
   - Adjust cooling intervals
   - Test on small page range first

### Testing Changes

```bash
# Test installation
python test_installation.py

# Test scrape (first 5 pages only)
# Modify scraper.py temporarily:
# for page_num in range(1, 6):  # Test with 5 pages
python scraper.py

# Validate output
python validate_sppg.py --input sppg_data/latest/sppg_raw.csv --target-count {N}
```

### Pull Request Guidelines

1. **Branch naming:**
   - `fix/issue-description` (bug fixes)
   - `feature/feature-name` (new features)
   - `docs/update-description` (documentation)

2. **Commit messages:**
   - Clear, descriptive
   - Reference issue number if applicable
   - Example: "Fix target extraction for new HTML structure (#12)"

3. **PR description must include:**
   - What changed and why
   - How you tested it
   - Screenshots/logs if applicable

4. **Code style:**
   - Follow existing patterns
   - Keep functions modular
   - Add comments for complex logic
   - Run basic validation before submitting

---

## Feature Requests

This scraper is built to specific requirements (see PRD v1.2). New features should:

1. Align with core purpose (scraping + change tracking)
2. Not compromise reliability or data integrity
3. Be configurable (prefer `config.json` over hardcoded changes)

**In-scope examples:**
- Additional validation checks
- New duplicate detection algorithms
- Export format options (JSON, Excel)
- Performance optimizations

**Out-of-scope examples:**
- Real-time monitoring (design constraint)
- Web dashboard (separate project)
- Geocoding (planned for Phase 2)
- Email alerts (separate notification layer)

---

## Code of Conduct

- Be respectful and constructive
- Focus on technical merit
- Assume good intent
- This is a tool, not a community project — keep discussions technical

---

## Questions?

Open an issue tagged with `question` — no need for separate discussions forum.

---

**Thank you for contributing!**
