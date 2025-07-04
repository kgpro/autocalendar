import streamlit as st
import requests
from datetime import datetime
import time
import json
from typing import Optional, Dict, Any

# Configuration
API_URL = "http://localhost:8000/chat"
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Custom CSS for dynamic UI
st.markdown("""
<style>
    /* Main chat container */
    .main .block-container {
        max-width: 900px;
        padding-top: 2rem;
    }
    
    /* Enhanced text input */
    .stTextInput>div>div>input {
        height: 100px !important;
        width: 100% !important;
        font-size: 16px !important;
        padding: 15px !important;
        border-radius: 20px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput>div>div>input:focus {
        box-shadow: 0 6px 10px rgba(0, 0, 0, 0.15) !important;
        border-color: #4a90e2 !important;
    }
    
    /* Chat messages */
    .stChatMessage {
        border-radius: 20px !important;
        padding: 15px 20px !important;
        margin: 10px 0 !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05) !important;
        transition: transform 0.2s ease;
    }
    
    .stChatMessage:hover {
        transform: translateY(-2px);
    }
    
    /* User message */
    [data-testid="stChatMessage-user"] {
        background-color: #f8f9fa;
        border-left: 4px solid #4a90e2;
    }
    
    /* Assistant message */
    [data-testid="stChatMessage-assistant"] {
        background-color: #e6f7ff;
        border-left: 4px solid #00b4d8;
    }
    
    /* Typing animation */
    @keyframes typing {
        0% { opacity: 0.4; }
        50% { opacity: 1; }
        100% { opacity: 0.4; }
    }
    
    .typing-dots {
        display: flex;
        padding: 10px 0;
    }
    
    .typing-dots span {
        height: 10px;
        width: 10px;
        margin: 0 2px;
        background-color: #6c757d;
        border-radius: 50%;
        display: inline-block;
        animation: typing 1.4s infinite ease-in-out;
    }
    
    .typing-dots span:nth-child(2) {
        animation-delay: 0.2s;
    }
    
    .typing-dots span:nth-child(3) {
        animation-delay: 0.4s;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_status" not in st.session_state:
    st.session_state.api_status = "unknown"

if "typing_indicator" not in st.session_state:
    st.session_state.typing_indicator = False

# Sidebar for settings
with st.sidebar:
    st.title("⚙️ Settings")
    st.markdown("---")
    
    # API status indicator
    status_color = {
        "healthy": "#28a745",
        "unhealthy": "#dc3545",
        "unknown": "#6c757d"
    }.get(st.session_state.api_status, "#6c757d")
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <div style="width: 12px; height: 12px; border-radius: 50%; background-color: {status_color}; 
                    margin-right: 8px;"></div>
        <span>API Status: <strong>{st.session_state.api_status.capitalize()}</strong></span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Check Connection"):
        with st.spinner("Checking..."):
            try:
                test_response = requests.get(API_URL, timeout=3)
                if test_response.status_code == 200:
                    st.session_state.api_status = "healthy"
                    st.success("✅ Connected successfully!")
                else:
                    st.session_state.api_status = "unhealthy"
                    st.error(f"❌ API returned status {test_response.status_code}")
            except Exception as e:
                st.session_state.api_status = "unhealthy"
                st.error(f"❌ Connection failed: {str(e)}")
    
    st.markdown("---")
    st.markdown("### Quick Actions")
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.title("📅 CalendarBot Assistant")
st.caption("Your intelligent scheduling assistant")

# Display messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and "metadata" in msg and "suggestions" in msg["metadata"]:
            cols = st.columns(len(msg["metadata"]["suggestions"]))
            for col_idx, suggestion in enumerate(msg["metadata"]["suggestions"]):
                with cols[col_idx]:
                    if st.button(suggestion):
                        st.session_state.messages.append({
                            "role": "user", 
                            "content": suggestion,
                            "timestamp": datetime.now().isoformat()
                        })
                        st.rerun()

# Typing indicator
if st.session_state.typing_indicator:
    with st.chat_message("assistant"):
        st.markdown("""
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        """, unsafe_allow_html=True)

# Enhanced text input
user_input = st.chat_input(
    "Type your message here...", 
    key="chat_input"
)

# Function to send message to API
def send_to_api(message: str) -> Optional[Dict[str, Any]]:
    """Send message to API with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            st.session_state.typing_indicator = True
            st.rerun()
            
            response = requests.post(
                API_URL,
                json={"text": message},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            st.error(f"API request failed after {MAX_RETRIES} attempts")
            return None
        finally:
            st.session_state.typing_indicator = False
            st.rerun()

# Process user input
if user_input:
    # Add user message to history
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now().isoformat()
    })
    st.rerun()
    
    # Get bot response
    bot_response = send_to_api(user_input)
    
    if bot_response:
        # Format response with metadata
        formatted_response = {
            "role": "assistant",
            "content": bot_response.get("response", "I didn't understand that."),
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "intent": bot_response.get("metadata", {}).get("last_intent"),
                "suggestions": ["Confirm", "Change", "Cancel"]  # Simplified for this example
            }
        }
        
        # Add to message history
        st.session_state.messages.append(formatted_response)
        st.rerun()
    else:
        # Error case
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Sorry, I'm having trouble connecting to the calendar service.",
            "timestamp": datetime.now().isoformat()
        })
        st.rerun()
