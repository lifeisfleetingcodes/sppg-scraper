#!/usr/bin/env python3
"""
SPPG Data Scraper - BGN Website
Version: 1.2
Author: Generated from PRD v1.2

Complete implementation with:
- Dynamic target detection from "Hasil Pencarian"
- Incremental update tracking
- Duplicate detection (strict + fuzzy)
- Checkpoint/resume capability
- Full logging and validation
"""

import hashlib
import json
import math
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from tqdm import tqdm

# Selenium for JavaScript-rendered content
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    'base_url': 'https://www.bgn.go.id/operasional-sppg',
    'delay_min': 1.5,
    'delay_max': 3.5,
    'timeout': 10,
    'max_retries': 5,
    'records_per_page': 10,
    'cooling_interval': 100,
    'cooling_duration': 20,
    'partial_threshold': 8,  # Flag pages with < 8 records
    'target_tolerance': 0.02,  # 2% tolerance for target match
    'completeness_threshold': 0.50,  # Abort if < 50% of target
    'nama_similarity_threshold': 0.85,
    'address_similarity_threshold': 0.70,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


# ============================================================
# DIRECTORY STRUCTURE
# ============================================================

class DirectoryManager:
    """Manage versioned run directories and master dataset location."""
    
    def __init__(self, base_dir: str = "sppg_data"):
        self.base_dir = Path(base_dir)
        self.runs_dir = self.base_dir / "runs"
        self.master_dir = self.base_dir / "master"
        self.latest_link = self.base_dir / "latest"
        
    def setup(self):
        """Create directory structure."""
        self.base_dir.mkdir(exist_ok=True)
        self.runs_dir.mkdir(exist_ok=True)
        self.master_dir.mkdir(exist_ok=True)
        
    def create_run_dir(self, run_id: str) -> Path:
        """Create timestamped run directory."""
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(exist_ok=True)
        return run_dir
    
    def get_latest_run(self) -> Optional[Path]:
        """Get most recent run directory."""
        if not self.runs_dir.exists():
            return None
        
        run_dirs = sorted([d for d in self.runs_dir.iterdir() if d.is_dir()])
        return run_dirs[-1] if run_dirs else None
    
    def update_latest_link(self, run_dir: Path):
        """Update symlink to latest run."""
        if self.latest_link.exists() or self.latest_link.is_symlink():
            self.latest_link.unlink()
        
        try:
            self.latest_link.symlink_to(run_dir.relative_to(self.base_dir))
        except Exception:
            # Windows or permission issues - skip symlink
            pass


# ============================================================
# LOGGING
# ============================================================

class ScraperLogger:
    """Dual logging: file (CSV) + console (progress)."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.entries = []
        
        # Initialize log file with header
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("timestamp;page;status;records_scraped;duration_seconds;error_type;error_message\n")
    
    def log_page(self, page: int, status: str, records: int, 
                 duration: float, error_type: str = "", error_msg: str = ""):
        """Log single page scrape result."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = {
            'timestamp': timestamp,
            'page': page,
            'status': status,
            'records': records,
            'duration': duration,
            'error_type': error_type,
            'error_msg': error_msg.replace(';', ',')  # Escape semicolons
        }
        self.entries.append(entry)
        
        # Append to file immediately
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp};{page};{status};{records};{duration:.2f};{error_type};{error_msg}\n")
    
    def get_stats(self) -> Dict:
        """Calculate logging statistics."""
        if not self.entries:
            return {}
        
        success = sum(1 for e in self.entries if e['status'] == 'SUCCESS')
        failed = sum(1 for e in self.entries if e['status'] == 'FAILED')
        partial = sum(1 for e in self.entries if e['status'] == 'PARTIAL')
        
        return {
            'total_pages': len(self.entries),
            'successful': success,
            'failed': failed,
            'partial': partial,
            'success_rate': success / len(self.entries) if self.entries else 0
        }


# ============================================================
# CHECKPOINT & RESUME
# ============================================================

class CheckpointManager:
    """Manage scraper state for resume capability."""
    
    def __init__(self, checkpoint_path: Path = Path(".scraper_checkpoint")):
        self.checkpoint_path = checkpoint_path
    
    def save(self, data: Dict):
        """Save checkpoint state."""
        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load(self) -> Optional[Dict]:
        """Load checkpoint state."""
        if not self.checkpoint_path.exists():
            return None
        
        try:
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load checkpoint: {e}")
            return None
    
    def clear(self):
        """Remove checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()


# ============================================================
# TARGET EXTRACTION
# ============================================================

def extract_target_count_with_selenium(url: str) -> int:
    """
    Extract total SPPG count using Selenium (handles JavaScript rendering).
    
    Args:
        url: URL to scrape
    
    Returns:
        int: Target count from website
    
    Raises:
        ValueError: If extraction fails
    """
    options = Options()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    
    driver = None
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Load page
        driver.get(url)
        
        # Wait for "Hasil Pencarian" or "Total Seluruh" to appear
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hasil Pencarian') or contains(text(), 'Total Seluruh')]"))
            )
        except TimeoutException:
            pass  # Continue anyway, element might be there
        
        # Give JavaScript time to render
        time.sleep(2)
        
        # Get page source after JavaScript execution
        html_content = driver.page_source
        
        # Try to extract from rendered HTML
        # Strategy 1: Look for "Hasil Pencarian" followed by number
        pattern1 = r'Hasil\s+Pencarian\s*</.*?>\s*([\d\.]+)\s+SPPG'
        match1 = re.search(pattern1, html_content, re.IGNORECASE | re.DOTALL)
        
        if match1:
            count_str = match1.group(1).replace('.', '').replace(',', '')
            if len(count_str) >= 4:
                return int(count_str)
        
        # Strategy 2: Look for "Total Seluruh SPPG Operasional"
        pattern2 = r'Total\s+Seluruh\s+SPPG\s+Operasional\s*</.*?>\s*([\d\.]+)'
        match2 = re.search(pattern2, html_content, re.IGNORECASE | re.DOTALL)
        
        if match2:
            count_str = match2.group(1).replace('.', '').replace(',', '')
            if len(count_str) >= 4:
                print("⚠ Used fallback: 'Total Seluruh SPPG Operasional'")
                return int(count_str)
        
        # Strategy 3: Try simpler pattern - just find large numbers
        pattern3 = r'(2[0-9]\.?[0-9]{3})\s+SPPG'
        match3 = re.search(pattern3, html_content)
        
        if match3:
            count_str = match3.group(1).replace('.', '').replace(',', '')
            print(f"⚠ Used pattern matching: found {count_str}")
            return int(count_str)
        
        # Save debug info
        debug_path = Path("debug_html_rendered.txt")
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(html_content[:15000])
        
        raise ValueError(
            f"Could not extract target count from JavaScript-rendered page.\n"
            f"Tried multiple patterns on rendered HTML.\n"
            f"HTML snippet saved to {debug_path}"
        )
    
    finally:
        if driver:
            driver.quit()


def extract_target_count(html_content: str) -> int:
    """
    Extract total SPPG count from 'Hasil Pencarian' field.
    
    NOTE: This function is kept for backward compatibility but may not work
    with JavaScript-rendered pages. Use extract_target_count_with_selenium instead.
    
    Args:
        html_content: Raw HTML from first page
    
    Returns:
        int: Target count from website
    
    Raises:
        ValueError: If extraction fails from both sources
    """
    # Strategy 1: Search for "Hasil Pencarian" pattern
    # Look for "Hasil Pencarian" followed by a number with optional thousand separators
    pattern1 = r'Hasil\s+Pencarian\s*\n?\s*([\d\.]+)\s+SPPG'
    match1 = re.search(pattern1, html_content, re.IGNORECASE)
    
    if match1:
        count_str = match1.group(1).replace('.', '').replace(',', '')
        if len(count_str) >= 4:  # Sanity check: should be at least 4 digits
            return int(count_str)
    
    # Strategy 2: Fallback to "Total Seluruh SPPG Operasional"
    pattern2 = r'Total\s+Seluruh\s+SPPG\s+Operasional\s*\n?\s*([\d\.]+)'
    match2 = re.search(pattern2, html_content, re.IGNORECASE)
    
    if match2:
        count_str = match2.group(1).replace('.', '').replace(',', '')
        if len(count_str) >= 4:  # Sanity check
            print("⚠ Used fallback: 'Total Seluruh SPPG Operasional'")
            return int(count_str)
    
    # Both strategies failed - save debug output
    debug_path = Path("debug_html_snippet.txt")
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(html_content[:10000])  # Save more HTML for debugging
    
    raise ValueError(
        f"Could not extract target count from website.\n"
        f"Searched for: 'Hasil Pencarian' and 'Total Seluruh SPPG Operasional'\n"
        f"HTML snippet saved to {debug_path}\n"
        f"This page likely requires JavaScript rendering. Using Selenium instead."
    )


def calculate_expected_pages(target_count: int, records_per_page: int = 10) -> int:
    """Calculate total pages needed to scrape target count."""
    return math.ceil(target_count / records_per_page)


# ============================================================
# SCRAPING ENGINE
# ============================================================

class SPPGScraper:
    """Main scraping engine with retry logic and error handling."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.session = requests.Session()
        self.failed_pages = []
        self.partial_pages = []
        
        # Adaptive rate limiting
        self.current_delay = 0.5  # Start optimistic (faster than default)
        self.min_delay = 0.3      # Minimum delay (fastest allowed)
        self.max_delay = 10.0     # Maximum delay (when heavily rate limited)
        self.success_count = 0    # Track consecutive successes
        self.backoff_multiplier = 2.0  # How much to slow down on errors
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent for rotation."""
        return random.choice(USER_AGENTS)
    
    def adjust_delay(self, success: bool, error_type: str = ""):
        """
        Adjust delay based on request success/failure.
        
        Speeds up on success, slows down on rate limiting.
        """
        if success:
            self.success_count += 1
            # Speed up after 5 consecutive successes
            if self.success_count >= 5:
                old_delay = self.current_delay
                self.current_delay = max(
                    self.min_delay,
                    self.current_delay * 0.8  # Reduce by 20%
                )
                if old_delay != self.current_delay:
                    print(f"✓ Speeding up: {old_delay:.2f}s → {self.current_delay:.2f}s per page")
                self.success_count = 0
        else:
            # Slow down on rate limiting or errors
            if error_type in ["HTTP_ERROR", "TIMEOUT"]:
                old_delay = self.current_delay
                self.current_delay = min(
                    self.max_delay,
                    self.current_delay * self.backoff_multiplier
                )
                self.success_count = 0
                print(f"⚠ Rate limited. Slowing down: {old_delay:.2f}s → {self.current_delay:.2f}s per page")
    
    def get_current_delay(self) -> float:
        """Get current adaptive delay."""
        return self.current_delay
    
    def _check_captcha(self, response: requests.Response) -> bool:
        """Detect CAPTCHA or rate limiting."""
        if response.status_code == 429:
            return True
        
        content_lower = response.text.lower()
        captcha_indicators = ['captcha', 'recaptcha', 'bot detection', 'verify you are human']
        
        return any(indicator in content_lower for indicator in captcha_indicators)
    
    def fetch_page(self, page_num: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch single page with retry logic.
        
        Returns:
            (html_content, error_type) tuple
            If successful: (html, None)
            If failed: (None, error_type)
        """
        url = f"{self.config['base_url']}?page={page_num}&search="
        
        for attempt in range(self.config['max_retries']):
            try:
                headers = {'User-Agent': self._get_random_user_agent()}
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.config['timeout']
                )
                
                # Check for CAPTCHA
                if self._check_captcha(response):
                    return None, "CAPTCHA"
                
                # Check HTTP errors
                if response.status_code != 200:
                    if attempt < self.config['max_retries'] - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return None, "HTTP_ERROR"
                
                return response.text, None
            
            except requests.Timeout:
                if attempt < self.config['max_retries'] - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None, "TIMEOUT"
            
            except requests.RequestException as e:
                if attempt < self.config['max_retries'] - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None, "HTTP_ERROR"
        
        return None, "UNKNOWN"
    
    def parse_table(self, html_content: str) -> List[Dict]:
        """
        Extract SPPG records from HTML table.
        
        Returns:
            List of record dictionaries
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        records = []
        
        # Find the main data table
        table = soup.find('table')
        if not table:
            return records
        
        tbody = table.find('tbody')
        if not tbody:
            return records
        
        rows = tbody.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            
            if len(cells) >= 7:
                record = {
                    'No': cells[0].get_text(strip=True),
                    'Provinsi SPPG': cells[1].get_text(strip=True),
                    'Kab./Kota SPPG': cells[2].get_text(strip=True),
                    'Kecamatan SPPG': cells[3].get_text(strip=True),
                    'Kelurahan/Desa SPPG': cells[4].get_text(strip=True),
                    'Alamat SPPG': cells[5].get_text(strip=True),
                    'Nama SPPG': cells[6].get_text(strip=True),
                }
                records.append(record)
        
        return records
    
    def scrape_all_pages(self, target_count: int, expected_pages: int, 
                         logger: ScraperLogger, checkpoint: CheckpointManager,
                         run_id: str, run_dir: Path) -> pd.DataFrame:
        """
        Main scraping loop with progress tracking and adaptive rate limiting.
        
        Args:
            target_count: Expected total records from website
            expected_pages: Calculated page count
            logger: Logger instance
            checkpoint: Checkpoint manager
            run_id: Current run identifier
            run_dir: Directory for this run's outputs
        
        Returns:
            DataFrame of all scraped records
        """
        all_records = []
        
        # Check for resume
        checkpoint_data = checkpoint.load()
        start_page = 1
        
        if checkpoint_data and checkpoint_data.get('run_id') == run_id:
            start_page = checkpoint_data.get('last_completed_page', 0) + 1
            print(f"Resuming from page {start_page}")
        
        # Progress bar
        with tqdm(total=expected_pages, desc="Scraping", unit="page", 
                  initial=start_page-1) as pbar:
            
            for page_num in range(start_page, expected_pages + 1):
                start_time = time.time()
                
                # Fetch page
                html_content, error_type = self.fetch_page(page_num)
                
                if error_type == "CAPTCHA":
                    print("\n" + "="*60)
                    print("⚠ CAPTCHA DETECTED")
                    print("="*60)
                    print("Manual intervention required.")
                    print("Please solve the CAPTCHA in your browser, then press Enter to continue...")
                    input()
                    # Retry after user intervention
                    html_content, error_type = self.fetch_page(page_num)
                
                duration = time.time() - start_time
                
                if html_content is None:
                    # Log failure
                    logger.log_page(page_num, "FAILED", 0, duration, error_type, 
                                   f"Failed after {self.config['max_retries']} retries")
                    self.failed_pages.append(page_num)
                    self.adjust_delay(success=False, error_type=error_type)
                    pbar.update(1)
                    continue
                
                # Parse table
                try:
                    records = self.parse_table(html_content)
                    
                    if len(records) < self.config['partial_threshold']:
                        logger.log_page(page_num, "PARTIAL", len(records), duration)
                        self.partial_pages.append((page_num, len(records)))
                    else:
                        logger.log_page(page_num, "SUCCESS", len(records), duration)
                    
                    all_records.extend(records)
                    
                    # Adjust delay based on success
                    self.adjust_delay(success=True)
                    
                    # Update checkpoint
                    checkpoint.save({
                        'last_completed_page': page_num,
                        'timestamp': datetime.now().isoformat(),
                        'total_records_scraped': len(all_records),
                        'run_id': run_id,
                        'target_count': target_count,
                        'expected_pages': expected_pages,
                        'current_delay': self.current_delay
                    })
                    
                    # Save partial data EVERY PAGE
                    if len(all_records) > 0:
                        partial_df = pd.DataFrame(all_records)
                        partial_path = run_dir / "sppg_partial.csv"
                        partial_df.to_csv(partial_path, sep=';', index=False, encoding='utf-8')
                
                except Exception as e:
                    logger.log_page(page_num, "FAILED", 0, duration, "PARSE_ERROR", str(e))
                    self.failed_pages.append(page_num)
                    self.adjust_delay(success=False, error_type="PARSE_ERROR")
                
                # Rate limiting with adaptive delay
                if page_num % self.config['cooling_interval'] == 0:
                    time.sleep(self.config['cooling_duration'])
                else:
                    # Use adaptive delay instead of random delay
                    time.sleep(self.get_current_delay())
                
                pbar.update(1)
        
        # Final save of partial data
        if len(all_records) > 0:
            partial_df = pd.DataFrame(all_records)
            partial_path = run_dir / "sppg_partial.csv"
            partial_df.to_csv(partial_path, sep=';', index=False, encoding='utf-8')
            print(f"\n✓ Partial data saved: {len(all_records)} records in {partial_path.name}")
        
        # Retry failed pages
        if self.failed_pages:
            print(f"\nRetrying {len(self.failed_pages)} failed pages...")
            retry_success = []
            
            for page_num in self.failed_pages:
                start_time = time.time()
                html_content, error_type = self.fetch_page(page_num)
                duration = time.time() - start_time
                
                if html_content:
                    try:
                        records = self.parse_table(html_content)
                        all_records.extend(records)
                        logger.log_page(page_num, "SUCCESS", len(records), duration)
                        retry_success.append(page_num)
                    except Exception as e:
                        logger.log_page(page_num, "FAILED", 0, duration, "PARSE_ERROR", str(e))
                
                time.sleep(self.get_current_delay())
            
            # Update failed list
            self.failed_pages = [p for p in self.failed_pages if p not in retry_success]
        
        # Convert to DataFrame
        df = pd.DataFrame(all_records)
        
        return df


# ============================================================
# VALIDATION
# ============================================================

def validate_scrape(df: pd.DataFrame, target_count: int, 
                    partial_pages: List[Tuple], run_dir: Path) -> bool:
    """
    Validate scraped data against target count.
    
    Returns:
        bool: True if validation passes critical checks
    """
    scraped_count = len(df)
    
    print("\n" + "="*60)
    print("VALIDATION CHECKS")
    print("="*60)
    
    # Critical check: Completeness
    if scraped_count < (target_count * CONFIG['completeness_threshold']):
        print(f"✗ CRITICAL: Scrape appears incomplete")
        print(f"  Target: {target_count}")
        print(f"  Scraped: {scraped_count}")
        print(f"  Percentage: {scraped_count/target_count:.1%}")
        return False
    
    # Check: Target match
    delta = abs(scraped_count - target_count)
    tolerance = target_count * CONFIG['target_tolerance']
    
    if delta <= tolerance:
        print(f"✓ Target match: {scraped_count}/{target_count}")
    else:
        print(f"⚠ Target mismatch: {scraped_count}/{target_count} (delta: {scraped_count - target_count:+d})")
    
    # Check: Schema
    expected_columns = ['No', 'Provinsi SPPG', 'Kab./Kota SPPG', 'Kecamatan SPPG',
                       'Kelurahan/Desa SPPG', 'Alamat SPPG', 'Nama SPPG']
    
    if list(df.columns) == expected_columns:
        print(f"✓ Schema: 7 columns")
    else:
        print(f"✗ Schema mismatch: {list(df.columns)}")
        return False
    
    # Check: Null values
    critical_cols = ['Provinsi SPPG', 'Kab./Kota SPPG', 'Nama SPPG']
    null_counts = {}
    
    for col in critical_cols:
        null_count = df[col].isna().sum()
        null_counts[col] = null_count
        
        if null_count == 0:
            print(f"✓ No null values in {col}")
        else:
            print(f"✗ CRITICAL: {null_count} null values in {col}")
            return False
    
    # Info: Partial pages
    if partial_pages:
        print(f"⚠ {len(partial_pages)} partial pages (< {CONFIG['partial_threshold']} records)")
        
        # Write partial pages file
        partial_path = run_dir / "partial_pages.txt"
        with open(partial_path, 'w') as f:
            f.write("page,record_count\n")
            for page, count in partial_pages:
                f.write(f"{page},{count}\n")
    
    print("="*60)
    return True


# ============================================================
# DEDUPLICATION
# ============================================================

def compute_record_hash(row: pd.Series) -> str:
    """
    Generate stable identifier for SPPG record.
    
    Uses: Provinsi + Kab/Kota + Kecamatan + Kelurahan + Nama
    """
    key_fields = [
        str(row['Provinsi SPPG']),
        str(row['Kab./Kota SPPG']),
        str(row['Kecamatan SPPG']),
        str(row['Kelurahan/Desa SPPG']),
        str(row['Nama SPPG'])
    ]
    
    normalized = '|'.join([f.lower().strip() for f in key_fields])
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def find_duplicates(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detect strict and fuzzy duplicates.
    
    Returns:
        (clean_df, duplicates_df) tuple
    """
    duplicates = []
    duplicate_ids = set()
    dup_id_counter = 1
    
    # Level 1: Strict duplicates (Nama + Alamat exact match)
    for idx, row in df.iterrows():
        if idx in duplicate_ids:
            continue
        
        # Find exact matches
        mask = (
            (df['Nama SPPG'].str.lower().str.strip() == row['Nama SPPG'].lower().strip()) &
            (df['Alamat SPPG'].str.lower().str.strip() == row['Alamat SPPG'].lower().strip()) &
            (df.index != idx)
        )
        
        matches = df[mask]
        
        for match_idx, match_row in matches.iterrows():
            if match_idx not in duplicate_ids:
                duplicates.append({
                    'duplicate_id': f"DUP{dup_id_counter:04d}",
                    'original_row_no': row['No'],
                    'duplicate_row_no': match_row['No'],
                    'match_type': 'STRICT',
                    'confidence_score': 1.00,
                    'review_flag': ''
                })
                duplicate_ids.add(match_idx)
                dup_id_counter += 1
    
    # Level 2: Fuzzy duplicates (Kecamatan + Kelurahan exact, Nama similar)
    for idx, row in df.iterrows():
        if idx in duplicate_ids:
            continue
        
        # Find candidates with same Kecamatan + Kelurahan
        mask = (
            (df['Kecamatan SPPG'].str.lower().str.strip() == row['Kecamatan SPPG'].lower().strip()) &
            (df['Kelurahan/Desa SPPG'].str.lower().str.strip() == row['Kelurahan/Desa SPPG'].lower().strip()) &
            (df.index != idx)
        )
        
        candidates = df[mask]
        
        for cand_idx, cand_row in candidates.iterrows():
            if cand_idx in duplicate_ids:
                continue
            
            # Check name similarity
            nama_sim = fuzz.ratio(
                row['Nama SPPG'].lower().strip(),
                cand_row['Nama SPPG'].lower().strip()
            ) / 100.0
            
            if nama_sim >= CONFIG['nama_similarity_threshold']:
                # Check address similarity
                addr_sim = fuzz.ratio(
                    row['Alamat SPPG'].lower().strip(),
                    cand_row['Alamat SPPG'].lower().strip()
                ) / 100.0
                
                confidence = (nama_sim + addr_sim) / 2
                
                if addr_sim >= CONFIG['address_similarity_threshold']:
                    match_type = 'FUZZY_HIGH'
                    review_flag = ''
                else:
                    match_type = 'FUZZY_UNCERTAIN'
                    review_flag = 'MANUAL_REVIEW'
                
                duplicates.append({
                    'duplicate_id': f"DUP{dup_id_counter:04d}",
                    'original_row_no': row['No'],
                    'duplicate_row_no': cand_row['No'],
                    'match_type': match_type,
                    'confidence_score': round(confidence, 2),
                    'review_flag': review_flag
                })
                duplicate_ids.add(cand_idx)
                dup_id_counter += 1
    
    # Clean dataset (remove duplicates)
    clean_df = df[~df.index.isin(duplicate_ids)].copy()
    
    # Duplicates dataframe
    duplicates_df = pd.DataFrame(duplicates)
    
    return clean_df, duplicates_df


# ============================================================
# DELTA DETECTION
# ============================================================

def load_master_dataset(master_path: Path) -> Optional[pd.DataFrame]:
    """Load master dataset if exists."""
    if not master_path.exists():
        return None
    
    try:
        df = pd.read_csv(master_path, sep=';', encoding='utf-8')
        return df
    except Exception as e:
        print(f"Warning: Could not load master dataset: {e}")
        return None


def compute_delta(current_df: pd.DataFrame, master_df: Optional[pd.DataFrame]) -> Dict:
    """
    Compare current scrape to master dataset.
    
    Returns:
        Dictionary of delta statistics
    """
    # Add hashes to current dataset
    current_df['record_hash'] = current_df.apply(compute_record_hash, axis=1)
    current_hashes = set(current_df['record_hash'])
    
    if master_df is None:
        # First run - all records are NEW
        return {
            'new': len(current_df),
            'removed': 0,
            'modified': 0,
            'unchanged': 0,
            'reinstated': 0,
            'new_records': current_df['record_hash'].tolist(),
            'removed_records': [],
            'modified_records': [],
            'reinstated_records': []
        }
    
    # Get active records from master
    active_master = master_df[master_df['status'] == 'ACTIVE']
    master_hashes = set(active_master['record_hash'])
    
    # Compute deltas
    new_hashes = current_hashes - master_hashes
    removed_hashes = master_hashes - current_hashes
    unchanged_hashes = current_hashes & master_hashes
    
    # Check for reinstated records (previously REMOVED, now back)
    removed_master = master_df[master_df['status'] == 'REMOVED']
    removed_master_hashes = set(removed_master['record_hash'])
    reinstated_hashes = current_hashes & removed_master_hashes
    
    # Adjust NEW count (exclude reinstated)
    new_hashes = new_hashes - reinstated_hashes
    
    return {
        'new': len(new_hashes),
        'removed': len(removed_hashes),
        'modified': 0,  # TODO: Implement modification detection
        'unchanged': len(unchanged_hashes),
        'reinstated': len(reinstated_hashes),
        'new_records': list(new_hashes),
        'removed_records': list(removed_hashes),
        'modified_records': [],
        'reinstated_records': list(reinstated_hashes)
    }


def update_master(current_df: pd.DataFrame, master_df: Optional[pd.DataFrame],
                  delta: Dict, run_timestamp: str, master_dir: Path) -> pd.DataFrame:
    """
    Update master dataset with current run results.
    
    Returns:
        Updated master DataFrame
    """
    # Ensure current_df has hashes
    if 'record_hash' not in current_df.columns:
        current_df['record_hash'] = current_df.apply(compute_record_hash, axis=1)
    
    if master_df is None:
        # First run - create master
        master_df = current_df.copy()
        master_df['first_seen'] = run_timestamp
        master_df['last_seen'] = run_timestamp
        master_df['status'] = 'ACTIVE'
        
        # Reorder columns
        cols = ['record_hash'] + [c for c in current_df.columns if c != 'record_hash'] + \
               ['first_seen', 'last_seen', 'status']
        master_df = master_df[cols]
        
        return master_df
    
    # Update existing master
    updated_master = master_df.copy()
    
    # 1. Mark REMOVED records
    for hash_val in delta['removed_records']:
        mask = (updated_master['record_hash'] == hash_val) & (updated_master['status'] == 'ACTIVE')
        updated_master.loc[mask, 'status'] = 'REMOVED'
        updated_master.loc[mask, 'last_seen'] = run_timestamp
    
    # 2. Update UNCHANGED records
    for hash_val in set(current_df['record_hash']):
        if hash_val not in delta['new_records'] and hash_val not in delta['reinstated_records']:
            mask = updated_master['record_hash'] == hash_val
            updated_master.loc[mask, 'last_seen'] = run_timestamp
    
    # 3. Add NEW records
    new_records = current_df[current_df['record_hash'].isin(delta['new_records'])].copy()
    if not new_records.empty:
        new_records['first_seen'] = run_timestamp
        new_records['last_seen'] = run_timestamp
        new_records['status'] = 'ACTIVE'
        
        # Ensure column alignment
        for col in updated_master.columns:
            if col not in new_records.columns:
                new_records[col] = ''
        
        updated_master = pd.concat([updated_master, new_records], ignore_index=True)
    
    # 4. Reinstate REMOVED records
    for hash_val in delta['reinstated_records']:
        mask = updated_master['record_hash'] == hash_val
        updated_master.loc[mask, 'status'] = 'ACTIVE'
        updated_master.loc[mask, 'last_seen'] = run_timestamp
    
    return updated_master


def write_changelog(delta: Dict, current_df: pd.DataFrame, master_df: Optional[pd.DataFrame],
                    run_timestamp: str, changelog_path: Path):
    """Append changes to changelog file."""
    entries = []
    
    # Ensure current_df has hashes
    if 'record_hash' not in current_df.columns:
        current_df['record_hash'] = current_df.apply(compute_record_hash, axis=1)
    
    # NEW records
    for hash_val in delta['new_records']:
        record = current_df[current_df['record_hash'] == hash_val].iloc[0]
        entries.append({
            'timestamp': run_timestamp,
            'change_type': 'NEW',
            'record_hash': hash_val,
            'provinsi': record['Provinsi SPPG'],
            'kab_kota': record['Kab./Kota SPPG'],
            'nama_sppg': record['Nama SPPG'],
            'old_value': '',
            'new_value': '',
            'notes': 'New SPPG detected'
        })
    
    # REMOVED records
    if master_df is not None:
        for hash_val in delta['removed_records']:
            record = master_df[master_df['record_hash'] == hash_val].iloc[0]
            entries.append({
                'timestamp': run_timestamp,
                'change_type': 'REMOVED',
                'record_hash': hash_val,
                'provinsi': record['Provinsi SPPG'],
                'kab_kota': record['Kab./Kota SPPG'],
                'nama_sppg': record['Nama SPPG'],
                'old_value': '',
                'new_value': '',
                'notes': 'No longer on website'
            })
    
    # REINSTATED records
    if master_df is not None:
        for hash_val in delta['reinstated_records']:
            record = current_df[current_df['record_hash'] == hash_val].iloc[0]
            entries.append({
                'timestamp': run_timestamp,
                'change_type': 'REINSTATED',
                'record_hash': hash_val,
                'provinsi': record['Provinsi SPPG'],
                'kab_kota': record['Kab./Kota SPPG'],
                'nama_sppg': record['Nama SPPG'],
                'old_value': '',
                'new_value': '',
                'notes': 'Previously removed record returned'
            })
    
    # Write or append to changelog
    df_new = pd.DataFrame(entries)
    
    if not df_new.empty:
        if changelog_path.exists():
            df_new.to_csv(changelog_path, mode='a', header=False, sep=';', 
                         index=False, encoding='utf-8')
        else:
            df_new.to_csv(changelog_path, sep=';', index=False, encoding='utf-8')


# ============================================================
# RUN SUMMARY
# ============================================================

def generate_run_summary(run_id: str, start_time: datetime, end_time: datetime,
                        target_count: int, previous_target: Optional[int],
                        expected_pages: int, scraped_count: int,
                        logger: ScraperLogger, duplicate_count: Dict,
                        delta: Dict, failed_pages: List, partial_pages: List,
                        output_files: Dict, master_stats: Dict) -> Dict:
    """Generate comprehensive run summary JSON."""
    
    log_stats = logger.get_stats()
    
    summary = {
        'run_id': run_id,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        
        'target_metrics': {
            'target_count_from_website': target_count,
            'previous_run_target': previous_target,
            'target_delta': target_count - previous_target if previous_target else target_count,
            'target_delta_pct': (target_count - previous_target) / previous_target if previous_target else None,
            'expected_pages': expected_pages
        },
        
        'scrape_metrics': {
            'total_pages_attempted': expected_pages,
            'successful_pages': log_stats.get('successful', 0),
            'failed_pages': log_stats.get('failed', 0),
            'partial_pages': log_stats.get('partial', 0),
            'total_records_scraped': scraped_count,
            'scrape_vs_target_delta': scraped_count - target_count,
            'scrape_vs_target_match': abs(scraped_count - target_count) <= (target_count * CONFIG['target_tolerance']),
            'success_rate': log_stats.get('success_rate', 0),
            'failed_page_list': failed_pages,
            'partial_page_count': len(partial_pages)
        },
        
        'deduplication_metrics': {
            'duplicate_count': duplicate_count['total'],
            'strict_duplicates': duplicate_count['strict'],
            'fuzzy_duplicates': duplicate_count['fuzzy']
        },
        
        'delta_statistics': {
            'previous_run_id': None,  # Will be filled if available
            'records_new': delta.get('new', 0),
            'records_removed': delta.get('removed', 0),
            'records_modified': delta.get('modified', 0),
            'records_unchanged': delta.get('unchanged', 0),
            'records_reinstated': delta.get('reinstated', 0),
            'master_total_active': master_stats.get('active', scraped_count),
            'master_total_removed': master_stats.get('removed', 0),
            'changelog_entries_added': delta.get('new', 0) + delta.get('removed', 0) + delta.get('reinstated', 0)
        },
        
        'output_files': output_files
    }
    
    return summary


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main scraper execution flow."""
    
    print("="*60)
    print("SPPG Data Scraper v1.2")
    print("BGN Website - Dynamic Target Detection + Incremental Updates")
    print("="*60)
    print()
    
    # Initialize
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    start_time = datetime.now()
    
    dir_manager = DirectoryManager()
    dir_manager.setup()
    
    run_dir = dir_manager.create_run_dir(run_id)
    
    logger = ScraperLogger(run_dir / "scrape_log.csv")
    checkpoint = CheckpointManager()
    scraper = SPPGScraper(CONFIG)
    
    # Step 1: Extract target count using Selenium
    print("Extracting target count from website (using browser)...")
    
    try:
        url = f"{CONFIG['base_url']}?page=1&search="
        target_count = extract_target_count_with_selenium(url)
        expected_pages = calculate_expected_pages(target_count, CONFIG['records_per_page'])
        
        print(f"✓ Target: {target_count:,} SPPG")
        print(f"✓ Expected pages: {expected_pages:,}")
        print()
        
    except Exception as e:
        print(f"✗ Failed to extract target count: {e}")
        print("\nTrying fallback with regular HTTP request...")
        
        # Fallback: try regular requests (might not work with JS-rendered pages)
        try:
            html, error = scraper.fetch_page(1)
            if html is None:
                print(f"✗ Failed to fetch first page: {error}")
                sys.exit(1)
            
            target_count = extract_target_count(html)
            expected_pages = calculate_expected_pages(target_count, CONFIG['records_per_page'])
            
            print(f"✓ Target: {target_count:,} SPPG")
            print(f"✓ Expected pages: {expected_pages:,}")
            print()
        except ValueError as e:
            print(f"✗ {e}")
            sys.exit(1)
    
    # Check for previous run target
    previous_run = dir_manager.get_latest_run()
    previous_target = None
    
    if previous_run and previous_run != run_dir:
        try:
            prev_summary_path = previous_run / "run_summary.json"
            if prev_summary_path.exists():
                with open(prev_summary_path, 'r') as f:
                    prev_summary = json.load(f)
                    previous_target = prev_summary['target_metrics']['target_count_from_website']
                    
                    if previous_target:
                        delta_pct = (target_count - previous_target) / previous_target
                        
                        if abs(delta_pct) > 0.50:
                            print(f"⚠ CRITICAL: Target count changed by {delta_pct:.1%}")
                            print(f"  Previous: {previous_target:,}")
                            print(f"  Current: {target_count:,}")
                            print("  Verify this is expected before proceeding.")
                            print()
                            response = input("Continue? (yes/no): ")
                            if response.lower() != 'yes':
                                print("Aborted by user.")
                                sys.exit(0)
                        elif abs(delta_pct) > 0.10:
                            print(f"⚠ Target count changed by {delta_pct:.1%}")
                            print(f"  Previous: {previous_target:,}")
                            print(f"  Current: {target_count:,}")
                            print()
                        else:
                            print(f"ℹ Target delta: {target_count - previous_target:+,} ({delta_pct:+.2%})")
                            print()
        except Exception as e:
            print(f"Warning: Could not load previous run data: {e}")
            print()
    
    # Step 2: Scrape all pages
    print("Starting scrape...")
    df_raw = scraper.scrape_all_pages(target_count, expected_pages, logger, checkpoint, run_id, run_dir)
    
    print(f"\n✓ Scraped {len(df_raw):,} records")
    
    # Step 3: Validate
    if not validate_scrape(df_raw, target_count, scraper.partial_pages, run_dir):
        print("\n✗ Validation failed. Aborting.")
        sys.exit(1)
    
    # Save raw CSV
    raw_path = run_dir / "sppg_raw.csv"
    df_raw.to_csv(raw_path, sep=';', index=False, encoding='utf-8')
    print(f"\n✓ Saved raw data: {raw_path}")
    
    # Step 4: Deduplicate
    print("\nDetecting duplicates...")
    df_clean, df_duplicates = find_duplicates(df_raw)
    
    strict_count = len(df_duplicates[df_duplicates['match_type'] == 'STRICT']) if not df_duplicates.empty else 0
    fuzzy_count = len(df_duplicates[df_duplicates['match_type'].str.startswith('FUZZY')]) if not df_duplicates.empty else 0
    
    print(f"✓ Found {len(df_duplicates)} duplicates")
    print(f"  Strict: {strict_count}")
    print(f"  Fuzzy: {fuzzy_count}")
    
    clean_path = run_dir / "sppg_clean.csv"
    df_clean.to_csv(clean_path, sep=';', index=False, encoding='utf-8')
    
    if not df_duplicates.empty:
        dup_path = run_dir / "sppg_duplicates.csv"
        df_duplicates.to_csv(dup_path, sep=';', index=False, encoding='utf-8')
    
    # Step 5: Delta detection
    print("\nComputing delta from previous run...")
    
    master_path = dir_manager.master_dir / "sppg_master.csv"
    changelog_path = dir_manager.master_dir / "sppg_changelog.csv"
    
    master_df = load_master_dataset(master_path)
    delta = compute_delta(df_raw, master_df)
    
    if master_df is not None:
        print(f"\nDelta Summary:")
        print(f"  NEW:        {delta['new']:,} records")
        print(f"  REMOVED:    {delta['removed']:,} records")
        print(f"  MODIFIED:   {delta['modified']:,} records")
        print(f"  UNCHANGED:  {delta['unchanged']:,} records")
        if delta['reinstated'] > 0:
            print(f"  REINSTATED: {delta['reinstated']:,} records")
    
    # Update master dataset
    updated_master = update_master(df_raw, master_df, delta, start_time.isoformat(), 
                                   dir_manager.master_dir)
    updated_master.to_csv(master_path, sep=';', index=False, encoding='utf-8')
    
    # Write changelog
    write_changelog(delta, df_raw, master_df, start_time.isoformat(), changelog_path)
    
    master_stats = {
        'active': len(updated_master[updated_master['status'] == 'ACTIVE']),
        'removed': len(updated_master[updated_master['status'] == 'REMOVED'])
    }
    
    print(f"\n✓ Master dataset updated ({master_stats['active']:,} ACTIVE, {master_stats['removed']:,} REMOVED)")
    
    # Step 6: Write failed pages if any
    if scraper.failed_pages:
        failed_path = run_dir / "failed_pages.txt"
        with open(failed_path, 'w') as f:
            f.write('\n'.join(map(str, scraper.failed_pages)))
    
    # Step 7: Generate run summary
    end_time = datetime.now()
    
    output_files = {
        'raw': str(raw_path.relative_to(dir_manager.base_dir)),
        'clean': str(clean_path.relative_to(dir_manager.base_dir)),
        'duplicates': str((run_dir / "sppg_duplicates.csv").relative_to(dir_manager.base_dir)) if not df_duplicates.empty else None,
        'log': str((run_dir / "scrape_log.csv").relative_to(dir_manager.base_dir)),
        'master': str(master_path.relative_to(dir_manager.base_dir)),
        'changelog': str(changelog_path.relative_to(dir_manager.base_dir))
    }
    
    duplicate_count = {
        'total': len(df_duplicates),
        'strict': strict_count,
        'fuzzy': fuzzy_count
    }
    
    summary = generate_run_summary(
        run_id, start_time, end_time, target_count, previous_target,
        expected_pages, len(df_raw), logger, duplicate_count,
        delta, scraper.failed_pages, scraper.partial_pages,
        output_files, master_stats
    )
    
    # Add previous run ID if available
    if previous_run and previous_run != run_dir:
        summary['delta_statistics']['previous_run_id'] = previous_run.name
    
    summary_path = run_dir / "run_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Update latest symlink
    dir_manager.update_latest_link(run_dir)
    
    # Clear checkpoint
    checkpoint.clear()
    
    # Final summary
    print("\n" + "="*60)
    print("SCRAPE COMPLETE")
    print("="*60)
    print(f"Duration: {(end_time - start_time).total_seconds() / 60:.1f} minutes")
    print(f"Records: {len(df_raw):,}")
    print(f"Clean records: {len(df_clean):,}")
    print(f"Success rate: {logger.get_stats()['success_rate']:.1%}")
    print(f"\nOutputs saved to: {run_dir}")
    print("="*60)


if __name__ == "__main__":
    main()
