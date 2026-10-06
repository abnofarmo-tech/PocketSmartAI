# PocketSmart AI

A budget-aware planning assistant for home decor, parties, and occasion jewelry. It provides an AI mode through Google's Gemini API and a deterministic demo mode when no API key is configured. It does not claim live retailer inventory or pricing: suggested prices are estimates, and store buttons open search pages.

## Requirements
- Windows, macOS, or Linux
- Python 3.11 or newer
- Optional: Gemini API key from Google AI Studio

## VS Code setup (Windows)
1. Open this folder in VS Code (`File > Open Folder...`).
2. In the integrated terminal, create a virtual environment and install packages:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`. Set a long random `APP_SECRET_KEY`. Set `GEMINI_API_KEY` to enable Gemini; leave it blank for demo mode. `GEMINI_MODEL` can be changed to a model available to your account.
4. Start the server with `uvicorn app.main:app --reload`.
5. Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

## Using the app
- Choose Home, Party, or Jewelry and enter a budget in INR.
- Register or sign in to save recommendation history on this computer.
- For Jewelry, an outfit photo is optional. It is processed in memory and not stored by the app. In Gemini mode, it is sent to Google's Gemini API.
- Prices are estimates. Retailer buttons open search pages; verify current prices and availability with the store.

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `APP_SECRET_KEY` | Signs session cookies | Development-only value; replace it |
| `GEMINI_API_KEY` | Enables Gemini | blank (demo mode) |
| `GEMINI_MODEL` | Gemini model | `gemini-3.8-flash` |
| `DATABASE_PATH` | SQLite file | `data/pocketsmart.db` |
| `COOKIE_SECURE` | Secure cookie flag behind HTTPS | `false` locally |

## Tests
Run `python -m unittest discover -s tests -v`. The tests use demo mode and do not require an API key or network access.

## Scope and security notes
- Live retailer integrations are not included. Prices are estimates and may differ from listings.
- Authentication uses PBKDF2 password hashes, signed HTTP-only session cookies, and SQLite. This starter project is not security-audited for production.
- Use HTTPS and set `COOKIE_SECURE=true` before exposing the service beyond localhost. Add rate limiting, account recovery, backups, privacy notices, and deployment secrets management before public launch.
- Outfit images are MIME/size checked, read in memory, and never saved. Gemini mode transmits them to Google's API under its terms.
- The PDF's Watsonx/IBM prerequisite list conflicts with its Gemini implementation path; this project uses Gemini and needs no IBM account.

