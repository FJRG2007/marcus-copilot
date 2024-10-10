from rich.panel import Panel
from src.utils.basics import console
from src.services.voice.worker import voice_input, process_voice_command, cleanup_speech_recognition, initialize_speech_recognition

async def test_voice_mode():
    global voice_mode
    voice_mode = True
    initialize_speech_recognition()
    console.print(Panel("Entering voice input test mode. Say a few phrases, then say 'exit voice mode' to end the test.", style="bold green"))
    while voice_mode:
        user_input = await voice_input()
        if user_input is None:
            voice_mode = False
            cleanup_speech_recognition()
            console.print(Panel("Exited voice input test mode due to error.", style="bold yellow"))
            break
        stay_in_voice_mode, command_result = process_voice_command(user_input)
        if not stay_in_voice_mode:
            voice_mode = False
            cleanup_speech_recognition()
            console.print(Panel("Exited voice input test mode.", style="bold green"))
            break
        elif command_result: console.print(Panel(command_result, style="cyan"))
    console.print(Panel("Voice input test completed.", style="bold green"))