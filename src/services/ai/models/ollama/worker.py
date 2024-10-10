

from rich.panel import Panel
from src.lib.config import config
from rich.markdown import Markdown
from src.utils.basics import console, terminal
from src.utils.local.terminal import execute_tool
from src.services.ai.prompts.worker import update_system_prompt
import json, re, ollama, subprocess, src.services.ai.prompts.tools.type1 as tools, src.lib.globals as globals

client = None

def main():
    global client
    # Initialize the Ollama client.
    client = ollama.AsyncClient()

def parse_goals(response):
    return re.findall(r'Goal \d+: (.+)', response)

async def execute_goals(goals):
    global automode
    for i, goal in enumerate(goals, 1):
        console.print(Panel(f"Executing Goal {i}: {goal}", title="Goal Execution", style="bold yellow"))
        response, _ = await chat_with_ollama(f"Continue working on goal: {goal}")
        if "AUTOMODE_COMPLETE" in response:
            automode = False
            console.print(Panel("Exiting automode.", title="Automode", style="bold green"))
            break

async def run_goals(response):
    await execute_goals(parse_goals(response))

async def chat_with_ollama(user_input, image_path=None, current_iteration=None, max_iterations=None):
    # This function uses MAINMODEL, which maintains context across calls.
    globals.current_conversation = []
    globals.current_conversation.append({"role": "user", "content": user_input})
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
    sft_tools = tools.get_tools()
    try:
        # MAINMODEL call, which maintains context.
        # Prepend the system message to the messages list.
        system_message = {"role": "system", "content": update_system_prompt(current_iteration, max_iterations)}
        messages_with_system = [system_message] + messages
        response = await client.chat(
            model=config.ai.providers.ollama.models.main_model,
            messages=messages_with_system,
            tools=sft_tools,
            stream=False
        )
        # Check if the response is a dictionary.
        if isinstance(response, dict):
            if "error" in response:
                console.print(Panel(f"Error: {response["error"]}", title="API Error", style="bold red"))
                return f"I'm sorry, but there was an error with the model response: {response["error"]}", False
            elif "message" in response:
                assistant_message = response["message"]
                assistant_response = assistant_message.get("content", "")
                exit_continuation = "AUTOMODE_COMPLETE" in assistant_response
                tool_calls = assistant_message.get('tool_calls', [])
            else:
                # Handle unexpected dictionary response.
                console.print(Panel("Unexpected response format", title="API Error", style="bold red"))
                return "I'm sorry, but there was an unexpected error in the model response.", False
        else:
            # Handle unexpected non-dictionary response.
            console.print(Panel("Unexpected response type", title="API Error", style="bold red"))
            return "I'm sorry, but there was an unexpected error in the model response.", False
    except Exception as e:
        e = str(e)
        if e.lower() == "all connection attempts failed": response["error"] = "Ollama is not installed, please install it from https://ollama.com/download."
        if e.lower() == 'model "mistral-nemo" not found, try pulling it first': 
            response["error"] = "Ollama is not installed, please install it from https://ollama.com/download."
            try:
                process = subprocess.Popen(["ollama", "pull", "mistral-nemo"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in process.stdout:
                    print(line, end="")
                return_code = process.wait()
                if return_code != 0:
                    stderr_output = process.stderr.read()
                    print(stderr_output)
            except subprocess.CalledProcessError as e: terminal("e", e)
        console.print(Panel(f"API Error: {e}", title="API Error", style="bold red"))
        return "I'm sorry, there was an error communicating with the AI. Please try again.", False
    terminal("ai", assistant_response)
    if tool_calls:
        console.print(Panel("Tool calls detected", title="Tool Usage", style="bold yellow"))
        console.print(Panel(json.dumps(tool_calls, indent=2), title="Tool Calls", style="cyan"))
    # Display files in context.
    if globals.file_contents: 
        globals.files_in_context = "\n".join(globals.file_contents.keys())
        console.print(Panel(globals.files_in_context, title="Files in Context", title_align="left", border_style="white", expand=False))
    else: globals.files_in_context = "No files in context. Read, create, or edit files to add."
    for tool_call in tool_calls:
        tool_name = tool_call["function"]["name"]
        tool_arguments = tool_call["function"]["arguments"]
        # Check if tool_arguments is a string and parse it if necessary.
        if isinstance(tool_arguments, str):
            try: tool_input = json.loads(tool_arguments)
            except json.JSONDecodeError: tool_input = {"error": "Failed to parse tool arguments"}
        else: tool_input = tool_arguments
        console.print(Panel(f"Tool Used: {tool_name}", style="green"))
        console.print(Panel(f"Tool Input: {json.dumps(tool_input, indent=2)}", style="green"))
        tool_result = await execute_tool(client, tool_name, tool_input)
        if tool_result["is_error"]: console.print(Panel(tool_result["content"], title="Tool Execution Error", style="bold red"))
        else: console.print(Panel(tool_result["content"], title_align="left", title="Tool Result", style="green"))
        globals.current_conversation.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [tool_call]
        })
        globals.current_conversation.append({
            "role": "tool",
            "content": tool_result["content"],
            "tool_call_id": tool_call.get("id", "unknown_id") # Use 'unknown_id' if 'id' is not present.
        })
        # Update the file_contents dictionary if applicable.
        if tool_name in ["create_file", "edit_and_apply", "read_file"] and not tool_result["is_error"]:
            if "path" in tool_input:
                file_path = tool_input["path"]
                if "File contents updated in system prompt" in tool_result["content"] or \
                   "File created and added to system prompt" in tool_result["content"] or \
                   "has been read and stored in the system prompt" in tool_result["content"]:
                    # The file_contents dictionary is already updated in the tool function.
                    pass
        messages = filtered_conversation_history + globals.current_conversation
        try:
            # Prepend the system message to the messages list.
            system_message = {"role": "system", "content": update_system_prompt(current_iteration, max_iterations)}
            messages_with_system = [system_message] + messages
            tool_response = await client.chat(
                model=config.ai.providers.ollama.models.tool_checker_model,
                messages=messages_with_system,
                tools=sft_tools,
                stream=False
            )
            if isinstance(tool_response, dict) and "message" in tool_response:
                tool_checker_response = tool_response["message"].get("content", "")
                console.print(Panel(Markdown(tool_checker_response), title="Marcus's Response to Tool Result",  title_align="left", border_style="blue", expand=False))
                assistant_response += "\n\n" + tool_checker_response
            else:
                error_message = "Unexpected tool response format"
                console.print(Panel(error_message, title="Error", style="bold red"))
                assistant_response += f"\n\n{error_message}"
        except Exception as e:
            error_message = f"Error in tool response: {str(e)}"
            console.print(Panel(error_message, title="Error", style="bold red"))
            assistant_response += f"\n\n{error_message}"
    if assistant_response: globals.current_conversation.append({"role": "assistant", "content": assistant_response})
    globals.conversation_history = messages + [{"role": "assistant", "content": assistant_response}]
    return assistant_response, exit_continuation