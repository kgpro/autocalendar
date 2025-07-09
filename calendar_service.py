import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarAutomation:
    def __init__(self, credential_file, service_email, calendar_id, delegated_user=None):
        """
        Initialize the Google Calendar automation with credentials and calendar ID.

        Args:
            credential_file (str): Path to the service account credentials JSON file
            service_email (str): The service account email address
            calendar_id (str): The ID of the shared calendar to manage
            delegated_user (str): Email of user to impersonate (for domain-wide delegation)
        """
        self.credential_file = credential_file
        self.service_email = service_email
        self.calendar_id = calendar_id
        self.delegated_user = delegated_user
        self.service = None

        # Validate inputs
        if not os.path.exists(credential_file):
            raise FileNotFoundError(f"Credential file not found: {credential_file}")

        if not service_email or not calendar_id:
            raise ValueError("Service email and calendar ID must be provided")

    def authenticate(self):
        """Authenticate with Google Calendar API using service account credentials."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credential_file,
                scopes=['https://www.googleapis.com/auth/calendar']
            )

            # If domain-wide delegation is set up, impersonate the user
            if self.delegated_user:
                credentials = credentials.with_subject(self.delegated_user)
            else:
                # Without delegation, just use the service account
                credentials = credentials.with_subject(self.service_email)

            self.service = build('calendar', 'v3', credentials=credentials)
            return True
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            return False

    def create_event(self, summary, start_time, end_time, timezone='UTC', description=None, location=None,
                     attendees=None, send_updates='none'):
        """
        Create a new event on the calendar.

        Args:
            summary (str): Title of the event
            start_time (str/datetime): Start time in ISO format or datetime object
            end_time (str/datetime): End time in ISO format or datetime object
            timezone (str): Timezone for the event (default: 'UTC')
            description (str): Optional event description
            location (str): Optional event location
            attendees (list): Optional list of attendee email addresses
            send_updates (str): Whether to send notifications ('none', 'all', 'externalOnly')

        Returns:
            dict: The created event details or None if failed
        """
        if not self.service:
            if not self.authenticate():
                return None

        # Convert datetime objects to ISO strings if needed
        if isinstance(start_time, datetime):
            start_time = start_time.isoformat()
        if isinstance(end_time, datetime):
            end_time = end_time.isoformat()

        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': timezone,
            },
        }

        if description:
            event['description'] = description
        if location:
            event['location'] = location
        if attendees:
            if not self.delegated_user:
                print("Warning: Attendees won't receive invitations without domain-wide delegation")
            event['attendees'] = [{'email': email} for email in attendees]

        try:
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendUpdates=send_updates
            ).execute()
            print(f"Event created: {created_event.get('htmlLink')}")
            return created_event
        except HttpError as error:
            if error.resp.status == 403 and 'forbiddenForServiceAccounts' in str(error):
                print("Service account cannot send invitations without domain-wide delegation")
                print("Creating event without sending invitations...")
                # Retry without attendees if the error is due to delegation
                if 'attendees' in event:
                    del event['attendees']
                return self.service.events().insert(
                    calendarId=self.calendar_id,
                    body=event,
                    sendUpdates='none'
                ).execute()
            print(f"An error occurred while creating event: {error}")
            return None


    def list_events(self, time_min=None, time_max=None, max_results=10):
        """
        List events from the calendar within a time range.

        Args:
            time_min (str/datetime): Minimum time for events (default: now)
            time_max (str/datetime): Maximum time for events (default: 30 days from now)
            max_results (int): Maximum number of events to return

        Returns:
            list: List of events or None if failed
        """
        if not self.service:
            if not self.authenticate():
                return None

        # Set default time range if not provided
        now = datetime.utcnow()
        if time_min is None:
            time_min = now.isoformat() + 'Z'  # 'Z' indicates UTC time
        elif isinstance(time_min, datetime):
            time_min = time_min.isoformat() + 'Z'

        if time_max is None:
            time_max = (now + timedelta(days=30)).isoformat() + 'Z'
        elif isinstance(time_max, datetime):
            time_max = time_max.isoformat() + 'Z'

        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events
        except HttpError as error:
            print(f"An error occurred while listing events: {error}")
            return None


    def update_event(self, event_id, summary=None, start_time=None, end_time=None, timezone=None,
                     description=None, location=None, attendees=None):
        """
        Update an existing event.

        Args:
            event_id (str): ID of the event to update
            summary (str): Updated event title
            start_time (str/datetime): Updated start time
            end_time (str/datetime): Updated end time
            timezone (str): Updated timezone
            description (str): Updated description
            location (str): Updated location
            attendees (list): Updated list of attendee emails

        Returns:
            dict: Updated event details or None if failed
        """
        if not self.service:
            if not self.authenticate():
                return None

        try:
            # First get the existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            # Update fields if provided
            if summary:
                event['summary'] = summary
            if start_time:
                if isinstance(start_time, datetime):
                    start_time = start_time.isoformat()
                event['start']['dateTime'] = start_time
            if end_time:
                if isinstance(end_time, datetime):
                    end_time = end_time.isoformat()
                event['end']['dateTime'] = end_time
            if timezone:
                event['start']['timeZone'] = timezone
                event['end']['timeZone'] = timezone
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]

            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()

            print(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event
        except HttpError as error:
            print(f"An error occurred while updating event: {error}")
            return None


    def delete_event(self, event_id):
        """
        Delete an event from the calendar.

        Args:
            event_id (str): ID of the event to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            print(f"Event {event_id} deleted successfully")
            return True
        except HttpError as error:
            print(f"An error occurred while deleting event: {error}")
            return False


