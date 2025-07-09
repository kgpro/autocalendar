import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, field_validator
from calendar_service import GoogleCalendarAutomation
from dotenv import load_dotenv
import os
load_dotenv()
# Configuration - replace these with your actual values
CREDENTIAL_FILE = "credentials.json"
SERVICE_EMAIL = os.getenv('SERVICE_MAIL_ID')
CALENDAR_ID = os.getenv('GMAIL')

class EventDetails(BaseModel):
    """Simplified event model for personal calendar management"""
    summary: str
    start_time: Union[str, datetime]
    end_time: Union[str, datetime]
    timezone: str = 'UTC'
    description: Optional[str] = None
    location: Optional[str] = None

    @field_validator('start_time', 'end_time', mode='before')
    def parse_datetime(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid datetime format: {value}")
        return value


class CalendarDispatcher:
    def __init__(self):
        # Initialize the Google Calendar service
        self.calendar_service = GoogleCalendarAutomation(
            credential_file=CREDENTIAL_FILE,
            service_email=SERVICE_EMAIL,
            calendar_id=CALENDAR_ID
        )
        self.calendar_service.authenticate()

        self.operations = {
            "create_event": self._handle_create_event,
            "list_events": self._handle_list_events,
            "update_event": self._handle_update_event,
            "delete_event": self._handle_delete_event,
        }

    def dispatch(self, command: str) -> Any:
        """Execute calendar commands for personal management"""
        try:
            command = command.strip()
            if not command:
                raise ValueError("Empty command")

            # Parse command and arguments
            cmd_parts = command.split("(", 1)
            if len(cmd_parts) != 2 or not cmd_parts[1].endswith(")"):
                raise ValueError(f"Invalid command format: {command[:50]}...")

            cmd_name = cmd_parts[0]
            if cmd_name not in self.operations:
                raise ValueError(f"Unknown command: {cmd_name}")

            args_str = cmd_parts[1][:-1]  # Remove trailing )
            return self.operations[cmd_name](args_str)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in command: {str(e)}")
        except Exception as e:
            raise ValueError(f"Command execution failed: {str(e)}")

    def _handle_create_event(self, args: str) -> Dict[str, Any]:
        """Handle event creation for personal calendar"""
        payload = json.loads(args)
        event_details = EventDetails(**payload)

        # Convert datetime objects to strings if needed
        start_time = event_details.start_time.isoformat() if isinstance(event_details.start_time,
                                                                        datetime) else event_details.start_time
        end_time = event_details.end_time.isoformat() if isinstance(event_details.end_time,
                                                                    datetime) else event_details.end_time

        return self.calendar_service.create_event(
            summary=event_details.summary,
            start_time=start_time,
            end_time=end_time,
            timezone=event_details.timezone,
            description=event_details.description,
            location=event_details.location
        )

    def _handle_list_events(self, args: str) -> List[Dict[str, Any]]:
        """List events with optional time range"""
        params = json.loads(args) if args else {}
        return self.calendar_service.list_events(
            time_min=params.get('time_min'),
            time_max=params.get('time_max'),
            max_results=params.get('max_results', 50)
        )

    def _handle_update_event(self, args: str) -> Dict[str, Any]:
        """Update existing event"""
        event_id, update_data = args.split(",", 1)
        event_id = event_id.strip(" '\"")
        update_payload = json.loads(update_data.strip())

        # Convert string datetimes if needed
        for time_field in ['start_time', 'end_time']:
            if time_field in update_payload:
                if isinstance(update_payload[time_field], str):
                    update_payload[time_field] = datetime.fromisoformat(update_payload[time_field])

        return self.calendar_service.update_event(
            event_id=event_id,
            **update_payload
        )

    def _handle_delete_event(self, args: str) -> Dict[str, str]:
        """Delete an event"""
        event_id = args.strip("'\"")
        success = self.calendar_service.delete_event(event_id=event_id)
        return {"status": "success" if success else "failed", "event_id": event_id}


def dispatch_command(command: str) -> Any:
    """Public interface for command dispatching"""
    return CalendarDispatcher().dispatch(command)

