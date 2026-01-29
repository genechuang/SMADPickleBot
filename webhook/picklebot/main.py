"""
SMAD Picklebot - WhatsApp Chatbot Cloud Function

Receives commands from Admin Dinkers WhatsApp group via GREEN-API webhook.
Uses Claude Haiku for natural language intent parsing.

Commands:
    /pb help - Show available commands
    /pb deadbeats - Show players with outstanding balances
    /pb balance [name] - Show balances
    /pb book <date> <time> [duration] - Book court (requires confirmation)
    /pb poll create - Create weekly poll (requires confirmation)
    /pb reminders - Send vote reminders (requires confirmation)
    /pb status - Show system status

Deployment:
    gcloud functions deploy smad-picklebot \
        --runtime=python311 \
        --trigger-http \
        --allow-unauthenticated \
        --entry-point=picklebot_webhook
"""

import os
import json
import logging
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional

import functions_framework
import pytz
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PST timezone
PST = pytz.timezone('America/Los_Angeles')

# Environment variables
GREENAPI_INSTANCE_ID = os.environ.get('GREENAPI_INSTANCE_ID', '')
GREENAPI_API_TOKEN = os.environ.get('GREENAPI_API_TOKEN', '')
ADMIN_DINKERS_GROUP_ID = os.environ.get('ADMIN_DINKERS_WHATSAPP_GROUP_ID', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'genechuang/SMADPickleBot')
PICKLEBOT_CONFIRM_URL = os.environ.get('PICKLEBOT_CONFIRM_URL', '')

# Google Sheets config (reuse from smad-whatsapp.py)
SPREADSHEET_ID = os.environ.get('SMAD_SPREADSHEET_ID', '1w4_-hnykYgcs6nyyDkie9CwBRwri7aJUblD2mxgNUHY')
SHEET_NAME = os.environ.get('SMAD_SHEET_NAME', '2026 Pickleball')

# GCS bucket for pending actions
GCS_BUCKET_NAME = 'smad-pickleball-screenshots'
GCS_PROJECT_ID = 'smad-pickleball'

# Bot signature
PICKLEBOT_SIGNATURE = "SMAD Picklebot"

# Column indices for player data
COL_FIRST_NAME = 0
COL_LAST_NAME = 1
COL_BALANCE = 7

# Command prefixes
COMMAND_PREFIXES = ['/pb ', '/picklebot ']

# Dry run flags that can appear in command text
DRY_RUN_FLAGS = ['--dry-run', '--dry', '-n', 'dry run', 'dryrun']


def extract_dry_run_flag(command_text: str) -> tuple[str, bool]:
    """
    Check if command contains a dry run flag and remove it from the command.

    Returns:
        tuple: (cleaned_command, is_dry_run)
    """
    text_lower = command_text.lower()

    for flag in DRY_RUN_FLAGS:
        if flag in text_lower:
            # Remove the flag from command (case-insensitive)
            import re
            pattern = re.compile(re.escape(flag), re.IGNORECASE)
            cleaned = pattern.sub('', command_text).strip()
            # Clean up any double spaces
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned, True

    return command_text, False


def send_whatsapp_message(chat_id: str, message: str, dry_run: bool = False) -> bool:
    """Send a WhatsApp message via GREEN-API.

    Args:
        chat_id: The WhatsApp chat ID to send to
        message: The message content
        dry_run: If True, skip sending and just log

    Returns:
        True if sent (or would be sent in dry run), False on error
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would send to {chat_id}: {message[:100]}...")
        return True

    if not GREENAPI_INSTANCE_ID or not GREENAPI_API_TOKEN:
        logger.error("GREEN-API credentials not configured")
        return False

    url = f"https://api.green-api.com/waInstance{GREENAPI_INSTANCE_ID}/sendMessage/{GREENAPI_API_TOKEN}"

    try:
        response = requests.post(url, json={
            'chatId': chat_id,
            'message': message
        }, timeout=30)

        if response.status_code == 200:
            logger.info(f"Message sent to {chat_id}")
            return True
        else:
            logger.error(f"Failed to send message: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


def parse_intent_with_claude(command_text: str) -> dict:
    """Use Claude Haiku to parse natural language command."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set, using fallback parsing")
        return parse_intent_fallback(command_text)

    prompt = f"""Parse this SMAD Picklebot command and extract the intent and parameters.

Command: {command_text}

Available intents:
- help: Show available commands (no params)
- show_deadbeats: Show players with outstanding balances (no params)
- show_balances: Show all balances or specific player (optional: player_name)
- book_court: Book a court (params: date, time, duration_minutes, court - north/south/both)
- create_poll: Create weekly availability poll (no params)
- send_reminders: Send reminders (params: type - vote/payment)
- show_status: Show system status (no params)

For book_court:
- Parse dates like "2/4", "Feb 4", "tomorrow", "next Tuesday"
- Parse times like "7pm", "7:00 PM", "19:00"
- Parse durations like "2 hours", "2hrs", "120 minutes" (default: 120 minutes)
- Parse courts like "north", "south", "both" (default: both)

Return ONLY valid JSON (no markdown, no explanation):
{{"intent": "...", "params": {{}}, "confirmation_required": true/false}}

Set confirmation_required=true for: book_court, create_poll, send_reminders
Set confirmation_required=false for: help, show_deadbeats, show_balances, show_status"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 256,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            content = result.get('content', [{}])[0].get('text', '{}')
            # Clean up any markdown formatting
            content = content.strip()
            if content.startswith('```'):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            return json.loads(content)
        else:
            logger.error(f"Claude API error: {response.status_code} - {response.text}")
            return parse_intent_fallback(command_text)

    except Exception as e:
        logger.error(f"Error parsing intent with Claude: {e}")
        return parse_intent_fallback(command_text)


def parse_intent_fallback(command_text: str) -> dict:
    """Simple regex-based intent parsing as fallback."""
    text = command_text.lower().strip()

    # Remove command prefix
    for prefix in COMMAND_PREFIXES:
        if text.startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            break

    if text in ['help', '?', 'commands']:
        return {"intent": "help", "params": {}, "confirmation_required": False}

    if text in ['deadbeats', 'deadbeat', 'owes', 'outstanding']:
        return {"intent": "show_deadbeats", "params": {}, "confirmation_required": False}

    if text.startswith('balance'):
        name = text.replace('balance', '').strip()
        return {"intent": "show_balances", "params": {"player_name": name} if name else {}, "confirmation_required": False}

    if text.startswith('book'):
        # Basic parsing: book 2/4 7pm 2hrs
        return {"intent": "book_court", "params": {"raw": text}, "confirmation_required": True}

    if 'poll' in text and 'create' in text:
        return {"intent": "create_poll", "params": {}, "confirmation_required": True}

    if 'reminder' in text:
        return {"intent": "send_reminders", "params": {"type": "vote"}, "confirmation_required": True}

    if text in ['status', 'health']:
        return {"intent": "show_status", "params": {}, "confirmation_required": False}

    return {"intent": "unknown", "params": {"raw": text}, "confirmation_required": False}


def get_sheets_service():
    """Initialize Google Sheets API service."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        # Try SMAD-specific credentials first, then fall back to generic
        creds_env = os.environ.get('SMAD_GOOGLE_CREDENTIALS_JSON') or os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_env:
            creds_json = json.loads(creds_env)
            creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        else:
            from google.auth import default
            creds, _ = default(scopes=SCOPES)

        service = build('sheets', 'v4', credentials=creds)
        return service.spreadsheets()
    except Exception as e:
        logger.error(f"Failed to initialize Sheets service: {e}")
        return None


def get_player_balances() -> list:
    """Get all player balances from Google Sheets."""
    sheets = get_sheets_service()
    if not sheets:
        return []

    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{SHEET_NAME}'"
        ).execute()
        data = result.get('values', [])

        players = []
        for row in data[1:]:  # Skip header
            if len(row) > COL_BALANCE:
                first_name = row[COL_FIRST_NAME] if len(row) > COL_FIRST_NAME else ""
                last_name = row[COL_LAST_NAME] if len(row) > COL_LAST_NAME else ""

                if not first_name:
                    continue

                balance_str = row[COL_BALANCE] if len(row) > COL_BALANCE else "0"
                try:
                    balance = float(balance_str.replace('$', '').replace(',', '').strip() or '0')
                except ValueError:
                    balance = 0

                players.append({
                    'name': f"{first_name} {last_name}".strip(),
                    'balance': balance
                })

        return players

    except Exception as e:
        logger.error(f"Failed to get player balances: {e}")
        return []


# Command handlers
def handle_help() -> str:
    """Return help message with available commands."""
    return f"""*{PICKLEBOT_SIGNATURE} Commands*

*Read-only:*
/pb help - Show this message
/pb deadbeats - Show players with outstanding balances
/pb balance [name] - Show all balances or specific player
/pb status - Show system status

*Actions (require confirmation):*
/pb book <date> <time> [duration] - Book court
  Example: /pb book 2/4 7pm 2hrs both courts
/pb poll create - Create weekly availability poll
/pb reminders - Send vote reminders

*Options:*
--dry-run - Test command without sending messages
  Example: /pb deadbeats --dry-run

Tip: You can use natural language!
  "/pb book next Tuesday at 7pm for 2 hours"
  "/pb who owes money?"
"""


def handle_deadbeats() -> str:
    """Return list of players with outstanding balances."""
    players = get_player_balances()
    deadbeats = [p for p in players if p['balance'] > 0]

    if not deadbeats:
        return f"*{PICKLEBOT_SIGNATURE}*\n\nNo outstanding balances! Everyone is paid up."

    # Sort by balance descending
    deadbeats.sort(key=lambda x: x['balance'], reverse=True)
    total = sum(p['balance'] for p in deadbeats)

    message = f"*{PICKLEBOT_SIGNATURE} - Outstanding Balances*\n\n"
    for p in deadbeats:
        message += f"- {p['name']}: ${p['balance']:.2f}\n"
    message += f"\n*Total: ${total:.2f}*"

    return message


def handle_balances(player_name: str = None) -> str:
    """Return all balances or specific player balance."""
    players = get_player_balances()

    if player_name:
        # Search for specific player
        player_name_lower = player_name.lower()
        matches = [p for p in players if player_name_lower in p['name'].lower()]

        if not matches:
            return f"*{PICKLEBOT_SIGNATURE}*\n\nPlayer '{player_name}' not found."

        if len(matches) == 1:
            p = matches[0]
            status = "owes" if p['balance'] > 0 else "has credit of" if p['balance'] < 0 else "is all paid up"
            if p['balance'] == 0:
                return f"*{PICKLEBOT_SIGNATURE}*\n\n{p['name']} {status}!"
            return f"*{PICKLEBOT_SIGNATURE}*\n\n{p['name']} {status} ${abs(p['balance']):.2f}"

        # Multiple matches
        message = f"*{PICKLEBOT_SIGNATURE}*\n\nMultiple matches for '{player_name}':\n"
        for p in matches:
            message += f"- {p['name']}: ${p['balance']:.2f}\n"
        return message

    # All players
    players.sort(key=lambda x: x['balance'], reverse=True)
    total = sum(p['balance'] for p in players if p['balance'] > 0)

    message = f"*{PICKLEBOT_SIGNATURE} - All Balances*\n\n"
    for p in players:
        if p['balance'] != 0:
            message += f"- {p['name']}: ${p['balance']:.2f}\n"
    message += f"\n*Total Outstanding: ${total:.2f}*"

    return message


def handle_status() -> str:
    """Return system status."""
    now = datetime.now(PST)
    timestamp = now.strftime('%m/%d/%y %I:%M %p PST')

    status = f"""*{PICKLEBOT_SIGNATURE} Status*

Time: {timestamp}
Webhook: Online
GREEN-API: {'Connected' if GREENAPI_INSTANCE_ID else 'Not configured'}
Claude API: {'Connected' if ANTHROPIC_API_KEY else 'Not configured'}
GitHub: {'Connected' if GITHUB_TOKEN else 'Not configured'}
Sheets: {'Connected' if SPREADSHEET_ID else 'Not configured'}
"""
    return status


def handle_unknown(raw_text: str) -> str:
    """Handle unknown commands."""
    return f"""*{PICKLEBOT_SIGNATURE}*

I didn't understand: "{raw_text}"

Type /pb help to see available commands."""


def handle_book_court_preview(params: dict) -> str:
    """Generate preview message for court booking (confirmation required)."""
    # Extract parameters
    date = params.get('date', 'unknown')
    time = params.get('time', 'unknown')
    duration = params.get('duration_minutes', 120)
    court = params.get('court', 'both')

    # TODO: Generate confirmation link
    return f"""*{PICKLEBOT_SIGNATURE} - Book Court*

This action requires confirmation.

*Details:*
- Date: {date}
- Time: {time}
- Duration: {duration} minutes
- Court: {court}

_Confirmation links coming in Phase 2_"""


def handle_create_poll_preview() -> str:
    """Generate preview message for poll creation (confirmation required)."""
    return f"""*{PICKLEBOT_SIGNATURE} - Create Poll*

This action requires confirmation.

Will create a weekly availability poll in the SMAD group.

_Confirmation links coming in Phase 2_"""


def handle_send_reminders_preview(reminder_type: str) -> str:
    """Generate preview message for sending reminders (confirmation required)."""
    return f"""*{PICKLEBOT_SIGNATURE} - Send Reminders*

This action requires confirmation.

Will send {reminder_type} reminders to players who haven't responded.

_Confirmation links coming in Phase 2_"""


def process_command(command_text: str, sender_data: dict, dry_run: bool = False) -> dict:
    """Process a picklebot command and return response.

    Args:
        command_text: The command text (with or without dry run flag)
        sender_data: Sender info from webhook
        dry_run: If True, don't execute actions (external override)

    Returns:
        dict with message, intent, and dry_run status
    """
    # Check for dry run flag in command text
    cleaned_command, text_has_dry_run = extract_dry_run_flag(command_text)
    is_dry_run = dry_run or text_has_dry_run

    if is_dry_run:
        logger.info(f"[DRY RUN] Processing command: {cleaned_command}")
    else:
        logger.info(f"Processing command: {cleaned_command}")

    # Parse intent from cleaned command
    intent_data = parse_intent_with_claude(cleaned_command)
    intent = intent_data.get('intent', 'unknown')
    params = intent_data.get('params', {})
    needs_confirmation = intent_data.get('confirmation_required', False)

    logger.info(f"Parsed intent: {intent}, params: {params}, needs_confirmation: {needs_confirmation}")

    # Build base result with dry_run status
    def build_result(message: str, **kwargs) -> dict:
        result = {'message': message, 'dry_run': is_dry_run}
        if is_dry_run:
            result['message'] = f"[DRY RUN]\n\n{message}"
        result.update(kwargs)
        return result

    # Handle read-only commands directly
    if intent == 'help':
        return build_result(handle_help(), intent=intent)

    if intent == 'show_deadbeats':
        return build_result(handle_deadbeats(), intent=intent)

    if intent == 'show_balances':
        return build_result(handle_balances(params.get('player_name')), intent=intent)

    if intent == 'show_status':
        return build_result(handle_status(), intent=intent)

    # Handle destructive commands (show preview, require confirmation)
    if intent == 'book_court':
        return build_result(handle_book_court_preview(params), intent=intent, needs_confirmation=True)

    if intent == 'create_poll':
        return build_result(handle_create_poll_preview(), intent=intent, needs_confirmation=True)

    if intent == 'send_reminders':
        return build_result(handle_send_reminders_preview(params.get('type', 'vote')), intent=intent, needs_confirmation=True)

    # Unknown command
    return build_result(handle_unknown(params.get('raw', cleaned_command)), intent='unknown')


@functions_framework.http
def picklebot_webhook(request):
    """
    HTTP Cloud Function entry point for picklebot commands.

    This can be called directly or routed from the main smad-whatsapp-webhook.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    if request.method != 'POST':
        return {'error': 'Method not allowed'}, 405

    try:
        data = request.get_json(silent=True)
        if not data:
            return {'error': 'No JSON payload'}, 400

        # Check for dry_run parameter in request
        dry_run = data.get('dry_run', False)

        # Check if this is a direct command (from routing) or a webhook payload
        if 'command' in data:
            # Direct routing from smad-whatsapp-webhook
            command_text = data['command']
            chat_id = data.get('chatId', ADMIN_DINKERS_GROUP_ID)
            sender_data = {
                'chatId': chat_id,
                'sender': data.get('sender', ''),
                'senderName': data.get('senderName', '')
            }
        else:
            # Full GREEN-API webhook payload
            sender_data = data.get('senderData', {})
            message_data = data.get('messageData', {})
            chat_id = sender_data.get('chatId', '')

            # Only process from Admin Dinkers group
            if ADMIN_DINKERS_GROUP_ID and chat_id != ADMIN_DINKERS_GROUP_ID:
                return {'status': 'ignored', 'reason': 'not_admin_group'}, 200

            # Extract text message
            type_message = message_data.get('typeMessage', '')
            if type_message != 'textMessage':
                return {'status': 'ignored', 'reason': 'not_text_message'}, 200

            text = message_data.get('textMessageData', {}).get('textMessage', '')

            # Check for command prefix
            is_command = False
            for prefix in COMMAND_PREFIXES:
                if text.lower().startswith(prefix.lower()):
                    is_command = True
                    break

            if not is_command:
                return {'status': 'ignored', 'reason': 'not_command'}, 200

            command_text = text

        # Process the command
        result = process_command(command_text, sender_data, dry_run=dry_run)

        # Get effective dry_run status (could be from param or command text)
        is_dry_run = result.get('dry_run', dry_run)

        # Send response to group (skipped in dry run mode)
        if result.get('message'):
            send_whatsapp_message(chat_id or ADMIN_DINKERS_GROUP_ID, result['message'], dry_run=is_dry_run)

        return {
            'status': 'processed',
            'intent': result.get('intent'),
            'needs_confirmation': result.get('needs_confirmation', False),
            'dry_run': is_dry_run,
            'response_message': result.get('message') if is_dry_run else None
        }, 200

    except Exception as e:
        logger.error(f"Picklebot error: {e}", exc_info=True)
        return {'error': str(e)}, 500


# For local testing
if __name__ == '__main__':
    # Test intent parsing
    test_commands = [
        "/pb help",
        "/pb deadbeats",
        "/pb balance John",
        "/pb book 2/4 7pm 2hrs",
        "/pb poll create",
        "/pb status",
    ]

    for cmd in test_commands:
        print(f"\nCommand: {cmd}")
        result = parse_intent_fallback(cmd)
        print(f"Result: {json.dumps(result, indent=2)}")
