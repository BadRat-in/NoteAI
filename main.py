import os
import re
import sys
import json
import platform
import keyboard
from typing import Union, Dict
import pyttsx3
from google import genai
from google.genai import types
import datetime
import speech_recognition as sr
import threading
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# --- File Path Creation and Validation ---
def create_file_path(filename: str, directory: str) -> str:
    special_dirs = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    }
    dir_key = directory.strip().lower()
    resolved_dir = special_dirs.get(dir_key, directory)
    resolved_dir = os.path.expandvars(os.path.expanduser(resolved_dir))
    if not isinstance(resolved_dir, str) or not resolved_dir.strip():
        return "Error: Directory must be a non-empty string."
    if not os.path.isdir(resolved_dir):
        return f"Error: Directory '{resolved_dir}' does not exist."
    if not isinstance(filename, str) or not filename.strip():
        return "Error: Filename must be a non-empty string."
    if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename):
        return "Error: Filename should not contain path separators."
    if re.search(r'[<>:"/\\|?*]', filename):
        return "Error: Filename contains invalid characters."
    full_path = os.path.join(resolved_dir, filename)
    return full_path


# --- Progress Bar Utility ---
def print_progress_bar(
    iteration, total, prefix="", suffix="", decimals=1, length=30, fill="█"
):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end="\r")
    if iteration >= total:
        print()


# --- File Read with Progress ---
def read_file_with_progress(file_path):
    try:
        file_size = os.path.getsize(file_path)
        chunk_size = 4096
        content = ""
        with open(file_path, "r", encoding="utf-8") as f:
            read_bytes = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                content += chunk
                read_bytes += len(chunk.encode("utf-8"))
                print_progress_bar(
                    read_bytes, file_size, prefix="Reading", suffix="Complete"
                )
        return content
    except Exception as e:
        return f"Error reading file: {e}"


# --- Config ---
MEMORY_FILE = "memory.json"
WAKE_WORDS = ["Hey NoteAI", "NoteAI"]
SLEEP_PHRASES = ["go to sleep", "that's all", "goodbye", "exit", "stop"]
STOP_PHRASES = ["stop", "pause", "quiet"]
LISTEN_TIMEOUT = 10
INACTIVITY_TIMEOUT = 10

# Global flags
speaking = False
should_stop = False
active = False
waiting_for_response = False
last_interaction = 0

engine = pyttsx3.init()
engine.setProperty("rate", 180)

# --- gemini Chat Function ---
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# --- Memory Functions ---
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"facts": {}, "conversations": []}

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


def save_memory(memory):
    if len(memory["conversations"]) % 3 == 0:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)


def add_to_memory_conversation(memory: Dict, role: str, content: str):
    memory["conversations"].append(
        {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    )
    save_memory(memory)
    return memory


# --- Speech Recognition ---
def listen(timeout=3, phrase_limit=5):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        try:
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_limit
            )
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
    system_instruction = """You are NoteAI, a helpful AI assistant. Respond conversationally when activated.
Keep responses concise but helpful. Maintain context from previous interactions.
If you ask a question and don't get a response, don't repeat yourself.
Do NOT return code blocks or code formatting. Only reply in plain, spoken English.
"""
    full_context = (
        "CONVERSATION HISTORY:\n"
        + conversation_context
        + "\n\nUSER FACTS:\n"
        + facts_context
        + "\n\nCurrent query: "
        + q
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(system_instruction=system_instruction),
        contents=full_context,
    )

    return response.text


def restart():
    print("Restarting the program...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)


def clean_response(text):
    text = re.sub(r"``````", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\btool_code\b", "", text, flags=re.IGNORECASE)
    match = re.search(r'print\(["\']([\s\S]+?)["\']\)', text)
    if match:
        text = match.group(1)
    text = text.replace("\\n", " ")
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


# --- Source Code Reading with Progress ---
def read_source_code(file_path="main.py"):
    return read_file_with_progress(file_path)


# --- NEW FUNCTION: Read all files on Desktop ---
def hello_amit_suthar():
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop_path):
        print("Desktop directory does not exist.")
        return
    files = [
        f
        for f in os.listdir(desktop_path)
        if os.path.isfile(os.path.join(desktop_path, f))
    ]
    if not files:
        print("No files found on Desktop.")
        return
    print("Files on your Desktop:")
    for filename in files:
        file_path = os.path.join(desktop_path, filename)
        print(f"\n--- {filename} ---")
        try:
            content = read_file_with_progress(file_path)
            print(content)
        except Exception as e:
            print(f"Could not read {filename}: {e}")


# --- MAIN LOOP ---
def main():
    print("Jarvis is always listening. Just speak your command.")
    memory = load_memory()
    if platform.platform().lower() == "darwin":
        keyboard.add_hotkey("cmd+r", restart)
    else:
        keyboard.add_hotkey("ctrl+r", restart)

    while True:
        user_input = listen(timeout=LISTEN_TIMEOUT, phrase_limit=10)
        if user_input:
            print("Recognized:", user_input)
            memory = add_to_memory_conversation(memory, "user", user_input)

            # --- Custom Hello Amit Suthar Command ---
            if "hello amit suthar" in user_input.lower():
                hello_amit_suthar()
                speak(
                    "Read all files on your desktop and printed their contents in the terminal."
                )
                continue

            # Handle stop/exit commands
            if any(
                phrase in user_input.lower() for phrase in STOP_PHRASES + SLEEP_PHRASES
            ):
                speak("Pausing as requested. Say something to continue.")
                continue

            # Handle 'remember' commands
            if user_input.lower().startswith("remember"):
                try:
                    _, fact = user_input.split("remember", 1)
                    if " is " in fact:
                        key, value = fact.strip().split(" is ", 1)
                        memory["facts"][key.strip()] = value.strip()
                        save_memory(memory)
                        speak(f"Remembered: {key.strip()} is {value.strip()}")
                        continue
                except Exception:
                    pass

            # --- Source Code Q&A with Progress ---
            if (
                "source code" in user_input.lower()
                or "your code" in user_input.lower()
                or "explain your code" in user_input.lower()
            ):
                speak("Reading my source code, please wait.")
                source_code = read_source_code(
                    "main.py"
                )  # Change to your script filename if needed
                prompt = (
                    f"This is my source code:\n{source_code}\n\n"
                    f"User question: {user_input}\n"
                    "Please answer or explain based on the code above."
                )
                response = get_ai_response(prompt, memory)
                response = clean_response(response)
                memory = add_to_memory_conversation(memory, "jarvis", response)
                speak(response)
                continue

            response = get_ai_response(user_input, memory)
            response = clean_response(response)
            memory = add_to_memory_conversation(memory, "jarvis", response)
            speak(response)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        os.system("cls" if os.name == "nt" else "clear")
        print("Jarvis terminated.")
