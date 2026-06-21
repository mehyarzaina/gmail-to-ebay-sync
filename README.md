# Gmail to eBay Sync

Automatically pulls supplier product spreadsheets from Gmail and converts them into eBay-ready listing templates — using Gemini to map mismatched column names and fill in missing prices.

## What it does

1. **Authenticates with Gmail** via OAuth and watches for unread emails from a specific sender that have `.xlsx` attachments.
2. **Downloads** those attachments and marks the emails as read.
3. **Maps supplier columns to eBay columns** automatically using Gemini — so it doesn't matter if the supplier calls it `product_name`, `title`, or `item_name`, it gets matched to the right eBay field.
4. **Fills in missing prices** by asking Gemini to suggest a realistic retail price based on the product name and description, when no price is provided.
5. **Applies a markup** (currently 1.16x) to all unit costs.
6. **Exports** a clean eBay-formatted `.xlsx` file for each supplier sheet, ready to upload.

## Project structure

```
.
├── main.py          # Entry point — runs the full pipeline
├── helper.py         # Gmail auth, download, and conversion logic
├── credentials.json   # Google OAuth client credentials (not committed)
├── token.json         # Saved Gmail auth token, generated on first run (not committed)
├── .env                # Environment variables (not committed)
├── downloads/           # Raw supplier files downloaded from Gmail
└── ebay_output/          # Converted eBay-ready templates
```

## Setup

### 1. Install dependencies

```bash
pip install pandas google-generativeai google-auth-oauthlib google-api-python-client python-dotenv openpyxl
```

### 2. Set up Gmail API access

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Gmail API**.
3. Create OAuth 2.0 credentials (Desktop app type) and download the file as `credentials.json` into the project root.
4. On first run, a browser window will open asking you to log in and grant access. This generates `token.json`, which is reused on future runs.

### 3. Configure environment variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Set the supplier email address

In `helper.py`, update:

```python
SENDER_EMAIL = 'supplier@example.com'
```

to the address you're pulling supplier files from.

## Usage

```bash
python main.py
```

The script will:
- Check for unread emails from `SENDER_EMAIL` with `.xlsx` attachments
- Download and save them to `downloads/`
- Convert each one into an eBay template saved to `ebay_output/`

If there are no new emails, it will simply print `No files to convert.` and exit.

## Configuration

| Variable | Location | Description |
|---|---|---|
| `SENDER_EMAIL` | `helper.py` | Only emails from this address are checked |
| `MARKUP` | `helper.py` | Multiplier applied to unit cost (e.g. `1.16` = 16% markup) |
| `GEMINI_API_KEY` | `.env` | API key used for column mapping and price suggestions |

## Notes

- Gemini-suggested prices are a fallback only — used when the supplier sheet has no price or a price of `0`.
- If Gemini's column mapping or price suggestion fails for any reason, the script falls back to safe defaults (e.g. `$9.99`) rather than crashing.

## .gitignore 

```
credentials.json
token.json
.env
downloads/
ebay_output/
__pycache__/
```
