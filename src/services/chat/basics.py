from rich.panel import Panel
from rich.syntax import Syntax
from typing import AsyncIterable
from src.utils.basics import console
from src.utils.consumption import display_token_usage
import json, difflib, datetime, src.lib.globals as globals

def save_chat():
    # Generate filename.
    filename = f"Chat_{datetime.datetime.now().strftime("%H%M")}.md"
    # Format conversation history.
    formatted_chat = "# Marcus Copilot Chat Log\n\n"
    for message in globals.conversation_history:
        if message["role"] == "user": formatted_chat += f"## User\n\n{message["content"]}\n\n"
        elif message["role"] == "assistant":
            if isinstance(message["content"], str): formatted_chat += f"## Marcus\n\n{message["content"]}\n\n"
            elif isinstance(message["content"], list):
                for content in message["content"]:
                    if content["type"] == "tool_use": formatted_chat += f"### Tool Use: {content["name"]}\n\n```json\n{json.dumps(content["input"], indent=2)}\n```\n\n"
                    elif content["type"] == "text": formatted_chat += f"## Marcus\n\n{content["text"]}\n\n"
        elif message["role"] == "user" and isinstance(message["content"], list):
            for content in message["content"]:
                if content["type"] == "tool_result": formatted_chat += f"### Tool Result\n\n```\n{content["content"]}\n```\n\n"

    # Save to file.
    with open(filename, "w", encoding="utf-8") as f:
        f.write(formatted_chat)
    return filename

def reset_conversation():
    globals.conversation_history = []
    globals.main_model_tokens = {"input": 0, "output": 0}
    globals.tool_checker_tokens = {"input": 0, "output": 0}
    globals.code_editor_tokens = {"input": 0, "output": 0}
    globals.code_execution_tokens = {"input": 0, "output": 0}
    globals.file_contents = {}
    globals.code_editor_files = set()
    reset_code_editor_memory()
    console.print(Panel("Conversation history, token counts, file contents, code editor memory, and code editor files have been reset.", title="Reset", style="bold green"))
    display_token_usage()

async def text_chunker(text: str) -> AsyncIterable[str]:
    # Split text into chunks, ensuring to not break sentences.
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""
    for char in text:
        if buffer.endswith(splitters):
            yield buffer + " "
            buffer = char
        elif char in splitters:
            yield buffer + char + " "
            buffer = ""
        else: buffer += char
    if buffer: yield buffer + " "

def reset_code_editor_memory():
    globals.code_editor_memory = []
    console.print(Panel("Code editor memory has been reset.", title="Reset", style="bold green"))

def generate_diff(original, new, path):
    return Syntax(("".join(list(difflib.unified_diff(
        original.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3
    )))), "diff", theme="monokai", line_numbers=True)