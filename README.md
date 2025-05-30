# 📝 NoteAI

**NoteAI** is a voice-first personal assistant that captures timestamped notes, conversations, and logs using your voice — without typing. It listens passively (or with a wake word) and saves your thoughts in real time.

> “What did I say during the meeting yesterday?”  
> “Summarize my work notes from last week.”  
> **NoteAI makes it possible.**

---

## 🚀 Features

- 🎙️ Passive voice listening with wake word (default: `Hey NoteAI`)
- 🧠 Uses Gemini AI for contextual understanding and replies
- 📝 Saves timestamped notes in a memory file (`memory.json`)
- 🔊 Voice response using text-to-speech
- 🧪 Basic file summarization demo
- ⌨️ Hotkey restart support (e.g. `Cmd+R`)

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.8+
- Microphone access
- Google Gemini API key

### 2. Install Dependencies

  ```bash
  pip install -r requirements.txt
  ````

### 3. Add Environment Variable

  Create a `.env` file:

  ```
  GEMINI_API_KEY=your_google_api_key
  ```

### 4. Run the App

  ```bash
  python main.py
  ```

---

## 🧭 Keyboard Shortcuts

- `Cmd+R` (macOS) or `Ctrl+R` (Windows/Linux): Restart the assistant

---

## 📁 File Structure

```bash
noteai/
├── main.py            # Main assistant logic
├── memory.json        # Saved conversation logs
├── .env               # Environment variables
├── requirements.txt   # Dependencies
└── README.md          # Documentation
```

---

## 📌 Customize Wake Word

You can change the wake word from `jarvis` to something else (e.g., `note ai`) in `main.py`:

```python
WAKE_WORDS = ["Hey NoteAI", "Note AI"]
```
