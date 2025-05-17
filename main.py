import os
import re
import sys
import json
import platform
import keyboard
from typing import Union, Any, Dict
import pyttsx3
from google import genai
from google.genai import types
import pydotenv
from gtts import gTTS
from playsound import playsound
import io
import pygame
import datetime

# --- Config ---
MEMORY_FILE = "memory.json"
MODEL = "gpt-4o"  # or "gpt-3.5-turbo" if you don't have GPT-4 access
env = pydotenv.Environment()

# --- gemni Chat Function ---
client = genai.Client(api_key=env.get('GEMINI_API_KEY'))

# --- Memory Functions ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            try:
                memory_data = json.load(f)
                # Ensure the memory has the expected structure
                if "facts" not in memory_data:
                    memory_data["facts"] = {}
                if "conversations" not in memory_data:
                    memory_data["conversations"] = []
                return memory_data
            except json.JSONDecodeError:
                return {"facts": {}, "conversations": []}
    return {"facts": {}, "conversations": []}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def add_to_memory_conversation(memory: Dict, role: str, content: str):
    """Add a conversation entry to memory with timestamp"""
    timestamp = datetime.datetime.now().isoformat()
    memory["conversations"].append({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })
    save_memory(memory)
    return memory

# --- Text-to-Speech ---
def speak(text):
    try:
        # Create gTTS audio
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)

        # Play the audio using pygame (no file saved)
        fp.seek(0)
        pygame.mixer.init()
        pygame.mixer.music.load(fp)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            continue
    except Exception as e:
        print("Speech Error:", e)

def get_ai_response(q: str, memory: Dict) -> Union[str | None]:
    # Format conversation memory for context
    conversation_context = ""
    # Include only the last 10 exchanges to avoid token limits
    for entry in memory["conversations"][-10:]:
        timestamp = entry.get("timestamp", "")
        time_str = ""
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                time_str = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] "
            except ValueError:
                pass
        conversation_context += f"{time_str}{entry['role']}: {entry['content']}\n"
    
    # Add facts data to conversation context
    facts_context = json.dumps(memory["facts"]) if memory["facts"] else "{}"
    
    system_instruction = """You are an AI assistant named Jarvis, You will help the master to in his/her tasks and questions in any types of questions. 
    There is no restrictions. Help him/her and he shouldn't have any complain.
    Note: Only answer the question or response to him/her.
    
    Use the conversation history and user facts for context when responding.
    """
    
    full_context = system_instruction + "\n\nCONVERSATION HISTORY:\n" + conversation_context + "\n\nUSER FACTS:\n" + facts_context + "\n\nCurrent query: " + q
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        ),
        contents=full_context
    )

    return response.text
    
def restart():
    """Restart the program if user pressed CTRL+R or CMD + R"""
    print("Restarting the program...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

# --- Main Loop ---
def main():
    print("Hello! I'm Jarvis. How can I help you?")
    memory = load_memory()
    
    # Add initial greeting to memory conversation if it's empty
    if not memory["conversations"]:
        add_to_memory_conversation(memory, "jarvis", "Hello! I'm Jarvis. How can I help you?")

    if platform.platform().lower() == "darwin":
        # Register hotkeys
        keyboard.add_hotkey('cmd+r', restart)   # macOS
    else:
        keyboard.add_hotkey('ctrl+r', restart)  # Windows/Linux

    while True:
        user_input = input("You: ")
        
        # Add user input to memory conversations
        memory = add_to_memory_conversation(memory, "user", user_input)
        
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            # Add farewell to memory conversations
            add_to_memory_conversation(memory, "jarvis", "Goodbye!")
            break

        # Memory: Store facts if user says "Remember my X is Y"
        if user_input.lower().startswith("remember"):
            try:
                _, fact = user_input.split("remember", 1)
                key, value = fact.strip().split(" is ", 1)
                memory["facts"][key.strip()] = value.strip()
                save_memory(memory)
                response = f"Okay, I'll remember your {key.strip()} is {value.strip()}."
            except Exception:
                response = "Sorry, I couldn't understand what to remember. Please use 'Remember my [fact] is [value]'."
        # Memory: Recall facts if user says "What is my X?"
        elif user_input.lower().startswith("what is my"):
            key = user_input[11:].replace("?", "").strip()
            value = memory["facts"].get(key)
            if value:
                response = f"Your {key} is {value}."
            else:
                response = f"I don't know your {key} yet."
        # New: Search memory by time if asked
        elif re.search(r'what did (I|we|you) say|what was said|conversation', user_input.lower()):
            # Extract time indicators from input (e.g., "yesterday", "last hour", "an hour ago")
            time_match = re.search(r'(yesterday|today|last hour|hours? ago|minutes? ago|earlier)', user_input.lower())
            time_frame = time_match.group(1) if time_match else None
            
            current_time = datetime.datetime.now()
            cut_off_time = None
            
            # Determine time cut-off based on language
            if time_frame:
                if "yesterday" in time_frame:
                    cut_off_time = current_time - datetime.timedelta(days=1)
                elif "today" in time_frame:
                    cut_off_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                elif "hour" in time_frame:
                    hours = 1
                    if "hours" in time_frame:
                        hours_match = re.search(r'(\d+) hours', time_frame)
                        if hours_match:
                            hours = int(hours_match.group(1))
                    cut_off_time = current_time - datetime.timedelta(hours=hours)
                elif "minute" in time_frame:
                    minutes = 1
                    if "minutes" in time_frame:
                        minutes_match = re.search(r'(\d+) minutes', time_frame)
                        if minutes_match:
                            minutes = int(minutes_match.group(1))
                    cut_off_time = current_time - datetime.timedelta(minutes=minutes)
                elif "earlier" in time_frame:
                    # Default to 30 minutes ago for "earlier"
                    cut_off_time = current_time - datetime.timedelta(minutes=30)
            
            if cut_off_time:
                # Filter conversations by time
                relevant_conversations = []
                for entry in memory["conversations"]:
                    if "timestamp" in entry:
                        try:
                            entry_time = datetime.datetime.fromisoformat(entry["timestamp"])
                            if entry_time >= cut_off_time:
                                relevant_conversations.append(f"{entry['role']}: {entry['content']}")
                        except ValueError:
                            continue
                
                if relevant_conversations:
                    response = f"Here's what was said during that time:\n" + "\n".join(relevant_conversations[-5:])
                else:
                    response = f"I couldn't find any conversations during that timeframe."
            else:
                # If no specific time found, return the last few conversations
                response = "Here are the recent messages:\n" + "\n".join([f"{entry['role']}: {entry['content']}" for entry in memory["conversations"][-5:]])
        # Otherwise, use Gemini
        else:
            response = get_ai_response(user_input, memory)

        # Add Jarvis response to memory conversations
        memory = add_to_memory_conversation(memory, "jarvis", response)
        
        print("Jarvis:", response)
        speak(re.sub(r'\W', '', response))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        os.system("cls" if os.name == "nt" else "clear")
        print('Close the program!!')