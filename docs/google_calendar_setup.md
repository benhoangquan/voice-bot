# Google Calendar Setup Guide

This guide explains how to set up Google Calendar integration for the voice bot.

## Authentication Options

The Google Calendar adapter supports three authentication methods:

### Option 1: Service Account (Recommended for Production)

1. **Create a Service Account**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Calendar API
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name and description
   - Click "Create and Continue"
   - Grant it the "Editor" role (or create a custom role with calendar permissions)
   - Click "Done"

2. **Create and Download Key**
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format
   - Download the JSON file

3. **Share Calendar with Service Account**
   - Open Google Calendar
   - Go to Settings > Settings for my calendars
   - Select the calendar you want to use
   - Click "Share with specific people"
   - Add the service account email (found in the JSON file, `client_email` field)
   - Give it "Make changes to events" permission
   - Click "Send"

4. **Configure Environment**
   ```bash
   # Option A: Use file path
   GOOGLE_CALENDAR_CREDENTIALS_PATH=./credentials/service-account.json
   GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
   
   # Option B: Use JSON string (for cloud deployments)
   GOOGLE_CALENDAR_CREDENTIALS_JSON='{"type":"service_account",...}'
   GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
   ```

### Option 2: OAuth 2.0 (For User Calendar Access)

1. **Create OAuth Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the Google Calendar API
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as application type
   - Download the credentials JSON

2. **Generate Token**
   - Run the OAuth flow to generate a token file
   - You can use the Google OAuth playground or write a script
   - Save the token to a file

3. **Configure Environment**
   ```bash
   GOOGLE_CALENDAR_TOKEN_PATH=./credentials/token.json
   GOOGLE_CALENDAR_ID=primary
   ```

## Calendar ID

- **Primary Calendar**: Use `"primary"` (default)
- **Shared Calendar**: Use the calendar email address (e.g., `restaurant@example.com`)
- **Custom Calendar**: Use the calendar ID from Google Calendar settings

## Testing

After setup, test the integration:

```python
from src.adapters.calendar import GoogleCalendarAdapter

# Initialize adapter
adapter = GoogleCalendarAdapter(
    credentials_path="./credentials/service-account.json",
    calendar_id="primary"
)

# Test availability check
available = await adapter.check_availability("2024-12-25", "19:00", 4)
print(f"Available: {available}")

# Test reservation creation
result = await adapter.create_reservation({
    "date": "2024-12-25",
    "time": "19:00",
    "party_size": 4,
    "customer_name": "Test Customer",
    "customer_phone": "+1234567890",
    "customer_email": "test@example.com",
    "special_requests": "Window seat preferred"
})
print(f"Reservation: {result}")
```

## Troubleshooting

### "Insufficient Permission" Error
- Make sure the service account has been shared with the calendar
- Check that the calendar sharing permissions include "Make changes to events"

### "Calendar not found" Error
- Verify the calendar ID is correct
- For shared calendars, use the full email address
- Check that the service account has access to the calendar

### Authentication Errors
- Verify the credentials file path is correct
- Check that the JSON file is valid
- Ensure the service account hasn't been deleted

## Security Notes

- Never commit credentials files to version control
- Use environment variables for credentials in production
- Rotate service account keys regularly
- Use least-privilege permissions
