from src.lib.config import config
from src.services.chat.loader import TermLoading
import os, importlib, src.lib.globals as globals
from src.utils.basics import terminal

def get_function(module_name, function_name="main"):
    return getattr(importlib.import_module(f"src.services.ai.models.{module_name}.worker"), function_name)

async def chat_with_ai(user_input, image_path=None, current_iteration=None, max_iterations=None):
    animation: TermLoading = TermLoading()
    animation.show("Thinking...", finish_message="", failed_message="Failed!❌😨😨")
    if config.ai.default_provider == "anthropic":
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        if not ANTHROPIC_API_KEY: terminal("e", "ANTHROPIC_API_KEY not found in environment variables.", exitScript=True)
        else:
            get_function("anthropic")(ANTHROPIC_API_KEY)
            await get_function("anthropic", "chat_with_claude")(user_input, image_path=None, current_iteration=None, max_iterations=None)
            animation.finished = True
    if config.ai.default_provider == "ollama":
        get_function("ollama")()
        await get_function("ollama", "chat_with_ollama")(user_input, image_path=None, current_iteration=None, max_iterations=None)
        animation.finished = True
    else: return terminal("e", "Invalid provider, please check your configuration.", exitScript=True)