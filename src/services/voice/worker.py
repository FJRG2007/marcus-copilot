from pydub import AudioSegment
from pydub.playback import play
from src.utils.basics import console, terminal
from src.services.chat.basics import save_chat, reset_conversation
import io, shutil, asyncio, subprocess, src.lib.globals as globals, speech_recognition as sr

def initialize_speech_recognition():
    globals.recognizer = sr.Recognizer()
    globals.microphone = sr.Microphone()
    
    # Adjust for ambient noise.
    with globals.microphone as source:
        globals.recognizer.adjust_for_ambient_noise(source, duration=1)

# Define a list of voice commands.
VOICE_COMMANDS = {
    "exit voice mode": "exit_voice_mode",
    "save chat": "save_chat",
    "reset conversation": "reset_conversation"
}

def process_voice_command(command):
    if command in VOICE_COMMANDS:
        action = VOICE_COMMANDS[command]
        if action == "exit_voice_mode": return False, "Exiting voice mode."
        elif action == "save_chat": return True, f"Chat saved to {save_chat()}"
        elif action == "reset_conversation":
            reset_conversation()
            return True, "Conversation has been reset."
    return True, None

def cleanup_speech_recognition():
    globals.recognizer = None
    globals.microphone = None

async def voice_input(max_retries=3):
    for attempt in range(max_retries):
        # Reinitialize speech recognition objects before each attempt.
        initialize_speech_recognition()
        try:
            with globals.microphone as source:
                console.print("Listening... Speak now.", style="bold green")
                audio = globals.recognizer.listen(source, timeout=5)
            console.print("Processing speech...", style="bold yellow")
            text = globals.recognizer.recognize_google(audio)
            console.print(f"You said: {text}", style="cyan")
            return text.lower()
        except sr.WaitTimeoutError: console.print(f"No speech detected. Attempt {attempt + 1} of {max_retries}.", style="bold red")
        except sr.UnknownValueError: console.print(f"Speech was unintelligible. Attempt {attempt + 1} of {max_retries}.", style="bold red")
        except sr.RequestError as e:
            console.print(f"Could not request results from speech recognition service; {e}", style="bold red")
            return None
        except Exception as e:
            terminal("e", f"Unexpected error in voice input: {str(e)}")
            return None
        # Add a short delay between attempts.
        await asyncio.sleep(1)
    terminal("e", "Max retries reached. Returning to text input mode.")
    return None

async def stream_audio(audio_stream):
    # Stream audio data using mpv player.
    if not shutil.which("mpv") is not None:
        console.print("mpv not found. Installing alternative audio playback...", style="bold yellow")
        # Fall back to pydub playback if mpv is not available.
        play(AudioSegment.from_mp3(io.BytesIO(b"".join([chunk async for chunk in audio_stream]))))
        return

    mpv_process = subprocess.Popen(["mpv", "--no-cache", "--no-terminal", "--", "fd://0"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,)

    console.print("Started streaming audio", style="bold green")
    try:
        async for chunk in audio_stream:
            if chunk:
                mpv_process.stdin.write(chunk)
                mpv_process.stdin.flush()
    except Exception as e: terminal("e", f"Error during audio streaming: {str(e)}")
    finally:
        if mpv_process.stdin: mpv_process.stdin.close()
        mpv_process.wait()