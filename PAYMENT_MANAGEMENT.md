# Payment Management

Track SMAD group payments with Venmo API integration and Google Sheets.

## Overview

The payment management system provides:
- **Automatic Venmo sync**: Real-time payment detection via Gmail Watch + Cloud Functions
- **Manual Venmo sync**: CLI tool for on-demand payment syncing
- **Payment recording**: Manual payment entry with audit trail
- **Balance tracking**: Automatic balance calculations in Google Sheets

## Quick Start

```bash
# Record a manual payment
python payments-management.py record "John Doe" 50.00 --method venmo

# Set up Venmo API access (one-time, requires 2FA)
python payments-management.py setup-venmo

# Sync payments from Venmo
python payments-management.py sync-venmo

# List recent payments
python payments-management.py list --days 30

# Show payment history for a player
python payments-management.py history "John Doe"
```

## Venmo Integration

The system uses the unofficial `venmo-api` library to fetch transactions:
- Matches payments by Venmo username (@handle) to the Venmo column in the main sheet
- Automatically skips already-recorded transactions (by transaction ID)
- Updates `Last Paid` date in the main sheet when payments are recorded

### Setup

1. Install: `pip install venmo-api`
2. Run: `python payments-management.py setup-venmo`
3. Complete 2FA verification
4. Add the token to `.env`: `VENMO_ACCESS_TOKEN=your_token`

## Payment Log Sheet

Payments are logged to a "Payment Log" sheet with columns:
| Column | Description |
|--------|-------------|
| Date | Payment date |
| Player Name | Full name from main sheet |
| Amount | Payment amount |
| Method | venmo, zelle, cash, check |
| Transaction ID | Venmo transaction ID (for deduplication) |
| Notes | Optional notes |
| Recorded By | "auto" for webhook, "manual" for CLI |
| Recorded At | Timestamp when recorded |

## Automatic Payment Sync

The system supports real-time payment detection:

1. **Gmail Watch** monitors inbox for Venmo payment emails
2. **Pub/Sub** delivers notifications to Cloud Function
3. **Cloud Function** triggers venmo-sync module
4. **Venmo API** fetches recent transactions
5. **Google Sheets** records payment with deduplication
6. **WhatsApp DM** sends thank-you message with updated balance

See [Gmail Watch Setup](GMAIL_WATCH_SETUP.md) and [Venmo Email Sync Setup](VENMO_EMAIL_SYNC_SETUP.md) for configuration.

## Manual Commands

### sync-venmo
Fetches recent Venmo transactions and records matching payments.

```bash
python payments-management.py sync-venmo
```

Options:
- `--days N`: Look back N days (default: 7)
- `--dry-run`: Show what would be recorded without saving

### record
Manually record a payment.

```bash
python payments-management.py record "John Doe" 50.00 --method venmo --notes "For January sessions"
```

Arguments:
- `player_name`: Player's full name (must match sheet)
- `amount`: Payment amount
- `--method`: Payment method (venmo, zelle, cash, check)
- `--notes`: Optional notes

### list
List recent payments from the Payment Log.

```bash
python payments-management.py list --days 30
```

Options:
- `--days N`: Show payments from last N days (default: 30)
- `--player NAME`: Filter by player name

### history
Show payment history for a specific player.

```bash
python payments-management.py history "John Doe"
```

## Environment Variables

```env
# Venmo API (get token via setup-venmo command)
VENMO_ACCESS_TOKEN=your_venmo_api_token

# Google Sheets
SMAD_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_CREDENTIALS_PATH=path/to/smad-credentials.json
```

## Related Documentation

- [SMAD Google Sheets Setup](SMAD_SETUP.md) - Sheet structure and player data
- [Venmo Email Sync Setup](VENMO_EMAIL_SYNC_SETUP.md) - Real-time payment sync
- [Gmail Watch Setup](GMAIL_WATCH_SETUP.md) - Email notification setup
- [WhatsApp Webhook Setup](webhook/README.md) - Cloud Function configuration
