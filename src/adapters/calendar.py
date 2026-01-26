"""Calendar/Reservation adapter implementations"""

from typing import Dict, Any, Optional
import aiohttp
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
import asyncio

from .base import CalendarAdapter


class YelpAdapter(CalendarAdapter):
    """Yelp Reservation API adapter"""
    
    def __init__(self, api_key: str, restaurant_id: str):
        self.api_key = api_key
        self.restaurant_id = restaurant_id
        self.base_url = "https://api.yelp.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_reservation(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reservation via Yelp API"""
        # Note: Yelp Fusion API doesn't have a direct reservation endpoint
        # This is a placeholder that would integrate with Yelp's reservation system
        # or a restaurant's own reservation system that uses Yelp
        
        reservation_data = {
            "restaurant_id": self.restaurant_id,
            "date": details.get("date"),
            "time": details.get("time"),
            "party_size": details.get("party_size"),
            "customer_name": details.get("customer_name"),
            "customer_phone": details.get("customer_phone"),
            "customer_email": details.get("customer_email"),
            "special_requests": details.get("special_requests", ""),
        }
        
        # In a real implementation, this would call Yelp's reservation API
        # For now, return a mock response
        async with aiohttp.ClientSession() as session:
            try:
                # This is a placeholder - actual Yelp reservation endpoint would be used
                # url = f"{self.base_url}/reservations"
                # async with session.post(url, json=reservation_data, headers=self.headers) as response:
                #     return await response.json()
                
                # Mock response for now
                return {
                    "reservation_id": f"yelp_{datetime.now().timestamp()}",
                    "status": "confirmed",
                    "details": reservation_data
                }
            except Exception as e:
                print(f"Yelp reservation error: {e}")
                return {"error": str(e)}
    
    async def check_availability(self, date: str, time: str, party_size: int) -> bool:
        """Check if time slot is available"""
        # Check availability via Yelp API
        # This would query the restaurant's availability
        async with aiohttp.ClientSession() as session:
            try:
                # Placeholder - actual implementation would query Yelp
                # For now, assume available if party size <= 8
                return party_size <= 8
            except Exception as e:
                print(f"Availability check error: {e}")
                return False
    
    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel a reservation"""
        async with aiohttp.ClientSession() as session:
            try:
                # Placeholder - actual implementation would call Yelp cancellation endpoint
                # url = f"{self.base_url}/reservations/{reservation_id}"
                # async with session.delete(url, headers=self.headers) as response:
                #     return response.status == 200
                return True
            except Exception as e:
                print(f"Cancellation error: {e}")
                return False


class GoogleCalendarAdapter(CalendarAdapter):
    """Google Calendar adapter"""
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_json: Optional[str] = None,
        calendar_id: str = "primary",
        token_path: Optional[str] = None
    ):
        """
        Initialize Google Calendar adapter
        
        Args:
            credentials_path: Path to service account JSON file
            credentials_json: Service account JSON as string (alternative to credentials_path)
            calendar_id: Google Calendar ID (default: "primary")
            token_path: Path to OAuth token file (for user authentication)
        """
        self.calendar_id = calendar_id
        self.service = None
        
        # Initialize credentials
        if credentials_json:
            # Use provided JSON string
            creds_info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
        elif credentials_path and os.path.exists(credentials_path):
            # Use service account file
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
        elif token_path and os.path.exists(token_path):
            # Use OAuth token
            credentials = Credentials.from_authorized_user_file(
                token_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
        else:
            raise ValueError(
                "Must provide credentials_path, credentials_json, or token_path"
            )
        
        # Build the service
        self.service = build('calendar', 'v3', credentials=credentials)
    
    async def create_reservation(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reservation in Google Calendar"""
        try:
            # Parse date and time
            date_str = details.get("date")
            time_str = details.get("time")
            
            # Combine date and time
            datetime_str = f"{date_str}T{time_str}:00"
            try:
                start_datetime = datetime.fromisoformat(datetime_str)
            except ValueError:
                # Try alternative format
                start_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            
            # Estimate end time (default 2 hours for restaurant reservation)
            end_datetime = start_datetime + timedelta(hours=2)
            
            # Create event
            event = {
                'summary': f"Reservation - {details.get('customer_name', 'Guest')}",
                'description': self._format_reservation_description(details),
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                    ],
                },
            }
            
            # Add customer email if provided
            if details.get("customer_email"):
                event['attendees'].append({'email': details.get("customer_email")})
            
            # Create the event (run in thread pool to avoid blocking)
            def create_event():
                return self.service.events().insert(
                    calendarId=self.calendar_id,
                    body=event
                ).execute()
            
            created_event = await asyncio.to_thread(create_event)
            
            return {
                "reservation_id": created_event.get('id'),
                "status": "confirmed",
                "event_link": created_event.get('htmlLink'),
                "details": details
            }
            
        except HttpError as e:
            print(f"Google Calendar error: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"Reservation creation error: {e}")
            return {"error": str(e)}
    
    def _format_reservation_description(self, details: Dict[str, Any]) -> str:
        """Format reservation details as event description"""
        desc_parts = [
            f"Party Size: {details.get('party_size', 'N/A')}",
            f"Customer: {details.get('customer_name', 'N/A')}",
            f"Phone: {details.get('customer_phone', 'N/A')}",
        ]
        
        if details.get("customer_email"):
            desc_parts.append(f"Email: {details.get('customer_email')}")
        
        if details.get("special_requests"):
            desc_parts.append(f"\nSpecial Requests: {details.get('special_requests')}")
        
        return "\n".join(desc_parts)
    
    async def check_availability(self, date: str, time: str, party_size: int) -> bool:
        """Check if time slot is available"""
        try:
            # Parse date and time
            datetime_str = f"{date}T{time}:00"
            try:
                start_datetime = datetime.fromisoformat(datetime_str)
            except ValueError:
                start_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            
            # Check 2 hours ahead (typical reservation duration)
            end_datetime = start_datetime + timedelta(hours=2)
            
            # Query for existing events in this time range (run in thread pool)
            def list_events():
                return self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=start_datetime.isoformat() + 'Z',
                    timeMax=end_datetime.isoformat() + 'Z',
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
            
            events_result = await asyncio.to_thread(list_events)
            
            events = events_result.get('items', [])
            
            # Check if there are conflicting events
            # For simplicity, we'll allow overlapping if party size is reasonable
            # In a real system, you might check table availability
            if len(events) > 0:
                # Check if any event is a reservation that would conflict
                for event in events:
                    # If there's a reservation event, check if we can accommodate
                    # This is simplified - real implementation would check table capacity
                    if 'Reservation' in event.get('summary', ''):
                        # For now, allow if party size is small (<= 4)
                        # Larger parties might need more checking
                        if party_size > 4:
                            return False
            
            # Check maximum capacity (simplified - assume max 20 people per time slot)
            total_people = party_size
            for event in events:
                if 'Reservation' in event.get('summary', ''):
                    # Try to extract party size from description
                    desc = event.get('description', '')
                    if 'Party Size:' in desc:
                        try:
                            existing_size = int(desc.split('Party Size:')[1].split('\n')[0].strip())
                            total_people += existing_size
                        except:
                            pass
            
            # Allow if total is under capacity
            return total_people <= 20
            
        except HttpError as e:
            print(f"Google Calendar availability check error: {e}")
            return False
        except Exception as e:
            print(f"Availability check error: {e}")
            return False
    
    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel a reservation (delete event)"""
        try:
            def delete_event():
                return self.service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=reservation_id
                ).execute()
            
            await asyncio.to_thread(delete_event)
            return True
        except HttpError as e:
            if e.resp.status == 404:
                # Event not found - consider it cancelled
                return True
            print(f"Google Calendar cancellation error: {e}")
            return False
        except Exception as e:
            print(f"Cancellation error: {e}")
            return False
