#!/usr/bin/env python3
"""
Common Email Service Module

Shared email functionality for:
- ath-booking.py (Athenaeum court booking notifications)
- smad-sheets.py (SMAD pickleball payment reminders)

Configuration via environment variables:
- GMAIL_USERNAME: Gmail address for sending
- GMAIL_APP_PASSWORD: Gmail app password (not regular password)
- NOTIFICATION_EMAIL: Recipient email (defaults to GMAIL_USERNAME)
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional, Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on actual environment variables

# Email configuration from environment variables
GMAIL_USERNAME = os.getenv('GMAIL_USERNAME', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL', '')  # Defaults to GMAIL_USERNAME if not set

# SMTP settings
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465  # SSL


def is_email_configured() -> bool:
    """Check if email is properly configured."""
    return bool(GMAIL_USERNAME and GMAIL_APP_PASSWORD)


def get_recipient_email() -> str:
    """Get the recipient email address."""
    return NOTIFICATION_EMAIL or GMAIL_USERNAME


def send_email(
    subject: str,
    body_html: str,
    recipient: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    log_func=None
) -> bool:
    """
    Send an email via Gmail SMTP.

    Args:
        subject: Email subject line
        body_html: HTML body content
        recipient: Recipient email (defaults to NOTIFICATION_EMAIL or GMAIL_USERNAME)
        attachments: List of file paths to attach (images only)
        log_func: Optional logging function (callable with message and level)

    Returns:
        True if email sent successfully, False otherwise
    """
    def log(message: str, level: str = 'INFO'):
        if log_func:
            log_func(message, level)
        else:
            print(f"[{level}] {message}")

    # Check configuration
    if not is_email_configured():
        log("Email notification skipped - GMAIL_USERNAME or GMAIL_APP_PASSWORD not configured", 'INFO')
        return False

    # Determine recipient
    to_email = recipient or get_recipient_email()
    if not to_email:
        log("Email notification skipped - no recipient email configured", 'INFO')
        return False

    try:
        log(f"Sending email to: {to_email}", 'INFO')

        # Create message
        msg = MIMEMultipart('related')
        msg['From'] = GMAIL_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject

        # Create HTML body
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        # Attach HTML content
        msg_text = MIMEText(body_html, 'html')
        msg_alternative.attach(msg_text)

        # Attach files if provided
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'rb') as f:
                            img_data = f.read()
                        image = MIMEImage(img_data, name=os.path.basename(file_path))
                        # Set Content-ID for inline display
                        filename = os.path.basename(file_path)
                        image.add_header('Content-ID', f'<{filename}>')
                        image.add_header('Content-Disposition', 'inline', filename=filename)
                        msg.attach(image)
                        log(f"  Attached: {filename}", 'INFO')
                    except Exception as e:
                        log(f"Failed to attach {file_path}: {e}", 'ERROR')

        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
            smtp_server.login(GMAIL_USERNAME, GMAIL_APP_PASSWORD)
            smtp_server.send_message(msg)

        log(f"Email sent successfully to {to_email}", 'INFO')
        return True

    except Exception as e:
        log(f"Failed to send email: {e}", 'ERROR')
        return False


def send_booking_notification(
    booking_summary: Dict[str, Any],
    booking_details: List[Dict[str, Any]],
    booking_date: str,
    screenshot_files: Optional[List[str]] = None,
    log_func=None
) -> bool:
    """
    Send Athenaeum booking notification email.

    Args:
        booking_summary: Dictionary with booking results summary
        booking_details: List of individual booking results
        booking_date: The date being booked
        screenshot_files: List of screenshot file paths to attach
        log_func: Optional logging function

    Returns:
        True if email sent successfully, False otherwise
    """
    from datetime import datetime
    import pytz

    def log(message: str, level: str = 'INFO'):
        if log_func:
            log_func(message, level)
        else:
            print(f"[{level}] {message}")

    successful_bookings = booking_summary.get('successful', 0)
    failed_bookings = booking_summary.get('failed', 0)
    total_attempts = booking_summary.get('total_attempts', 0)

    # Determine status
    if successful_bookings > 0 and failed_bookings == 0:
        status_icon = "[OK]"
        status_text = "All Bookings Successful"
        status_color = "#28a745"
    elif successful_bookings > 0 and failed_bookings > 0:
        status_icon = "[WARN]"
        status_text = "Partial Success"
        status_color = "#ffc107"
    else:
        status_icon = "[ERROR]"
        status_text = "All Bookings Failed"
        status_color = "#dc3545"

    # Format execution datetime for subject
    exec_datetime = datetime.now(pytz.timezone('America/Los_Angeles')).strftime('%m/%d/%Y %I:%M %p PST')
    email_subject = f"Athenaeum Pickleball Booking Report for {exec_datetime} - {status_text}"

    # Build HTML email body
    email_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
            .summary {{ background-color: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 5px; }}
            .booking-item {{ border-left: 4px solid #007bff; padding: 10px; margin: 10px 0; background-color: #fff; }}
            .success {{ border-left-color: #28a745; }}
            .failed {{ border-left-color: #dc3545; }}
            .error {{ border-left-color: #dc3545; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{status_icon} {status_text}</h1>
            <p>Athenaeum Court Booking Automation</p>
        </div>

        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Timestamp:</strong> {booking_summary.get('timestamp', exec_datetime)}</p>
            <p><strong>Booking Date:</strong> {booking_date}</p>
            <p><strong>Total Attempts:</strong> {total_attempts}</p>
            <p><strong>[OK] Successful:</strong> {successful_bookings}</p>
            <p><strong>[ERROR] Failed:</strong> {failed_bookings}</p>
        </div>

        <h2>Booking Details</h2>
    """

    # Add individual booking details
    for detail in booking_details:
        status_class = detail.get('status', 'error')
        if detail.get('status') == 'success':
            icon = "[OK]"
            status_label = "SUCCESS"
        elif detail.get('status') == 'failed':
            icon = "[WARN]"
            status_label = "FAILED"
        else:
            icon = "[ERROR]"
            status_label = "ERROR"

        email_body += f"""
        <div class="booking-item {status_class}">
            <p><strong>{icon} {status_label}</strong></p>
            <p><strong>Court:</strong> {detail.get('court', 'Unknown')}</p>
            <p><strong>Date:</strong> {detail.get('date', booking_date)}</p>
            <p><strong>Time:</strong> {detail.get('time', 'Unknown')}</p>
            <p><strong>Duration:</strong> {detail.get('duration', 'Unknown')} minutes</p>
        """
        if 'error' in detail:
            email_body += f"<p><strong>Error:</strong> {detail['error']}</p>"
        email_body += "</div>"

    email_body += """
        <div class="footer">
            <p>This is an automated notification from Athenaeum Court Booking Automation.</p>
            <p>Screenshots are attached for verification.</p>
        </div>
    </body>
    </html>
    """

    log("=== Sending Email Notification ===", 'INFO')
    return send_email(email_subject, email_body, attachments=screenshot_files, log_func=log_func)


def send_payment_reminder(
    player_name: str,
    balance: float,
    player_email: str,
    last_game_date: Optional[str] = None,
    hours_2026: float = 0,
    log_func=None
) -> bool:
    """
    Send SMAD payment reminder email to a player.

    Args:
        player_name: Player's full name
        balance: Amount owed
        player_email: Player's email address
        last_game_date: Date of last game played (e.g., "Sun 1/19/26")
        hours_2026: Total hours played in 2026
        log_func: Optional logging function

    Returns:
        True if email sent successfully, False otherwise
    """
    email_subject = f"SMAD Pickleball - Balance Reminder (${balance:.2f})"

    # Determine last game played text
    if hours_2026 > 0 and last_game_date:
        last_game_text = f"Your last game played was {last_game_date}."
    else:
        last_game_text = "Your last game played was in 2025."

    email_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .balance {{ font-size: 24px; color: #dc3545; font-weight: bold; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>SMAD Pickleball</h1>
            <p>Payment Reminder</p>
        </div>

        <div class="content">
            <p>Hi {player_name},</p>

            <p>This is a friendly reminder that you have an outstanding balance with SMAD Pickleball:</p>

            <p class="balance">Balance Due: ${balance:.2f}</p>

            <p>{last_game_text}</p>

            <p>Please send payment via Venmo to @gene-chuang or Zelle to genechuang@gmail.com at your earliest convenience.</p>

            <p>Thanks for playing!</p>
        </div>

        <div class="footer">
            <p>This is an automated reminder from SMAD Pickleball.</p>
            <p>San Marino Awesome Dinkers</p>
        </div>
    </body>
    </html>
    """

    return send_email(email_subject, email_body, recipient=player_email, log_func=log_func)


def send_balance_summary(
    players_with_balances: List[Dict[str, Any]],
    log_func=None
) -> bool:
    """
    Send summary of all outstanding balances to the admin.

    Args:
        players_with_balances: List of dicts with 'name' and 'balance' keys
        log_func: Optional logging function

    Returns:
        True if email sent successfully, False otherwise
    """
    from datetime import datetime

    total_owed = sum(p.get('balance', 0) for p in players_with_balances)
    date_str = datetime.now().strftime('%m/%d/%Y')

    email_subject = f"SMAD Pickleball - Outstanding Balances Summary ({date_str})"

    # Build player list HTML
    player_rows = ""
    for player in sorted(players_with_balances, key=lambda x: x.get('balance', 0), reverse=True):
        player_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{player.get('name', 'Unknown')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">${player.get('balance', 0):.2f}</td>
        </tr>
        """

    email_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background-color: #f8f9fa; padding: 10px; text-align: left; border-bottom: 2px solid #ddd; }}
            .total {{ font-size: 18px; font-weight: bold; margin-top: 20px; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>SMAD Pickleball</h1>
            <p>Outstanding Balances Summary</p>
        </div>

        <div class="content">
            <p>Date: {date_str}</p>

            <table>
                <tr>
                    <th>Player</th>
                    <th style="text-align: right;">Balance</th>
                </tr>
                {player_rows}
            </table>

            <p class="total">Total Outstanding: ${total_owed:.2f}</p>
            <p>Players with balances: {len(players_with_balances)}</p>
        </div>

        <div class="footer">
            <p>This is an automated summary from SMAD Pickleball.</p>
        </div>
    </body>
    </html>
    """

    return send_email(email_subject, email_body, log_func=log_func)
