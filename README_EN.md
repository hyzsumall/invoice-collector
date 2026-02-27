# Invoice Auto-Archiver

Automatically downloads invoice PDFs/OFDs (email attachments + web links) from your mailbox, renames them intelligently, and archives by month into a local directory.

---

## Features

- **Supported platforms**: Baiwang (baiwang.com), Nuonuo (nuonuocs.cn / nuonuo.com), Fadada (fapiao.com.cn), 51Fapiao (51fapiao.cloud), China Tax Bureau (chinatax.gov.cn), Vpiaotong (vpiaotong.com), Newtimeai (newtimeai.com), and any direct PDF/OFD links
- **Supported formats**: PDF attachments, **OFD attachments** (China national e-invoice standard GB/T 33190), and web downloads
- **Invoice categories**: Hotel / Dining / Flight & Train / Taxi / Other
- **Output naming**: `YYYYMMDD_Amount_Category.pdf` (or `.ofd`), organized into `YYYY年MM月/` subdirectories
- **Error reporting**: Prints a summary table of failed/skipped emails after each run and writes an `errors_YYYYMMDD.log` file

---

## Requirements

- Python 3.10+
- pip
- A mailbox with IMAP enabled and an app password / authorization code

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/hyzsumall/invoice-collector.git
cd invoice-collector

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install the tool (with all dependencies)
pip install -e .

# 4. Install the Playwright browser (for dynamic web invoice pages)
playwright install chromium
```

> **Tip**: You can invoke the tool without activating the venv each time:
> `~/invoice-collector/.venv/bin/agentinvoice`

---

## Configuration

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:

```yaml
email:
  provider: qq           # qq | 163 | gmail | outlook | custom
  username: "your@example.com"
  password: "your_app_password"   # App password / authorization code, NOT your login password!

filters:
  subject_keywords:
    - "发票"          # Chinese: invoice
    - "fapiao"
    - "Invoice"
    - "电子发票"      # Chinese: e-invoice
    - "receipt"
    - "invoice"
  lookback_days: 60   # Scan emails from the past 60 days

output:
  base_dir: "~/Downloads/发票归档"   # Change to any local path you prefer

playwright:
  headless: true
  timeout_ms: 30000
```

> **Security note**: `config.yaml` contains your email credentials and is listed in `.gitignore` — it will never be committed to GitHub.
>
> You can also read the password from an environment variable:
> `password: "${EMAIL_APP_PASSWORD}"`

### How to get your app password / authorization code

| Provider | Steps |
|----------|-------|
| **QQ Mail** | Settings → Account → POP3/IMAP → Enable IMAP → Generate authorization code |
| **163 Mail** | Settings → POP3/SMTP/IMAP → Enable IMAP → Set client authorization code |
| **Gmail** | Google Account → Security → Enable 2-Step Verification → App Passwords |
| **Outlook** | Microsoft Account Security → App passwords |
| **Custom** | Set `provider: custom` and provide `host` and `port` manually |

---

## Usage

```bash
# Process emails from the past 60 days (default)
agentinvoice

# Process a specific historical month
agentinvoice --month 2025-01

# Dry-run mode — preview actions without writing any files
agentinvoice --dry-run

# Use a custom config file path
agentinvoice --config ~/path/to/config.yaml

# Show verbose debug logs
agentinvoice --verbose
```

---

## Output Example

```
~/Downloads/发票归档/
├── 2025年01月/
│   ├── 20250103_350.00_飞机火车发票.pdf
│   ├── 20250110_88.50_餐饮发票.pdf
│   └── 20250115_1200.00_住宿发票.ofd
├── 2025年12月/
│   ├── 20251201_120.00_餐饮发票.pdf
│   └── 20251215_2376.00_住宿发票.pdf
└── 未归类/
    └── UNKNOWN_235.64_餐饮发票.pdf   # Has amount but no date — review manually
```

After each run, a problem-email table is printed to the console and an error log is written to:

```
~/invoice-collector/errors_20260101.log
```

---

## How It Works

1. **Connect** to your mailbox via IMAP and fetch emails matching the configured subject keywords within the lookback window.
2. **Extract attachments** — PDF first; OFD only if no PDF is present in the same email.
3. **Extract web links** — skipped if a PDF attachment already exists (PDF-first policy).
4. **Download** — tries a direct HTTP GET first (fast path), falls back to Playwright for dynamic pages that require JavaScript rendering.
5. **Parse** — extracts issue date, amount, and service name from the PDF/OFD content.
6. **Classify** — maps the service name to a category (dining, hotel, transport, etc.).
7. **Save** — writes the file to `YYYY年MM月/YYYYMMDD_Amount_Category.ext`; files missing a date go to `未归类/`.
8. **State** — processed email UIDs are saved to `state.json` so re-runs never duplicate files.

---

## FAQ

**Q: IMAP connection fails?**
A: Make sure IMAP is enabled in your mailbox settings, and that you are using an app password / authorization code rather than your account login password.

**Q: Playwright can't find the browser?**
A: Run `playwright install chromium`.

**Q: A web invoice page requires login?**
A: The tool skips login-required URLs and records them in the error log. Automatic login is not supported.

**Q: How do I open OFD files?**
A: OFD is China's national e-invoice format (GB/T 33190). To open OFD files:
- **macOS / Windows**: [Suwell OFD Reader](https://www.suwell.cn/), [Foxit PDF](https://www.foxitsoftware.cn/), or WPS Office
- **Windows**: Kingsoft Office (WPS) natively supports OFD

**Q: Will re-running download duplicates?**
A: No. Processed email UIDs are stored in `state.json`. Re-runs automatically skip already-processed emails.

**Q: What are the files in `未归类/` (Uncategorized)?**
A: The invoice file was downloaded successfully, but the PDF/OFD text layer is missing the issue date (e.g., scanned image PDFs, encrypted PDFs). The filename retains the amount and category. You can manually move these files into the correct monthly folder after reviewing.

**Q: Can I add more email providers?**
A: Yes. Set `provider: custom` in `config.yaml` and specify `host` and `port`:
```yaml
email:
  provider: custom
  host: imap.your-provider.com
  port: 993
  username: "you@example.com"
  password: "your_app_password"
```

---

## Project Structure

```
invoice-collector/
├── src/invoice_collector/
│   ├── main.py              # CLI entry point
│   ├── pipeline.py          # Main orchestration logic
│   ├── email_client.py      # IMAP client
│   ├── attachment_handler.py# PDF/OFD attachment extraction
│   ├── web_handler.py       # Web invoice download (httpx + Playwright)
│   ├── pdf_parser.py        # PDF text extraction & field parsing
│   ├── ofd_parser.py        # OFD (ZIP+XML) parsing
│   ├── classifier.py        # Invoice category classification
│   ├── file_manager.py      # File naming & saving
│   ├── state_manager.py     # Processed UID tracking
│   └── config.py            # Config loading & defaults
├── config.yaml.example      # Configuration template
├── pyproject.toml
└── README.md / README_EN.md
```

---

## License

MIT
