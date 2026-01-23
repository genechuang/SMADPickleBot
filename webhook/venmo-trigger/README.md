# Venmo Payment Email Trigger - Cloud Function

This Cloud Function automatically syncs Venmo payments to the Payment Log sheet when triggered by forwarded Venmo payment emails.

## Architecture

```
Venmo Payment → Gmail → Email Forward → Cloud Function → venmo-api → Payment Log
                        (trigger only)   (sync logic)    (username   (Google Sheets)
                                                          matching)
```

**Key Benefits:**
- ✅ Real-time payment sync (seconds after payment)
- ✅ Reliable username matching (no name parsing fragility)
- ✅ Handles duplicate names (matches by @venmo-username)
- ✅ Automatic deduplication (checks transaction IDs)
- ✅ Zero cost (Cloud Functions free tier)

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Secret Manager** secrets:
   - `VENMO_ACCESS_TOKEN` - Venmo API access token
   - `SMAD_GOOGLE_CREDENTIALS_JSON` - Service account JSON
3. **Gmail account** - For receiving/forwarding Venmo emails

## Setup Instructions

### Step 1: Configure Secrets in Google Cloud

```bash
# Set your Google Cloud project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  cloudfunctions.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

# Create Venmo access token secret
echo -n "YOUR_VENMO_ACCESS_TOKEN" | \
  gcloud secrets create VENMO_ACCESS_TOKEN \
  --data-file=- \
  --replication-policy="automatic"

# Create Google credentials secret
gcloud secrets create SMAD_GOOGLE_CREDENTIALS_JSON \
  --data-file=smad-credentials.json \
  --replication-policy="automatic"

# Grant Cloud Function access to secrets
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding VENMO_ACCESS_TOKEN \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding SMAD_GOOGLE_CREDENTIALS_JSON \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 2: Deploy Cloud Function

```bash
cd webhook/venmo-trigger

gcloud functions deploy venmo-sync-trigger \
  --gen2 \
  --runtime=python311 \
  --region=us-west1 \
  --source=. \
  --entry-point=venmo_email_trigger \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars SMAD_SPREADSHEET_ID=1w4_-hnykYgcs6nyyDkie9CwBRwri7aJUblD2mxgNUHY \
  --set-secrets VENMO_ACCESS_TOKEN=VENMO_ACCESS_TOKEN:latest,SMAD_GOOGLE_CREDENTIALS_JSON=SMAD_GOOGLE_CREDENTIALS_JSON:latest \
  --max-instances=3 \
  --timeout=120s \
  --memory=256Mi
```

After deployment, note the **trigger URL** (something like `https://us-west1-PROJECT_ID.cloudfunctions.net/venmo-sync-trigger`).

### Step 3: Configure Gmail Forwarding

1. **Get the Cloud Function email address**:
   ```bash
   # The Cloud Function accepts emails at any address, but Gmail needs to verify
   # Use a real email for verification, or use Gmail's direct forwarding
   ```

2. **Set up Gmail filter** (Method 1: Direct Forwarding):
   - Go to Gmail Settings → Forwarding and POP/IMAP
   - Add forwarding address: Send a test email to the Cloud Function URL using a service like **Zapier Email Parser** or **Mailgun Routes**
   - Verify the address

3. **Set up Gmail filter** (Method 2: Gmail Script - Recommended):
   Create a Gmail Apps Script that forwards to Cloud Function:

   ```javascript
   function forwardVenmoToCloudFunction() {
     var searchQuery = 'from:venmo@venmo.com subject:"paid you"';
     var threads = GmailApp.search(searchQuery, 0, 10);

     threads.forEach(function(thread) {
       var messages = thread.getMessages();
       messages.forEach(function(message) {
         if (!message.isStarred()) {  // Only process unprocessed emails
           // Forward to Cloud Function
           UrlFetchApp.fetch('https://YOUR-CLOUD-FUNCTION-URL', {
             method: 'post',
             contentType: 'application/json',
             payload: JSON.stringify({
               from: message.getFrom(),
               subject: message.getSubject(),
               date: message.getDate(),
               body: message.getPlainBody()
             })
           });

           // Mark as processed
           message.star();
         }
       });
     });
   }
   ```

   Set the script to run every 5 minutes via Triggers.

4. **Alternative: Use n8n or Zapier** (Easiest):
   - Connect Gmail to n8n/Zapier
   - Filter: From `venmo@venmo.com`, Subject contains `paid you`
   - Action: HTTP POST to Cloud Function URL

### Step 4: Test the Function

```bash
# Manual test - trigger sync directly
curl -X POST https://YOUR-CLOUD-FUNCTION-URL \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Check logs
gcloud functions logs read venmo-sync-trigger --gen2 --region=us-west1 --limit=50

# Or via Console
open https://console.cloud.google.com/functions/details/us-west1/venmo-sync-trigger?project=$PROJECT_ID
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VENMO_ACCESS_TOKEN` | Yes | - | Venmo API access token (from Secret Manager) |
| `SMAD_GOOGLE_CREDENTIALS_JSON` | Yes | - | Google service account JSON (from Secret Manager) |
| `SMAD_SPREADSHEET_ID` | Yes | - | Google Sheets spreadsheet ID |
| `SMAD_SHEET_NAME` | No | `2026 Pickleball` | Main sheet name |
| `PAYMENT_LOG_SHEET_NAME` | No | `Payment Log` | Payment log sheet name |

## Monitoring & Debugging

### View Logs

```bash
# Recent logs
gcloud functions logs read venmo-sync-trigger --gen2 --region=us-west1 --limit=50

# Follow logs in real-time
gcloud functions logs tail venmo-sync-trigger --gen2 --region=us-west1

# Filter for errors
gcloud functions logs read venmo-sync-trigger --gen2 --region=us-west1 --limit=50 | grep ERROR
```

### Common Issues

1. **"VENMO_ACCESS_TOKEN not configured"**
   - Check secret exists: `gcloud secrets list`
   - Check IAM permissions on secret
   - Redeploy function

2. **"Failed to connect to Venmo"**
   - Token may be expired (shouldn't happen, but check)
   - Venmo API may be down
   - Run `python payments-management.py sync-venmo` locally to test

3. **"Could not fetch main sheet data"**
   - Check spreadsheet ID is correct
   - Check service account has access to spreadsheet
   - Check sheet name matches

4. **Duplicate payments**
   - Should not happen (transaction ID deduplication)
   - Check Payment Log for duplicate transaction IDs

## Cost Estimate

**Google Cloud Functions:**
- Invocations: ~30/month (1 per payment)
- Duration: ~2-3 seconds each
- Memory: 256MB
- **Cost: $0/month** (Free tier: 2M invocations, 400K GB-seconds/month)

**Total: $0/month** ✅

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export VENMO_ACCESS_TOKEN="your-token"
export SMAD_SPREADSHEET_ID="your-sheet-id"
export SMAD_GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'

# Run locally with Functions Framework
functions-framework --target=venmo_email_trigger --debug

# Test with curl
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

## Maintenance

### Update Function

```bash
cd webhook/venmo-trigger
gcloud functions deploy venmo-sync-trigger --gen2 --region=us-west1
```

### Rotate Secrets

```bash
# Update Venmo token
echo -n "NEW_TOKEN" | gcloud secrets versions add VENMO_ACCESS_TOKEN --data-file=-

# Update service account
gcloud secrets versions add SMAD_GOOGLE_CREDENTIALS_JSON --data-file=new-smad-credentials.json

# Redeploy function to pick up new secrets
gcloud functions deploy venmo-sync-trigger --gen2 --region=us-west1
```

## Troubleshooting

### Test Venmo Connection

```python
from venmo_api import Client
import os

client = Client(access_token=os.environ['VENMO_ACCESS_TOKEN'])
print(f"Connected as: {client.my_profile().username}")
transactions = client.user.get_user_transactions(
    user_id=client.my_profile().id,
    limit=5
)
print(f"Found {len(transactions)} transactions")
```

### Test Google Sheets Access

```python
import json
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds_json = json.loads(os.environ['SMAD_GOOGLE_CREDENTIALS_JSON'])
creds = Credentials.from_service_account_info(
    creds_json,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
service = build('sheets', 'v4', credentials=creds).spreadsheets()

spreadsheet_id = os.environ['SMAD_SPREADSHEET_ID']
result = service.values().get(
    spreadsheetId=spreadsheet_id,
    range='2026 Pickleball!A1:B5'
).execute()
print(f"Fetched {len(result.get('values', []))} rows")
```

## Security Notes

- Cloud Function is **unauthenticated** (anyone with URL can trigger)
- Email content is NOT parsed (no sensitive data processed)
- Consider adding basic auth header validation if concerned
- All credentials stored in Secret Manager (not in code)
- Service account has minimal permissions (Sheets API only)

## Support

For issues or questions:
1. Check logs: `gcloud functions logs read venmo-sync-trigger --gen2`
2. Test manually: Run `python payments-management.py sync-venmo` locally
3. Review [Venmo API docs](https://github.com/mmohades/Venmo)
4. Review [Cloud Functions docs](https://cloud.google.com/functions/docs)
