from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from fastapi.responses import JSONResponse
from agent import googlebot
from dispatcher import dispatch_command
from typing import Dict, Any
import json
import ast  # For safely evaluating string literals

app = FastAPI()

# Configure CORS - adjust these settings for production!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = googlebot()


def parse_system_command(command_str: str) -> Any:
    """Safely parse system commands that might use single quotes"""
    try:
        # First try to parse as JSON (with double quotes)
        return json.loads(command_str)
    except json.JSONDecodeError:
        try:
            # If JSON fails, try parsing as Python literal (handles single quotes)
            return ast.literal_eval(command_str)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"Invalid command format: {str(e)}")


def format_calendar_result(result: Any) -> Dict[str, Any]:
    """Format calendar API results for user/system readability."""
    if isinstance(result, str):
        return {"link": result, "status": "completed"}

    elif isinstance(result, list):
        def parse_time(time_str: str) -> str:
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                return dt.strftime("%I:%M %p on %b %d")
            except Exception:
                return time_str  # fallback

        formatted_events = []
        for event in result:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            formatted_events.append({
                "id": event.get("id"),
                "summary": event.get("summary", "No title"),
                "start": parse_time(start),
                "end": parse_time(end),
                "location": event.get("location", ""),
                "description": event.get("description", "")
            })
        return {"events": formatted_events}

    elif isinstance(result, dict):
        return result

    return {"result": str(result)}


def enhance_response(original: Dict[str, Any], result: Any) -> Dict[str, Any]:
    """Add casual summary to the AI response using calendar result."""
    response = original.copy()
    casual = response.get("casual", "Here's what I found:")

    if isinstance(result, str) and "calendar.google.com" in result:
        casual += f"\n\n📅 Event link: {result}"

    elif isinstance(result, list):
        if result:
            events = format_calendar_result(result)["events"]
            event_lines = "\n".join(
                f"- {e['summary']} at {e['start']}" for e in events[:5]
            )
            casual += f"\n\n🗓️ Upcoming events:\n{event_lines}"
        else:
            casual += "\n\nYou're totally free! 🧘‍♂️ No events found."

    response["casual"] = casual.strip()
    return response


@app.get("/chat/{text}")
async def chat(text: str) -> JSONResponse:
    """
    Processes user messages through CalendarBot with strict data handling.
    Maintains conversation flow while preventing system data leaks.
    """
    MAX_SYSTEM_ITERATIONS = 2  # Prevent infinite loops

    try:
        # Initialize conversation
        prompt = f"{text} system: stamp:[{datetime.now().isoformat()}]"
        bot_response = bot.get_message_from_bot(prompt)

        # Parse response (handling both str and dict formats)
        try:
            ai_response = bot_response if isinstance(bot_response, dict) else json.loads(bot_response)
        except (json.JSONDecodeError, TypeError):
            ai_response = {"casual": "Let me check that for you...", "system": "", "insight": {}}

        # System command processing pipeline
        iteration = 0
        while ai_response.get("system") and iteration < MAX_SYSTEM_ITERATIONS:
            try:
                # Parse and execute system command
                command_str = ai_response["system"]
                try:
                    # First try to parse the command parameters
                    command_name, params_str = command_str.split("(", 1)
                    params_str = params_str.rstrip(")")

                    # Convert to proper JSON format if needed
                    if not params_str.startswith("{"):
                        params_str = "{" + params_str + "}"

                    # Parse the parameters
                    params = parse_system_command(params_str)

                    # Reconstruct the command with proper JSON
                    reconstructed_command = f"{command_name}({json.dumps(params)})"
                    command_result = dispatch_command(reconstructed_command)
                except Exception as parse_error:
                    print(f"Command parsing failed: {parse_error}")
                    # Fallback to original command
                    command_result = dispatch_command(command_str)

                print("Command result:", command_result)

                # Format result for bot consumption
                processed_result = format_calendar_result(command_result)

                # Generate next response
                continuation_prompt = {
                    "role": "system",
                    "content": json.dumps(processed_result),
                    "timestamp": datetime.now().isoformat()
                }
                ai_response = bot.get_message_from_bot(json.dumps(continuation_prompt))

                iteration += 1
            except Exception as cmd_error:
                print(f"Command execution error: {cmd_error}")
                ai_response = {
                    "casual": "Having trouble with that request. Let's try again.",
                    "system": "",
                    "insight": ai_response.get("insight", {})
                }
                break

        # Final response sanitization
        safe_response = {
            "role": "assistant",
            "response": ai_response.get("casual", "How can I help with your schedule?"),
            "metadata": {
                "processed_commands": iteration,
                "last_intent": ai_response.get("insight", {}).get("intent")
            }
        }

        return JSONResponse(content=safe_response)

    except Exception as e:
        print(f"Unexpected error: {e}")
        error_msg = "Calendar services are temporarily unavailable" if "connection" in str(
            e).lower() else "Something went wrong"

        return JSONResponse(
            status_code=500,
            content={
                "role": "system",
                "response": error_msg,
                "metadata": {"error_type": "internal"}
            }
        )


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

