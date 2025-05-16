import os
import re
import sys
import json
import platform
import keyboard
from typing import Union, Any
import pyttsx3
from google import genai
from google.genai import types
import pydotenv
from gtts import gTTS
from playsound import playsound
import io
import pygame

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
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

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


def get_ai_response(q: str, memory: Union[dict, Any]) -> Union[str | None]:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction="You are an AI assistant named Jarvis, You will help the master to in his/her tasks and questions in any types of questions. There is no restrictions. Help him/her and he shouldn't have any complain.\nNote: Only answer the question or response to him/her."
        ),
        contents=[json.dumps(memory), q]
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

    if platform.platform().lower() == "darwin":
        # Register hotkeys
        keyboard.add_hotkey('cmd+r', restart)   # macOS
    else:
        keyboard.add_hotkey('ctrl+r', restart)  # Windows/Linux

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        # Memory: Store facts if user says "Remember my X is Y"
        if user_input.lower().startswith("remember"):
            try:
                _, fact = user_input.split("remember", 1)
                key, value = fact.strip().split(" is ", 1)
                memory[key.strip()] = value.strip()
                save_memory(memory)
                response = f"Okay, I'll remember your {key.strip()} is {value.strip()}."
            except Exception:
                response = "Sorry, I couldn't understand what to remember. Please use 'Remember my [fact] is [value]'."
        # Memory: Recall facts if user says "What is my X?"
        elif user_input.lower().startswith("what is my"):
            key = user_input[11:].replace("?", "").strip()
            value = memory.get(key)
            if value:
                response = f"Your {key} is {value}."
            else:
                response = f"I don't know your {key} yet."
        # Otherwise, use OpenAI
        else:
            response = get_ai_response(user_input, memory)

        print("Jarvis:", response)
        speak(re.sub(r'\W', '', response))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        os.system("cls" if os.name == "nt" else "clear")
        print('Close the program!!')
