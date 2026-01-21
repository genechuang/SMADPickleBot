# CLAUDE.md - AI Assistant Guide for Athenaeum Pickleball Automation

This document provides essential context for AI assistants working with this codebase.

## Project Overview

This is a **multi-feature automation platform** for:
1. **Court Booking Automation** - Automated booking of pickleball/tennis courts at The Athenaeum (Caltech's club)
2. **SMAD Player Management** - Google Sheets-based player tracking and payment management for the San Marino Awesome Dinkers pickleball group
3. **WhatsApp Integration** - Group messaging, poll creation, and vote tracking via GREEN-API

## Repository Structure

```
athpicklecourt/
├── .github/workflows/           # GitHub Actions CI/CD
│   ├── daily-booking.yml        # Scheduled court booking (11:50 PM & 12:01 AM PST)
│   └── deploy-webhook.yml       # Cloud Function deployment
├── webhook/                     # Google Cloud Function for poll webhooks
│   ├── main.py                  # Webhook handler for GREEN-API events
│   ├── requirements.txt         # Webhook dependencies
│   ├── deploy.sh                # Linux/Mac deployment script
│   └── deploy.bat               # Windows deployment script
├── ath-booking.py               # Core court booking automation (~1630 lines)
├── smad-sheets.py               # Google Sheets API integration (~1000 lines)
├── smad-whatsapp.py             # WhatsApp automation (~1488 lines)
├── email_service.py             # Shared email notification module
├── requirements.txt             # Main project dependencies
├── .env.example                 # Configuration template (copy to .env)
├── README.md                    # Main documentation
├── GITHUB_ACTION_SETUP.md       # GitHub Actions setup guide
└── SMAD_SETUP.md                # Google Sheets & Firestore setup
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Browser Automation | Playwright 1.48.0 (async, Chromium) |
| Python Runtime | Python 3.8+ (async/await) |
| Google APIs | Sheets API v4, Firestore, Cloud Functions |
| WhatsApp | GREEN-API (whatsapp-api-client-python) |
| Email | Gmail SMTP (port 465, SSL) |
| Timezone | pytz for PST/PDT handling |
| CI/CD | GitHub Actions with cron scheduling |

## Key Commands

### Court Booking (ath-booking.py)

```bash
# Booking list mode (uses BOOKING_LIST env var)
python ath-booking.py

# With invoke time (waits for BOOKING_TARGET_TIME)
python ath-booking.py --invoke-time "01-15-2026 23:55:00"

# Manual single booking
python ath-booking.py --booking-date-time "01/22/2026 7:00 PM" --court "both" --duration "120"
```

### SMAD Sheets (smad-sheets.py)

```bash
python smad-sheets.py list-players       # List all players
python smad-sheets.py show-balances      # Show payment balances
python smad-sheets.py register "Name" "Sun 1/19/26" 2   # Register hours
python smad-sheets.py add-date "Sun 1/19/26"            # Add date column
python smad-sheets.py send-reminders     # Email payment reminders
python smad-sheets.py sync-votes         # Sync Firestore votes to sheet
```

### WhatsApp (smad-whatsapp.py)

```bash
python smad-whatsapp.py create-poll             # Create poll with BOOKING_LIST dates
python smad-whatsapp.py show-votes              # Display vote summary
python smad-whatsapp.py send-vote-reminders     # DM players who haven't voted
python smad-whatsapp.py send-balance-dm "Name"  # Send individual balance reminder
python smad-whatsapp.py send-balance-summary    # Post group balance report
```

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in:

### Required for Court Booking
- `ATHENAEUM_USERNAME` / `ATHENAEUM_PASSWORD` - Login credentials
- `BOOKING_LIST` - Weekly schedule (e.g., `Tuesday 7:00 PM|Both,Friday 4:00 PM`)
- `COURT_NAME` - Default: `both`, `North Pickleball Court`, or `South Pickleball Court`
- `BOOKING_DURATION` - 60 or 120 minutes
- `BOOKING_TARGET_TIME` - When to book (default: `00:01:00` = 12:01 AM PST)

### Required for SMAD Features
- `SMAD_SPREADSHEET_ID` - Google Sheets ID
- `GOOGLE_CREDENTIALS_FILE` - Path to service account JSON
- `GREENAPI_INSTANCE_ID` / `GREENAPI_API_TOKEN` - WhatsApp API credentials
- `SMAD_WHATSAPP_GROUP_ID` - WhatsApp group ID (format: `123456789@g.us`)
- `GCP_PROJECT_ID` - For Firestore poll tracking

### Optional
- `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD` - For email notifications
- `SAFETY_MODE` - Set to `true` for dry-run (stops before final booking)
- `HEADLESS` - Set to `true` to run browser without window

## Code Patterns & Conventions

### Logging
Uses structured JSON logging to stdout/stderr (12-factor app style):
```python
log_structured("INFO", "Booking successful", court=court_name, date=date)
```

### Async Pattern
All Playwright browser automation is async:
```python
async def main():
    booking = AthenaeumBooking(username, password)
    await booking.setup()
    await booking.login()
```

### CLI Subcommands
`smad-sheets.py` and `smad-whatsapp.py` use argparse subcommands:
```python
subparsers = parser.add_subparsers(dest="command")
subparsers.add_parser("list-players", help="List all players")
```

### Google APIs
Service account authentication with scoped access:
```python
credentials = service_account.Credentials.from_service_account_file(
    credentials_file, scopes=SCOPES
)
service = build('sheets', 'v4', credentials=credentials)
```

### Error Handling
- Email notifications skip silently if not configured
- Graceful fallbacks for missing services
- Screenshots saved at each step for debugging

### Naming Conventions
- `snake_case` for functions and variables
- `UPPERCASE` for environment variables and constants
- Column indices prefixed with `COL_` (e.g., `COL_FIRST_NAME`)
- Command functions prefixed with `cmd_` (e.g., `cmd_create_poll`)

## Important Business Logic

### Court Booking Timing
- Courts become available 7 days in advance at midnight PST
- GitHub Actions runs at 11:50 PM PST (primary) and 12:01 AM PST (backup)
- Script waits until `BOOKING_TARGET_TIME` before attempting to book
- 10-minute grace period handles GitHub Actions delays

### BOOKING_LIST Format
```
DayName HH:MM AM/PM|Court
```
Examples:
- `Tuesday 7:00 PM|Both` - Both courts on Tuesday at 7 PM
- `Friday 4:00 PM` - Uses default COURT_NAME
- `Sunday 10:00 AM|North Pickleball Court` - Specific court

### Poll Vote Tracking
1. GREEN-API sends webhook to Cloud Function when votes occur
2. Cloud Function updates Firestore with vote data
3. `sync-votes` command syncs Firestore to Google Sheet
4. "Cannot play" votes override any previous date selections

## External Integrations

| Service | Purpose | Auth Method |
|---------|---------|-------------|
| Athenaeum Portal | Court reservations | Username/password |
| Google Sheets | Player data & balances | Service account |
| Firestore | Poll vote storage | Service account |
| GREEN-API | WhatsApp messaging | Instance ID + API token |
| Gmail SMTP | Email notifications | App password |

## Testing & Development

### Safety Mode
Set `SAFETY_MODE=true` to stop before final booking submission - useful for testing the flow without making actual reservations.

### Headless Mode
Set `HEADLESS=false` to see the browser during execution for debugging.

### Screenshots
Screenshots are saved at each step:
- `before_login.png`, `after_login.png`
- `booking_01_initial.png` through `booking_06_confirmation.png`

## Known Limitations

1. **DST Transitions** - Cron schedules need manual updates twice yearly (PST/PDT)
2. **Website Changes** - Script breaks if Athenaeum portal structure changes
3. **Telerik Controls** - Duration selection depends on specific RadComboBox API
4. **Firestore Free Tier** - 50K reads/day, 20K writes/day (usually sufficient)

## Git Workflow

- Main development happens on feature branches
- Commits should have clear, descriptive messages
- Never commit `.env` or credential files (they're in `.gitignore`)
- GitHub Actions handles automated deployments

## Quick Reference: Environment Variables

| Variable | Required For | Example |
|----------|--------------|---------|
| `ATHENAEUM_USERNAME` | Booking | `john.doe` |
| `ATHENAEUM_PASSWORD` | Booking | `secret123` |
| `BOOKING_LIST` | Booking | `Tuesday 7:00 PM\|Both` |
| `SMAD_SPREADSHEET_ID` | Sheets | `1w4_-hnykYgcs...` |
| `GOOGLE_CREDENTIALS_FILE` | Sheets/Firestore | `smad-credentials.json` |
| `GREENAPI_INSTANCE_ID` | WhatsApp | `1234567890` |
| `GREENAPI_API_TOKEN` | WhatsApp | `abc123...` |
| `SMAD_WHATSAPP_GROUP_ID` | WhatsApp | `123456@g.us` |
| `GCP_PROJECT_ID` | Firestore | `my-project-id` |
| `GMAIL_USERNAME` | Email | `user@gmail.com` |
| `GMAIL_APP_PASSWORD` | Email | `abcd efgh ijkl mnop` |

## Files to Never Commit

- `.env` (contains secrets)
- `smad-credentials.json` (service account key)
- Any `*-credentials.json` files
- Screenshots (optional, but can contain sensitive data)
