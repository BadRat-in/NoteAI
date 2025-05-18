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
import speech_recognition as sr
import threading
import time

# --- Config ---
MEMORY_FILE = "memory.json"
MODEL = "gpt-4o"
WAKE_WORDS = ["jarvis"]
SLEEP_PHRASES = ["go to sleep", "that's all", "goodbye", "exit", "stop"]
STOP_PHRASES = ["stop", "pause", "quiet"]
LISTEN_TIMEOUT = 10
INACTIVITY_TIMEOUT = 10
env = pydotenv.Environment()

# Global flags
speaking = False
should_stop = False
active = False
waiting_for_response = False
last_interaction = 0

engine = pyttsx3.init()
engine.setProperty('rate', 180)

# --- gemini Chat Function ---
client = genai.Client(api_key=env.get('GEMINI_API_KEY'))

# --- Memory Functions ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            try:
                memory_data = json.load(f)
                if "facts" not in memory_data:
                    memory_data["facts"] = {}
                if "conversations" not in memory_data:
                    memory_data["conversations"] = []
                return memory_data
            except json.JSONDecodeError:
                return {"facts": {}, "conversations": []}
    return {"facts": {}, "conversations": []}

def save_memory(memory):
    if len(memory["conversations"]) % 3 == 0:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f)

def add_to_memory_conversation(memory: Dict, role: str, content: str):
    timestamp = datetime.datetime.now().isoformat()
    memory["conversations"].append({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })
    save_memory(memory)
    return memory

# --- Speech Recognition ---
def listen(timeout=3, phrase_limit=5):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            return recognizer.recognize_google(audio).lower()
        except:
            return None

def background_listening():
    global should_stop, active, waiting_for_response
    recognizer = sr.Recognizer()
    while speaking:
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio = recognizer.listen(source, phrase_time_limit=2, timeout=1)
                try:
                    text = recognizer.recognize_google(audio).lower()
                    if "stop" in text or "pause" in text or "quiet" in text:
                        should_stop = True
                        engine.stop()
                        active = False
                        waiting_for_response = False
                        print("Conversation stopped by user.")
                        break
                except:
                    continue
        except:
            time.sleep(0.5)
            continue

def speak(text):
    global speaking, should_stop, waiting_for_response
    try:
        print("Jarvis:", text)
        speaking = True
        should_stop = False
        listener_thread = threading.Thread(target=background_listening)
        listener_thread.daemon = True
        listener_thread.start()
        
        engine.say(text)
        engine.runAndWait()
        
        speaking = False
        
        if should_stop:
            should_stop = False
            print("Speech interrupted by stop command.")
            return False

        if active:
            waiting_for_response = True
        return True
    except Exception as e:
        print("Speech Error:", e)
        speaking = False
        should_stop = False
        return False


def get_ai_response(q: str, memory: Dict) -> Union[str, None]:
    conversation_context = ""
    for entry in memory["conversations"]:
        timestamp = entry.get("timestamp", "")
        time_str = ""
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                time_str = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] "
            except ValueError:
                pass
        conversation_context += f"{time_str}{entry['role']}: {entry['content']}\n"
    
    facts_context = json.dumps(memory["facts"]) if memory["facts"] else "{}"
    system_instruction = """You are Jarvis, a helpful AI assistant. Respond conversationally when activated.
Keep responses concise but helpful. Maintain context from previous interactions.
If you ask a question and don't get a response, don't repeat yourself.
Do NOT return code blocks or code formatting. Only reply in plain, spoken English.
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
    print("Restarting the program...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

import re

def clean_response(text):
    # Remove code blocks (triple backticks)
    text = re.sub(r"``````", "", text)
    # Remove inline code (single backticks)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Remove tool_code or similar markers
    text = re.sub(r"\btool_code\b", "", text, flags=re.IGNORECASE)
    # Extract content inside print("...") or print('...')
    match = re.search(r'print\(["\']([\s\S]+?)["\']\)', text)
    if match:
        text = match.group(1)
    # Replace escaped newlines (\n) with space
    text = text.replace("\\n", " ")
    # Replace real newlines with space
    text = re.sub(r'\s*\n\s*', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


def main():
    global active, waiting_for_response, last_interaction
    print("Jarvis is running in background. Say 'Jarvis'" )
    memory = load_memory()

    if platform.platform().lower() == "darwin":
        keyboard.add_hotkey('cmd+r', restart)
    else:
        keyboard.add_hotkey('ctrl+r', restart)

    while True:
        current_time = time.time()

        if waiting_for_response:
            user_input = listen(timeout=LISTEN_TIMEOUT, phrase_limit=10)
        else:
            user_input = listen(timeout=0.5, phrase_limit=3)

        if user_input:
            print("Recognized:", user_input)
            last_interaction = current_time

            if any(phrase in user_input.lower() for phrase in STOP_PHRASES):
                should_stop = True
                if active:
                    speak("Pausing as requested.")
                    active = False
                    waiting_for_response = False
                continue

            if not active and any(wake_word in user_input.lower() for wake_word in WAKE_WORDS):
                active = True
                waiting_for_response = True
                speak("Yes sir?")
                memory = add_to_memory_conversation(memory, "jarvis", "Yes sir?")
                continue

            if active:
                if any(phrase in user_input.lower() for phrase in SLEEP_PHRASES):
                    if speak("Understood. I'm going to sleep now."):
                        add_to_memory_conversation(memory, "jarvis", "Going to sleep.")
                        active = False
                        waiting_for_response = False
                    continue

                if user_input.lower().startswith("remember"):
                    try:
                        _, fact = user_input.split("remember", 1)
                        if " is " in fact:
                            key, value = fact.strip().split(" is ", 1)
                            memory["facts"][key.strip()] = value.strip()
                            save_memory(memory)
                            speak(f"Remembered: {key.strip()} is {value.strip()}")
                            waiting_for_response = True
                            continue
                    except Exception:
                        pass

                memory = add_to_memory_conversation(memory, "user", user_input)
                response = get_ai_response(user_input, memory)
                response = clean_response(response)
                memory = add_to_memory_conversation(memory, "jarvis", response)
                speak(response)

        elif waiting_for_response:
            if time.time() - last_interaction < INACTIVITY_TIMEOUT/2:
                continue
            else:
                if speak("I didn't catch that. I'll wait a bit longer..."):
                    last_interaction = time.time()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        os.system("cls" if os.name == "nt" else "clear")
        print('Jarvis terminated.')
