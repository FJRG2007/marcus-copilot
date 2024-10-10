from typing import Optional
from rich.panel import Panel
from src.lib.config import config
from src.utils.basics import logging, console, terminal
import re, json, difflib, src.lib.globals as globals, src.services.ai.prompts.system as system_prompts

def generate_instructions_prompt(file_path, file_content, instructions, project_context, full_file_contents):
    return f"""
        You are an expert coding assistant specializing in web development (CSS, JavaScript, React, Tailwind, Node.JS, Hugo/Markdown). Review the following information carefully:
    
        1. File Content:
        {file_content}
    
        2. Edit Instructions:
        {instructions}
    
        3. Project Context:
        {project_context}
    
        4. Previous Edit Memory:
        {"\n".join([f"Memory {i+1}:\n{mem}" for i, mem in enumerate(globals.code_editor_memory)])}
    
        5. Full Project Files Context:
        {"\n\n".join([f"--- {path} ---\n{content}" for path, content in full_file_contents.items() if path != file_path or path not in globals.code_editor_files])}
    
        Follow this process to generate edit instructions:
    
        1. <CODE_REVIEW>
        Analyze the existing code thoroughly. Describe how it works, identifying key components, 
        dependencies, and potential issues. Consider the broader project context and previous edits.
        </CODE_REVIEW>
    
        2. <PLANNING>
        Construct a plan to implement the requested changes. Consider:
        - How to avoid code duplication (DRY principle)
        - Balance between maintenance and flexibility
        - Relevant frameworks or libraries
        - Security implications
        - Performance impacts
        Outline discrete changes and suggest small tests for each stage.
        </PLANNING>
    
        3. Finally, generate SEARCH/REPLACE blocks for each necessary change:
        - Use enough context to uniquely identify the code to be changed
        - Maintain correct indentation and formatting
        - Focus on specific, targeted changes
        - Ensure consistency with project context and previous edits
    
        USE THIS FORMAT FOR CHANGES:
    
        <SEARCH>
        Code to be replaced (with sufficient context)
        </SEARCH>
        <REPLACE>
        New code to insert
        </REPLACE>
    
        IMPORTANT: ONLY RETURN CODE INSIDE THE <SEARCH> AND <REPLACE> TAGS. DO NOT INCLUDE ANY OTHER TEXT, COMMENTS, or Explanations. FOR EXAMPLE:
    
        <SEARCH>
        def old_function():
            pass
        </SEARCH>
        <REPLACE>
        def new_function():
            print("New Functionality")
        </REPLACE>
        """

async def generate_edit_instructions(response, file_path):
    try:
        # Update token usage for code editor.
        globals.code_editor_tokens["input"] += response.usage.input_tokens
        globals.code_editor_tokens["output"] += response.usage.output_tokens
        globals.code_editor_tokens["cache_write"] = response.usage.cache_creation_input_tokens
        globals.code_editor_tokens["cache_read"] = response.usage.cache_read_input_tokens
        ai_response_text = response.content[0].text # Extract the text.
        # If ai_response_text is a list, handle it.
        if isinstance(ai_response_text, list): ai_response_text = " ".join(item["text"] if isinstance(item, dict) and "text" in item else str(item) for item in ai_response_text)
        elif not isinstance(ai_response_text, str): ai_response_text = str(ai_response_text)
        # Validate AI response.
        try:
            if not validate_ai_response(ai_response_text): terminal("e", "AI response does not contain valid SEARCH/REPLACE blocks.", exitScript=True)
        except ValueError as ve:
            logging.error(f"Validation failed: {ve}")
            return [] # Return empty list to indicate failure.
        # Parse the response to extract SEARCH/REPLACE blocks.
        edit_instructions = parse_search_replace_blocks(ai_response_text)
        if not edit_instructions: terminal("e", "No valid edit instructions were generated", exitScript=True)
        # Update code editor memory.
        globals.code_editor_memory.append(f"Edit Instructions for {file_path}:\n{ai_response_text}")
        # Add the file to code_editor_files set.
        globals.code_editor_files.add(file_path)
        return edit_instructions
    except Exception as e:
        terminal("e", f"Error in generating edit instructions: {str(e)}")
        logging.error(f"Error in generating edit instructions: {str(e)}")
        return [] # Return empty list if any exception occurs.
    
def update_system_prompt(current_iteration: Optional[int] = None, max_iterations: Optional[int] = None) -> str:
    chain_of_thought_prompt = """
    Answer the user's request using relevant tools (if they are available). Before calling a tool, do some analysis within <thinking></thinking> tags. First, think about which of the provided tools is the relevant tool to answer the user's request. Second, go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. If all of the required parameters are present or can be reasonably inferred, close the thinking tag and proceed with the tool call. BUT, if one of the values for a required parameter is missing, DO NOT invoke the function (not even with fillers for the missing params) and instead, ask the user to provide the missing parameters. DO NOT ask for more information on optional parameters if it is not provided.

    Do not reflect on the quality of the returned search results in your response.

    IMPORTANT: Before using the read_multiple_files tool, always check if the files you need are already in your context (system prompt).
    If the file contents are already available to you, use that information directly instead of calling the read_multiple_files tool.
    Only use the read_multiple_files tool for files that are not already in your context.
    When instructing to read a file, always use the full file path.
    """
    file_contents_prompt = f"\n\nFiles already in your context:\n{"\n".join(globals.file_contents.keys())}\n\nFile Contents:\n"
    for path, content in globals.file_contents.items():
        file_contents_prompt += f"\n--- {path} ---\n{content}\n"
    if globals.automode:
        iteration_info = ""
        if current_iteration is not None and max_iterations is not None: iteration_info = f"You are currently on iteration {current_iteration} out of {max_iterations} in automode."
        return system_prompts.BASE_SYSTEM_PROMPT + file_contents_prompt + "\n\n" + system_prompts.AUTOMODE_SYSTEM_PROMPT.format(iteration_info=iteration_info) + "\n\n" + chain_of_thought_prompt
    else: return system_prompts.BASE_SYSTEM_PROMPT + file_contents_prompt + "\n\n" + chain_of_thought_prompt

def validate_ai_response(response_text):
    if isinstance(response_text, list):
        # Extract 'text' from each dictionary in the list.
        try: response_text = " ".join( item["text"] if isinstance(item, dict) and "text" in item else str(item) for item in response_text)
        except Exception as e: terminal("e", "Invalid format in response_text list.", exitScript=True)
    elif not isinstance(response_text, str): terminal("e", f"Invalid type for response_text: {type(response_text)}. Expected string.", exitScript=True)
    # Log the processed response_text.
    logging.debug(f"Processed response_text for validation: {response_text}")
    if not re.search(r'<SEARCH>.*?</SEARCH>', response_text, re.DOTALL): terminal("e", "AI response does not contain any <SEARCH> blocks.", exitScript=True)
    if not re.search(r'<REPLACE>.*?</REPLACE>', response_text, re.DOTALL): terminal("e", "AI response does not contain any <REPLACE> blocks.", exitScript=True)
    return True

def parse_search_replace_blocks(response_text, use_fuzzy=globals.USE_FUZZY_SEARCH):
    blocks = []
    matches = re.findall(r'<SEARCH>\s*(.*?)\s*</SEARCH>\s*<REPLACE>\s*(.*?)\s*</REPLACE>', response_text, re.DOTALL)
    for search, replace in matches:
        search = search.strip()
        replace = replace.strip()
        similarity = 1.0 # Default to exact match.
        if use_fuzzy and search not in response_text:
            # Extract possible search targets from the response text.
            possible_search_targets = re.findall(r'<SEARCH>\s*(.*?)\s*</SEARCH>', response_text, re.DOTALL)
            possible_search_targets = [target.strip() for target in possible_search_targets]
            best_match = difflib.get_close_matches(search, possible_search_targets, n=1, cutoff=0.6)
            if best_match: similarity = difflib.SequenceMatcher(None, search, best_match[0]).ratio()
            else: similarity = 0.0
        blocks.append({
            "search": search,
            "replace": replace,
            "similarity": similarity
        })
    return blocks

async def decide_retry(client, tool_checker_response, edit_results, tool_input):
    try:
        if not edit_results:
            console.print(Panel("No edits were made or an error occurred. Skipping retry.", title="Info", style="bold yellow"))
            return {"retry": False, "files_to_retry": []}
        response = client.messages.create(
            model=config.ai.providers.anthropic.models.tool_checker_model,
            max_tokens=1000,
            system="""You are an AI assistant tasked with deciding whether to retry editing files based on the previous edit results and the AI's response. Respond with a JSON object containing 'retry' (boolean) and 'files_to_retry' (list of file paths).

Example of the expected JSON response:
{
    "retry": true,
    "files_to_retry": ["/path/to/file1.py", "/path/to/file2.py"]
}

Only return the JSON object, nothing else. Ensure that the JSON is properly formatted with double quotes around property names and string values.""",
            messages=[
                {"role": "user", "content": f"Previous edit results: {json.dumps(edit_results)}\n\nAI's response: {tool_checker_response}\n\nDecide whether to retry editing any files."}
            ]
        )
        response_text = response.content[0].text.strip()
        # Handle list of dicts if necessary.
        if isinstance(response_text, list): response_text = " ".join( item["text"] if isinstance(item, dict) and "text" in item else str(item) for item in response_text)
        elif not isinstance(response_text, str): response_text = str(response_text)
        try: decision = json.loads(response_text)
        except json.JSONDecodeError:
            console.print(Panel("Failed to parse JSON from AI response. Using fallback decision.", title="Warning", style="bold yellow"))
            decision = {
                "retry": "retry" in response_text.lower(),
                "files_to_retry": []
            }
        files = tool_input.get("files", [])
        if isinstance(files, dict): files = [files]
        elif not isinstance(files, list):
            console.print(Panel("Error: 'files' must be a dictionary or a list of dictionaries.", title="Error", style="bold red"))
            return {"retry": False, "files_to_retry": []}
        if not all(isinstance(item, dict) for item in files):
            console.print(Panel("Error: Each file must be a dictionary with 'path' and 'instructions'.", title="Error", style="bold red"))
            return {"retry": False, "files_to_retry": []}
        valid_file_paths = set(file["path"] for file in files)
        retry_decision = {
            "retry": decision.get("retry", False),
            "files_to_retry": [file_path for file_path in decision.get("files_to_retry", []) if file_path in valid_file_paths]
        }
        console.print(Panel(f"Retry decision: {json.dumps(retry_decision, indent=2)}", title="Retry Decision", style="bold cyan"))
        return retry_decision
    except Exception as e:
        console.print(Panel(f"Error in decide_retry: {str(e)}", title="Error", style="bold red"))
        return {"retry": False, "files_to_retry": []}