import os, getpass, asyncio
from rich.panel import Panel
from dotenv import load_dotenv
from tavily import TavilyClient
from rich.console import Console
import src.lib.globals as globals
from prompt_toolkit.styles import Style
from prompt_toolkit import PromptSession
from src.utils.basics import cls, terminal
import src.services.voice.worker as voice_main
from src.services.voice.test import test_voice_mode
from src.services.ai.models.worker import chat_with_ai
from src.services.chat.basics import save_chat, reset_conversation

load_dotenv()

# 11 Labs TTS.
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
VOICE_ID = "YOUR VOICE ID"
MODEL_ID = "eleven_turbo_v2_5"

async def get_user_input(prompt="You: "):
    return await PromptSession(style=Style.from_dict({ "prompt": "cyan bold" })).prompt_async(prompt, multiline=False)

# Initialize the Tavily client.
tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key: terminal("e", "TAVILY_API_KEY not found in environment variables", exitScript=True)
tavily = TavilyClient(api_key=tavily_api_key)

console = Console()

async def main():
    global use_tts, tts_enabled
    console.print(Panel("Welcome to the Marcus Copilot Chat with Multi-Agent, Image, Voice, and Text-to-Speech Support!", title=f"Welcome {getpass.getuser()}", style="bold green"))
    console.print("Type 'exit' to end the conversation.")
    console.print("Type 'image' to include an image in your message.")
    console.print("Type 'voice' to enter voice input mode.")
    console.print("Type 'test voice' to run a voice input test.")
    console.print("Type 'automode [number]' to enter Autonomous mode with a specific number of iterations.")
    console.print("Type 'reset' to clear the conversation history.")
    console.print("Type 'save chat' to save the conversation to a Markdown file.")
    console.print("Type '11labs on' to enable text-to-speech.")
    console.print("Type '11labs off' to disable text-to-speech.")
    console.print("While in automode, press Ctrl+C at any time to exit the automode to return to regular chat.")
    voice_mode = False
    while True:
        if voice_mode:
            user_input = await voice_main.voice_input()
            if user_input is None:
                voice_mode = False
                voice_main.cleanup_speech_recognition()
                console.print(Panel("Exited voice input mode due to error. Returning to text input.", style="bold yellow"))
                continue
            stay_in_voice_mode, command_result = voice_main.process_voice_command(user_input)
            if not stay_in_voice_mode:
                voice_mode = False
                voice_main.cleanup_speech_recognition()
                console.print(Panel("Exited voice input mode. Returning to text input.", style="bold green"))
                if command_result: console.print(Panel(command_result, style="cyan"))
                continue
            elif command_result:
                console.print(Panel(command_result, style="cyan"))
                continue
        else: user_input = await get_user_input()
        if user_input.lower() == "exit":
            console.print(Panel("Thanks for chatting, see you next time!", title_align="left", title="Goodbye", style="bold green"))
            break
        if user_input.lower() == "test voice":
            await test_voice_mode()
            continue
        if user_input.lower() == "11labs on":
            use_tts = True
            tts_enabled = True
            console.print(Panel("Text-to-speech enabled.", style="bold green"))
            continue
        if user_input.lower() == "11labs off":
            use_tts = False
            tts_enabled = False
            console.print(Panel("Text-to-speech disabled.", style="bold yellow"))
            continue
        if user_input.lower() == "reset":
            reset_conversation()
            continue
        if user_input.lower() == "save chat":
            filename = save_chat()
            console.print(Panel(f"Chat saved to {filename}", title="Chat Saved", style="bold green"))
            continue
        if user_input.lower() == "voice":
            voice_mode = True
            voice_main.initialize_speech_recognition()
            console.print(Panel("Entering voice input mode. Say 'exit voice mode' to return to text input.", style="bold green"))
            continue
        if user_input.lower() == "image":
            image_path = (await get_user_input("Drag and drop your image here, then press enter: ")).strip().replace("'", "")
            if os.path.isfile(image_path):
                user_input = await get_user_input("You (prompt for image): ")
                response, _ = await chat_with_ai(user_input, image_path)
            else:
                console.print(Panel("Invalid image path. Please try again.", title="Error", style="bold red"))
                continue
        elif user_input.lower().startswith("automode"):
            try:
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit(): max_iterations = int(parts[1])
                else: max_iterations = 25
                globals.automode = True
                console.print(Panel(f"Entering automode with {max_iterations} iterations. Please provide the goal of the automode.", title_align="left", title="Automode", style="bold yellow"))
                console.print(Panel("Press Ctrl+C at any time to exit the automode loop.", style="bold yellow"))
                user_input = await get_user_input()
                iteration_count = 0
                error_count = 0
                max_errors = 3 # Maximum number of consecutive errors before exiting automode.
                try:
                    while globals.automode and iteration_count < max_iterations:
                        try:
                            response, exit_continuation = await chat_with_ai(user_input, current_iteration=iteration_count+1, max_iterations=max_iterations)
                            error_count = 0 # Reset error count on successful iteration.
                        except Exception as e:
                            console.print(Panel(f"Error in automode iteration: {str(e)}", style="bold red"))
                            error_count += 1
                            if error_count >= max_errors:
                                console.print(Panel(f"Exiting automode due to {max_errors} consecutive errors.", style="bold red"))
                                globals.automode = False
                                break
                            continue
                        if exit_continuation or "AUTOMODE_COMPLETE" in response:
                            console.print(Panel("Automode completed.", title_align="left", title="Automode", style="green"))
                            globals.automode = False
                        else:
                            console.print(Panel(f"Continuation iteration {iteration_count + 1} completed. Press Ctrl+C to exit automode. ", title_align="left", title="Automode", style="yellow"))
                            user_input = "Continue with the next step. Or STOP by saying 'AUTOMODE_COMPLETE' if you think you've achieved the results established in the original request."
                        iteration_count += 1
                        if iteration_count >= max_iterations:
                            console.print(Panel("Max iterations reached. Exiting automode.", title_align="left", title="Automode", style="bold red"))
                            globals.automode = False
                except KeyboardInterrupt:
                    console.print(Panel("\nAutomode interrupted by user. Exiting automode.", title_align="left", title="Automode", style="bold red"))
                    globals.automode = False
                    if globals.conversation_history and globals.conversation_history[-1]["role"] == "user": globals.conversation_history.append({"role": "assistant", "content": "Automode interrupted. How can I assist you further?"})
            except KeyboardInterrupt:
                console.print(Panel("\nAutomode interrupted by user. Exiting automode.", title_align="left", title="Automode", style="bold red"))
                globals.automode = False
                if globals.conversation_history and globals.conversation_history[-1]["role"] == "user": globals.conversation_history.append({"role": "assistant", "content": "Automode interrupted. How can I assist you further?"})
            console.print(Panel("Exited automode. Returning to regular chat.", style="green"))
        else: response, _ = await chat_with_ai(user_input)

if __name__ == "__main__":
    cls()
    try: asyncio.run(main())
    except KeyboardInterrupt: console.print("\nProgram interrupted by user. Exiting...", style="bold red")
    except Exception as e: terminal("e", f"An unexpected error occurred: {str(e)}")
    finally: console.print("Program finished. Goodbye!", style="bold green")