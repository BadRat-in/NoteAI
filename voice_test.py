from gtts import gTTS
import os

tts = gTTS(text="Hey! How are you doing today?", lang='en')
tts.save("speech.mp3")
os.system("start speech.mp3")  # Use "afplay" on macOS, "mpg123" on Linux
