import os, json, base64, asyncio, websockets
import src.services.voice.worker as voice_main
from src.services.chat.basics import text_chunker
from src.utils.basics import logging, console, terminal

VOICE_ID = "YOUR VOICE ID"
MODEL_ID = "eleven_turbo_v2_5"

async def text_to_speech(text):
    ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
    if not ELEVEN_LABS_API_KEY: return terminal("e", "ElevenLabs API key not found. Text-to-speech is disabled.")
    try:
        async with websockets.connect(f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}", extra_headers={"xi-api-key": ELEVEN_LABS_API_KEY}) as websocket:
            # Send initial message.
            await websocket.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                "xi_api_key": ELEVEN_LABS_API_KEY
            }))
            # Set up listener for audio chunks.
            async def listen():
                while True:
                    try:
                        data = json.loads(await websocket.recv())
                        if data.get("audio"): yield base64.b64decode(data["audio"])
                        elif data.get("isFinal"): break
                    except websockets.exceptions.ConnectionClosed:
                        logging.error("WebSocket connection closed unexpectedly")
                        break
                    except Exception as e:
                        logging.error(f"Error processing audio message: {str(e)}")
                        break
            # Start audio streaming task.
            stream_task = asyncio.create_task(voice_main.stream_audio(listen()))
            # Send text in chunks.
            async for chunk in text_chunker(text):
                try: await websocket.send(json.dumps({"text": chunk, "try_trigger_generation": True}))
                except Exception as e:
                    logging.error(f"Error sending text chunk: {str(e)}")
                    break
            # Send closing message.
            await websocket.send(json.dumps({"text": ""}))
            # Wait for streaming to complete.
            await stream_task
    except websockets.exceptions.InvalidStatusCode as e:
        terminal("e", f"Failed to connect to ElevenLabs API: {e}", style="bold red")
        console.print("Fallback: Printing the text instead.", style="bold yellow")
        console.print(text)
    except Exception as e:
        terminal("e", f"Error in text-to-speech: {str(e)}", style="bold red")
        console.print("Fallback: Printing the text instead.", style="bold yellow")
        console.print(text)