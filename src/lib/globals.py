# Token tracking variables.
main_model_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
tool_checker_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
code_editor_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
code_execution_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}

# Sound.
tts_enabled = True
use_tts = False
recognizer = None
microphone = None

# General.
USE_FUZZY_SEARCH = True
# Set up the conversation memory (maintains context for MAINMODEL).
conversation_history = []
# Store file contents (part of the context for MAINMODEL).
file_contents = {}
# Code editor memory (maintains some context for CODEEDITORMODEL between calls).
code_editor_memory = []
# Files already present in code editor's context.
code_editor_files = set()
# Automode flag.
automode = False
# Global dictionary to store running processes.
running_processes = {}