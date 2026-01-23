"""
Venmo Payment Email Trigger Cloud Function

Triggered when Venmo payment emails are forwarded from Gmail.
Runs venmo-sync to automatically update the Payment Log sheet.

Deployment:
    gcloud functions deploy venmo-sync-trigger \
      --gen2 \
      --runtime=python311 \
      --region=us-west1 \
      --source=. \
      --entry-point=venmo_email_trigger \
      --trigger-http \
      --allow-unauthenticated \
      --set-env-vars SMAD_SPREADSHEET_ID=<spreadsheet_id> \
      --set-secrets VENMO_ACCESS_TOKEN=VENMO_ACCESS_TOKEN:latest,SMAD_GOOGLE_CREDENTIALS_JSON=SMAD_GOOGLE_CREDENTIALS_JSON:latest

Environment Variables:
    SMAD_SPREADSHEET_ID: Google Sheets spreadsheet ID
    VENMO_ACCESS_TOKEN: Venmo API access token (from Secret Manager)
    SMAD_GOOGLE_CREDENTIALS_JSON: Google service account JSON (from Secret Manager)
    SMAD_SHEET_NAME: (optional) Main sheet name (default: 2026 Pickleball)
    PAYMENT_LOG_SHEET_NAME: (optional) Payment log sheet name (default: Payment Log)
"""

import os
import sys
import json
import functions_framework
from flask import Request

# Add parent directory to path for shared module access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.venmo_sync import sync_venmo_to_sheet


@functions_framework.http
def venmo_email_trigger(request: Request):
    """
    HTTP Cloud Function triggered by forwarded Venmo payment emails.

    The email content is not parsed - this just triggers a venmo-sync.
    The actual payment matching is done via Venmo API by username.

    Args:
        request: Flask Request object (email content)

    Returns:
        JSON response with sync results
    """
    print("[INFO] Venmo payment email received, triggering sync...")

    # Get configuration from environment
    venmo_token = os.environ.get('VENMO_ACCESS_TOKEN')
    spreadsheet_id = os.environ.get('SMAD_SPREADSHEET_ID')
    google_creds_json = os.environ.get('SMAD_GOOGLE_CREDENTIALS_JSON')
    main_sheet = os.environ.get('SMAD_SHEET_NAME', '2026 Pickleball')
    payment_log_sheet = os.environ.get('PAYMENT_LOG_SHEET_NAME', 'Payment Log')

    # Validate required configuration
    if not venmo_token:
        error_msg = "VENMO_ACCESS_TOKEN not configured"
        print(f"[ERROR] {error_msg}")
        return {"status": "error", "message": error_msg}, 500

    if not spreadsheet_id:
        error_msg = "SMAD_SPREADSHEET_ID not configured"
        print(f"[ERROR] {error_msg}")
        return {"status": "error", "message": error_msg}, 500

    if not google_creds_json:
        error_msg = "SMAD_GOOGLE_CREDENTIALS_JSON not configured"
        print(f"[ERROR] {error_msg}")
        return {"status": "error", "message": error_msg}, 500

    # Optional: Log email metadata (for debugging)
    # Don't parse the email content - just trigger sync
    try:
        # Get request headers to verify it's from Gmail (optional security)
        from_address = request.headers.get('From', '')
        subject = request.headers.get('Subject', '')

        if from_address:
            print(f"[INFO] Email from: {from_address}")
        if subject:
            print(f"[INFO] Subject: {subject}")

        # Optional: Basic validation to ensure it's a Venmo payment email
        # (Can be disabled if you trust the Gmail filter)
        # if 'venmo' not in from_address.lower():
        #     print("[WARN] Email not from Venmo, but proceeding anyway")

    except Exception as e:
        print(f"[WARN] Could not parse email headers: {e}")

    # Run venmo-sync
    try:
        recorded, skipped, unmatched = sync_venmo_to_sheet(
            venmo_access_token=venmo_token,
            spreadsheet_id=spreadsheet_id,
            google_credentials=google_creds_json,
            main_sheet_name=main_sheet,
            payment_log_sheet_name=payment_log_sheet,
            limit=50,  # Check last 50 transactions
            dry_run=False
        )

        print(f"[SUCCESS] Sync completed: {recorded} recorded, {skipped} skipped, {unmatched} unmatched")

        return {
            "status": "success",
            "recorded": recorded,
            "skipped": skipped,
            "unmatched": unmatched,
            "message": f"Venmo sync completed successfully"
        }, 200

    except Exception as e:
        error_msg = f"Sync failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        import traceback
        traceback.print_exc()

        return {
            "status": "error",
            "message": error_msg
        }, 500
