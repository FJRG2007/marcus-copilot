from rich.panel import Panel
from src.lib.config import config
from rich.markdown import Markdown
import json, time, src.lib.globals as globals
from src.utils.basics import console, terminal
from src.utils.local.terminal import execute_tool
from src.utils.consumption import display_token_usage
from src.services.ai.prompts.tools.type2 import get_tools
from anthropic import Anthropic, APIStatusError, APIError
from src.utils.local.worker import edit_and_apply_multiple
from src.services.ai.prompts.worker import update_system_prompt
from src.services.image.converter import encode_image_to_base64
from src.services.voice.text_to_speech.worker import text_to_speech
from src.services.ai.prompts.worker import decide_retry, generate_instructions_prompt

client = None

def main(ANTHROPIC_API_KEY):
    global client
    # Initialize the Anthropic client.
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

async def chat_with_claude(user_input, image_path=None, current_iteration=None, max_iterations=None):
    # Input validation.
    if not isinstance(user_input, str): terminal("e", "user_input must be a string", exitScript=True)
    if image_path is not None and not isinstance(image_path, str): terminal("e", "image_path must be a string or None", exitScript=True)
    if current_iteration is not None and not isinstance(current_iteration, int): terminal("e", "current_iteration must be an integer or None", exitScript=True)
    if max_iterations is not None and not isinstance(max_iterations, int): terminal("e", "max_iterations must be an integer or None", exitScript=True)
    globals.current_conversation = []
    if image_path:
        console.print(Panel(f"Processing image at path: {image_path}", title_align="left", title="Image Processing", expand=False, style="yellow"))
        image_base64 = encode_image_to_base64(image_path)
        if image_base64.startswith("Error"):
            console.print(Panel(f"Error encoding image: {image_base64}", title="Error", style="bold red"))
            return "I'm sorry, there was an error processing the image. Please try again.", False
        image_message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": f"User input for image: {user_input}"
                }
            ]
        }
        globals.current_conversation.append(image_message)
        console.print(Panel("Image message added to conversation history", title_align="left", title="Image Added", style="green"))
    else: globals.current_conversation.append({"role": "user", "content": user_input})
    # Filter conversation history to maintain context.
    filtered_conversation_history = []
    for message in globals.conversation_history:
        if isinstance(message["content"], list):
            filtered_content = [
                content for content in message["content"]
                if content.get("type") != "tool_result" or (
                    content.get("type") == "tool_result" and
                    not any(keyword in content.get("output", "") for keyword in [
                        "File contents updated in system prompt",
                        "File created and added to system prompt",
                        "has been read and stored in the system prompt"
                    ])
                )
            ]
            if filtered_content: filtered_conversation_history.append({**message, "content": filtered_content})
        else: filtered_conversation_history.append(message)
    # Combine filtered history with current conversation to maintain context.
    messages = filtered_conversation_history + globals.current_conversation
    max_retries = 3
    retry_delay = 5
    tools = get_tools()
    for attempt in range(max_retries):
        try:
            # MAINMODEL call with prompt caching.
            response = client.beta.prompt_caching.messages.create(
                model=config.ai.providers.anthropic.models.main_model,
                max_tokens=8000,
                system=[
                    {
                        "type": "text",
                        "text": update_system_prompt(current_iteration, max_iterations),
                        "cache_control": {"type": "ephemeral"}
                    },
                    {
                        "type": "text",
                        "text": json.dumps(tools),
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )
            # Update token usage for MAINMODEL.
            globals.main_model_tokens["input"] += response.usage.input_tokens
            globals.main_model_tokens["output"] += response.usage.output_tokens
            globals.main_model_tokens["cache_write"] = response.usage.cache_creation_input_tokens
            globals.main_model_tokens["cache_read"] = response.usage.cache_read_input_tokens
            break # If successful, break out of the retry loop.
        except APIStatusError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                console.print(Panel(f"Rate limit exceeded. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})", title="API Error", style="bold yellow"))
                time.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff.
            else:
                console.print(Panel(f"API Error: {str(e)}", title="API Error", style="bold red"))
                return "I'm sorry, there was an error communicating with the AI. Please try again.", False
        except APIError as e:
            console.print(Panel(f"API Error: {str(e)}", title="API Error", style="bold red"))
            return "I'm sorry, there was an error communicating with the AI. Please try again.", False
    else:
        console.print(Panel("Max retries reached. Unable to communicate with the AI.", title="Error", style="bold red"))
        return "I'm sorry, there was a persistent error communicating with the AI. Please try again later.", False
    assistant_response = ""
    exit_continuation = False
    tool_uses = []
    for content_block in response.content:
        if content_block.type == "text":
            assistant_response += content_block.text
            if "AUTOMODE_COMPLETE" in content_block.text: exit_continuation = True
        elif content_block.type == "tool_use": tool_uses.append(content_block)
    terminal("ai", assistant_response)
    if globals.tts_enabled and globals.use_tts: await text_to_speech(assistant_response)
    # Display files in context.
    if globals.file_contents: 
        globals.files_in_context = "\n".join(globals.file_contents.keys())
        console.print(Panel(globals.files_in_context, title="Files in Context", title_align="left", border_style="white", expand=False))
    else: globals.files_in_context = "No files in context. Read, create, or edit files to add."
    for tool_use in tool_uses:
        tool_name = tool_use.name
        tool_input = tool_use.input
        tool_use_id = tool_use.id
        console.print(Panel(f"Tool Used: {tool_name}", style="green"))
        console.print(Panel(f"Tool Input: {json.dumps(tool_input, indent=2)}", style="green"))
        # Always use execute_tool for all tools.
        tool_result = await execute_tool(tool_name, tool_input)
        if isinstance(tool_result, dict) and tool_result.get("is_error"):
            console.print(Panel(tool_result["content"], title="Tool Execution Error", style="bold red"))
            edit_results = [] # Assign empty list due to error.
        else: edit_results = tool_result.get("content", [])
        # Prepare the tool_result_content for conversation history.
        tool_result_content = {
            "type": "text",
            "text": json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        }
        globals.current_conversation.append({
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": tool_name,
                    "input": tool_input
                }
            ]
        })
        globals.current_conversation.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": [tool_result_content],
                    "is_error": tool_result.get("is_error", False) if isinstance(tool_result, dict) else False
                }
            ]
        })
        # Update the file_contents dictionary if applicable.
        if tool_name in ["create_files", "edit_and_apply_multiple", "read_multiple_files"] and not (isinstance(tool_result, dict) and tool_result.get("is_error")):
            if tool_name == "create_files":
                for file in tool_input["files"]:
                    if "File created and added to system prompt" in str(tool_result): globals.file_contents[file["path"]] = file["content"]
            elif tool_name == "edit_and_apply_multiple":
                edit_results = tool_result if isinstance(tool_result, list) else [tool_result]
                for result in edit_results:
                    if isinstance(result, dict) and result.get("status") in ["success", "partial_success"]: globals.file_contents[result["path"]] = result.get("edited_content", globals.file_contents.get(result["path"], ""))
            elif tool_name == "read_multiple_files": pass
        messages = filtered_conversation_history + globals.current_conversation
        try:
            tool_response = client.messages.create(
                model=config.ai.providers.anthropic.models.main_model,
                max_tokens=8000,
                system=update_system_prompt(current_iteration, max_iterations),
                extra_headers={"anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"},
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"}
            )
            # Update token usage for tool checker.
            globals.tool_checker_tokens["input"] += tool_response.usage.input_tokens
            globals.tool_checker_tokens["output"] += tool_response.usage.output_tokens
            tool_checker_response = ""
            for tool_content_block in tool_response.content:
                if tool_content_block.type == "text": tool_checker_response += tool_content_block.text
            console.print(Panel(Markdown(tool_checker_response), title="Marcus's Response to Tool Result",  title_align="left", border_style="blue", expand=False))
            if globals.use_tts: await text_to_speech(tool_checker_response)
            assistant_response += "\n\n" + tool_checker_response
            # If the tool was edit_and_apply_multiple, let the AI decide whether to retry.
            if tool_name == "edit_and_apply_multiple":
                retry_decision = await decide_retry(tool_checker_response, edit_results, tool_input)
                if retry_decision["retry"] and retry_decision["files_to_retry"]:
                    console.print(Panel(f"AI has decided to retry editing for files: {', '.join(retry_decision["files_to_retry"])}", style="yellow"))
                    retry_files = [ file for file in tool_input["files"] if file["path"] in retry_decision["files_to_retry"]]
                    # Ensure 'instructions' are present.
                    for file in retry_files:
                        if "instructions" not in file: file["instructions"] = "Please reapply the previous instructions."
                    if retry_files:
                        retry_result, retry_console_output = await edit_and_apply_multiple(
                            client.beta.prompt_caching.messages.create(
                                model=config.ai.providers.anthropic.models.code_editor_model,
                                max_tokens=8000,
                                system=[
                                    {
                                        "type": "text",
                                        "text": generate_instructions_prompt(),
                                        "cache_control": {"type": "ephemeral"}
                                    }
                                ],
                                messages=[
                                    {"role": "user", "content": "Generate SEARCH/REPLACE blocks for the necessary changes."}
                                ],
                                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
                            ), retry_files, tool_input["project_context"])
                        console.print(Panel(retry_console_output, title="Retry Result", style="cyan"))
                        assistant_response += f"\n\nRetry result: {json.dumps(retry_result, indent=2)}"
                    else: console.print(Panel("No files to retry. Skipping retry.", style="yellow"))
                else: console.print(Panel("Marcus has decided not to retry editing", style="green"))
        except APIError as e:
            error_message = f"Error in tool response: {str(e)}"
            console.print(Panel(error_message, title="Error", style="bold red"))
            assistant_response += f"\n\n{error_message}"
    if assistant_response: globals.current_conversation.append({"role": "assistant", "content": assistant_response})
    globals.conversation_history = messages + [{"role": "assistant", "content": assistant_response}]
    # Display token usage at the end.
    display_token_usage()
    return assistant_response, exit_continuation