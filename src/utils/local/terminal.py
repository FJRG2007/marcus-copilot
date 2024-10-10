import src.lib.globals as globals
from typing import Tuple, Dict, Any
import os, sys, json, venv, tavily, asyncio, subprocess
from src.utils.basics import logging, console, terminal
from src.utils.local.worker import edit_and_apply_multiple
from src.utils.local.files import create_files, read_multiple_files
from src.utils.local.folders import create_folders, list_files, scan_folder, validate_files_structure

async def send_to_ai_for_executing(client, code, execution_result):
    try:
        system_prompt = f"""
        You are an AI code execution agent. Your task is to analyze the provided code and its execution result from the 'code_execution_env' virtual environment, then provide a concise summary of what worked, what didn't work, and any important observations. Follow these steps:

        1. Review the code that was executed in the 'code_execution_env' virtual environment:
        {code}

        2. Analyze the execution result from the 'code_execution_env' virtual environment:
        {execution_result}

        3. Provide a brief summary of:
           - What parts of the code executed successfully in the virtual environment
           - Any errors or unexpected behavior encountered in the virtual environment
           - Potential improvements or fixes for issues, considering the isolated nature of the environment
           - Any important observations about the code's performance or output within the virtual environment
           - If the execution timed out, explain what this might mean (e.g., long-running process, infinite loop)

        Be concise and focus on the most important aspects of the code execution within the 'code_execution_env' virtual environment.

        IMPORTANT: PROVIDE ONLY YOUR ANALYSIS AND OBSERVATIONS. DO NOT INCLUDE ANY PREFACING STATEMENTS OR EXPLANATIONS OF YOUR ROLE.
        """
        response = client.beta.prompt_caching.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": f"Analyze this code execution from the 'code_execution_env' virtual environment:\n\nCode:\n{code}\n\nExecution Result:\n{execution_result}"}
            ],
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
        )
        # Update token usage for code execution.
        globals.code_execution_tokens["input"] += response.usage.input_tokens
        globals.code_execution_tokens["output"] += response.usage.output_tokens
        globals.code_execution_tokens["cache_creation"] = response.usage.cache_creation_input_tokens
        globals.code_execution_tokens["cache_read"] = response.usage.cache_read_input_tokens
        return response.content[0].text
    except Exception as e:
        console.print(f"Error in AI code execution analysis: {str(e)}", style="bold red")
        return f"Error analyzing code execution from 'code_execution_env': {str(e)}"

def run_shell_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.CalledProcessError as e:
        return {
            "stdout": e.stdout,
            "stderr": e.stderr,
            "return_code": e.returncode,
            "error": str(e)
        }
    except Exception as e: return { "error": f"An error occurred while executing the command: {str(e)}" }

def setup_virtual_environment() -> Tuple[str, str]:
    venv_name = "code_execution_env"
    venv_path = os.path.join(os.getcwd(), venv_name)
    try:
        if not os.path.exists(venv_path): venv.create(venv_path, with_pip=True)
        # Activate the virtual environment.
        if sys.platform == "win32": activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
        else: activate_script = os.path.join(venv_path, "bin", "activate")
        return venv_path, activate_script
    except Exception as e:
        logging.error(f"Error setting up virtual environment: {str(e)}")
        raise

def tavily_search(query):
    try: return tavily.qna_search(query=query, search_depth="advanced")
    except Exception as e: return f"Error performing search: {str(e)}"

async def execute_tool(client, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = None
        is_error = False
        console_output = None
        if tool_name == "create_files":
            if isinstance(tool_input, dict) and "files" in tool_input: files = tool_input["files"]
            else: files = tool_input
            result = create_files(files)
        elif tool_name == "edit_and_apply_multiple":
            files = tool_input.get("files")
            if not files:
                result = "Error: 'files' key is missing or empty."
                is_error = True
            else:
                # Ensure 'files' is a list of dictionaries.
                if isinstance(files, str):
                    try:
                        # Attempt to parse the JSON string.
                        files = json.loads(files)
                        if isinstance(files, dict): files = [files]
                        elif isinstance(files, list):
                            if not all(isinstance(file, dict) for file in files):
                                result = "Error: Each file must be a dictionary with 'path' and 'instructions'."
                                is_error = True
                    except json.JSONDecodeError:
                        result = "Error: 'files' must be a dictionary or a list of dictionaries, and should not be a string."
                        is_error = True
                elif isinstance(files, dict): files = [files]
                elif isinstance(files, list):
                    if not all(isinstance(file, dict) for file in files):
                        result = "Error: Each file must be a dictionary with 'path' and 'instructions'."
                        is_error = True
                else:
                    result = "Error: 'files' must be a dictionary or a list of dictionaries."
                    is_error = True
                if not is_error:
                    # Validate the structure of 'files'.
                    try: files = validate_files_structure(files)
                    except ValueError as ve:
                        result = f"Error: {str(ve)}"
                        is_error = True
            if not is_error: result, console_output = await edit_and_apply_multiple(files, tool_input["project_context"], is_automode=globals.automode)
        elif tool_name == "create_folders": result = create_folders(tool_input["paths"])
        elif tool_name == "read_multiple_files":
            paths = tool_input.get("paths")
            recursive = tool_input.get("recursive", False)
            if paths is None:
                result = "Error: No file paths provided"
                is_error = True
            else:
                files_to_read = [p for p in (paths if isinstance(paths, list) else [paths]) if p not in globals.file_contents]
                if not files_to_read: result = "All requested files are already in the system prompt. No need to read from disk."
                else: result = read_multiple_files(files_to_read, recursive)
        elif tool_name == "list_files": result = list_files(tool_input.get("path", "."))
        elif tool_name == "tavily_search": result = tavily_search(tool_input["query"])
        elif tool_name == "stop_process": result = stop_process(tool_input["process_id"])
        elif tool_name == "execute_code":
            process_id, execution_result = await execute_code(tool_input["code"])
            if execution_result.startswith("Process started and running"): analysis = "The process is still running in the background."
            else:
                analysis_task = asyncio.create_task(send_to_ai_for_executing(client, tool_input["code"], execution_result))
                analysis = await analysis_task
            result = f"{execution_result}\n\nAnalysis:\n{analysis}"
            if process_id in globals.running_processes: result += "\n\nNote: The process is still running in the background."
        elif tool_name == "scan_folder": result = scan_folder(tool_input["folder_path"], tool_input["output_file"])
        elif tool_name == "run_shell_command": result = run_shell_command(tool_input["command"])
        else:
            is_error = True
            result = f"Unknown tool: {tool_name}"
        return {
            "content": result,
            "is_error": is_error,
            "console_output": console_output
        }
    except KeyError as e:
        logging.error(f"Missing required parameter {str(e)} for tool {tool_name}")
        return {
            "content": f"Error: Missing required parameter {str(e)} for tool {tool_name}",
            "is_error": True,
            "console_output": None
        }
    except Exception as e:
        logging.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            "content": f"Error executing tool {tool_name}: {str(e)}",
            "is_error": True,
            "console_output": None
        }
    
def stop_process(process_id):
    global running_processes
    if process_id in running_processes:
        process = running_processes[process_id]
        if sys.platform == "win32": process.terminate()
        else: os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        del running_processes[process_id]
        return f"Process {process_id} has been stopped."
    else: return f"No running process found with ID {process_id}."

async def execute_code(code, timeout=10):
    global running_processes
    venv_path, activate_script = setup_virtual_environment()
    # Input validation.
    if not isinstance(code, str): terminal("e", "code must be a string", exitScript=True)
    if not isinstance(timeout, (int, float)): terminal("e", "timeout must be a number", exitScript=True)
    # Generate a unique identifier for this process.
    process_id = f"process_{len(running_processes)}"
    # Write the code to a temporary file.
    try:
        with open(f"{process_id}.py", "w") as f:
            f.write(code)
    except IOError as e: return process_id, f"Error writing code to file: {str(e)}"
    # Prepare the command to run the code.
    if sys.platform == "win32": command = f'"{activate_script}" && python3 {process_id}.py'
    else: command = f'source "{activate_script}" && python3 {process_id}.py'
    try:
        # Create a process to run the command.
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, shell=True, preexec_fn=None if sys.platform == "win32" else os.setsid)
        # Store the process in our global dictionary.
        running_processes[process_id] = process
        try:
            # Wait for initial output or timeout.
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout = stdout.decode()
            stderr = stderr.decode()
            return_code = process.returncode
        except asyncio.TimeoutError:
            # If we timeout, it means the process is still running.
            stdout = "Process started and running in the background."
            stderr = ""
            return_code = "Running"
        return process_id, f"Process ID: {process_id}\n\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nReturn Code: {return_code}"
    except Exception as e: return process_id, f"Error executing code: {str(e)}"
    finally:
        try: os.remove(f"{process_id}.py")
        except OSError: pass