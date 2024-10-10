import re, json, difflib
from rich.panel import Panel
import src.lib.globals as globals
from src.services.chat.basics import generate_diff
from src.utils.basics import logging, console, terminal
from src.utils.local.folders import validate_files_structure
from src.services.ai.prompts.worker import generate_edit_instructions
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

async def apply_edits(file_path, edit_instructions, original_content):
    changes_made = False
    edited_content = original_content
    total_edits = len(edit_instructions)
    failed_edits = []
    console_output = []
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        edit_task = progress.add_task("[cyan]Applying edits...", total=total_edits)
        for i, edit in enumerate(edit_instructions, 1):
            search_content = edit["search"].strip()
            replace_content = edit["replace"].strip()
            similarity = edit["similarity"]
            # Use regex to find the content, ignoring leading/trailing whitespace.
            pattern = re.compile(re.escape(search_content), re.DOTALL)
            match = pattern.search(edited_content)
            if match or (globals.USE_FUZZY_SEARCH and similarity >= 0.8):
                if not match:
                    # If using fuzzy search and no exact match, find the best match
                    best_match = difflib.get_close_matches(search_content, [edited_content], n=1, cutoff=0.6)
                    if best_match: match = re.search(re.escape(best_match[0]), edited_content)
                if match:
                    # Replace the content using re.sub for more robust replacement.
                    replace_content_cleaned = re.sub(r'</?SEARCH>|</?REPLACE>', "", replace_content)
                    edited_content = pattern.sub(replace_content_cleaned, edited_content, count=1)
                    changes_made = True
                    # Display the diff for this edit.
                    diff_result = generate_diff(search_content, replace_content, file_path)
                    console.print(Panel(diff_result, title=f"Changes in {file_path} ({i}/{total_edits}) - Similarity: {similarity:.2f}", style="cyan"))
                    console_output.append(f"Edit {i}/{total_edits} applied successfully")
                else:
                    message = f"Edit {i}/{total_edits} not applied: content not found (Similarity: {similarity:.2f})"
                    console_output.append(message)
                    console.print(Panel(message, style="yellow"))
                    failed_edits.append(f"Edit {i}: {search_content}")
            else:
                message = f"Edit {i}/{total_edits} not applied: content not found (Similarity: {similarity:.2f})"
                console_output.append(message)
                console.print(Panel(message, style="yellow"))
                failed_edits.append(f"Edit {i}: {search_content}")
            progress.update(edit_task, advance=1)

    if not changes_made:
        message = "No changes were applied. The file content already matches the desired state."
        console_output.append(message)
        console.print(Panel(message, style="green"))
    else:
        # Write the changes to the file.
        with open(file_path, "w") as file:
            file.write(edited_content)
        message = f"Changes have been written to {file_path}"
        console_output.append(message)
        console.print(Panel(message, style="green"))
    return edited_content, changes_made, failed_edits, "\n".join(console_output)

async def edit_and_apply(path, instructions, project_context, is_automode=False, max_retries=3):

    try:
        original_content = globals.file_contents.get(path, "")
        if not original_content:
            with open(path, "r") as file:
                original_content = file.read()
            globals.file_contents[path] = original_content
        for attempt in range(max_retries):
            edit_instructions_json = await generate_edit_instructions(path, original_content, instructions, project_context, globals.file_contents)
            if edit_instructions_json:
                edit_instructions = json.loads(edit_instructions_json)  # Parse JSON here
                console.print(Panel(f"Attempt {attempt + 1}/{max_retries}: The following SEARCH/REPLACE blocks have been generated:", title="Edit Instructions", style="cyan"))
                for i, block in enumerate(edit_instructions, 1):
                    console.print(f"Block {i}:")
                    console.print(Panel(f"SEARCH:\n{block['search']}\n\nREPLACE:\n{block['replace']}", expand=False))
                edited_content, changes_made, failed_edits = await apply_edits(path, edit_instructions, original_content)
                if changes_made:
                    globals.file_contents[path] = edited_content  # Update the file_contents with the new content
                    console.print(Panel(f"File contents updated in system prompt: {path}", style="green"))
                    if failed_edits:
                        console.print(Panel(f"Some edits could not be applied. Retrying...", style="yellow"))
                        instructions += f"\n\nPlease retry the following edits that could not be applied:\n{failed_edits}"
                        original_content = edited_content
                        continue
                    return f"Changes applied to {path}"
                elif attempt == max_retries - 1: return f"No changes could be applied to {path} after {max_retries} attempts. Please review the edit instructions and try again."
                else: console.print(Panel(f"No changes could be applied in attempt {attempt + 1}. Retrying...", style="yellow"))
            else: return f"No changes suggested for {path}"
        return f"Failed to apply changes to {path} after {max_retries} attempts."
    except Exception as e: return f"Error editing/applying to file: {str(e)}"

async def edit_and_apply_multiple(response, files, project_context, is_automode=False):
    results = []
    console_outputs = []
    logging.debug(f"edit_and_apply_multiple called with files: {files}")
    logging.debug(f"Project context: {project_context}")
    try: files = validate_files_structure(files)
    except ValueError as ve:
        logging.error(f"Validation error: {ve}")
        return [], f"Error: {ve}"
    logging.info(f"Starting edit_and_apply_multiple with {len(files)} file(s)")
    for file in files:
        path = file["path"]
        instructions = file["instructions"]
        logging.info(f"Processing file: {path}")
        try:
            original_content = globals.file_contents.get(path, "")
            if not original_content:
                logging.info(f"Reading content for file: {path}")
                with open(path, "r") as f:
                    original_content = f.read()
                globals.file_contents[path] = original_content
            logging.info(f"Generating edit instructions for file: {path}")
            edit_instructions = await generate_edit_instructions(response, path, original_content, instructions, project_context, globals.file_contents)
            logging.debug(f"AI response for {path}: {edit_instructions}")
            if not isinstance(edit_instructions, list) or not all(isinstance(item, dict) for item in edit_instructions): terminal("e", "Invalid edit_instructions format. Expected a list of dictionaries.", exitScript=True)
            if edit_instructions:
                console.print(Panel(f"File: {path}\nThe following SEARCH/REPLACE blocks have been generated:", title="Edit Instructions", style="cyan"))
                for i, block in enumerate(edit_instructions, 1):
                    console.print(f"Block {i}:")
                    console.print(Panel(f"SEARCH:\n{block["search"]}\n\nREPLACE:\n{block["replace"]}\nSimilarity: {block["similarity"]:.2f}", expand=False))
                logging.info(f"Applying edits to file: {path}")
                edited_content, changes_made, failed_edits, console_output = await apply_edits(path, edit_instructions, original_content)
                console_outputs.append(console_output)
                if changes_made:
                    globals.file_contents[path] = edited_content
                    console.print(Panel(f"File contents updated in system prompt: {path}", style="green"))
                    logging.info(f"Changes applied to file: {path}")

                    if failed_edits:
                        logging.warning(f"Some edits failed for file: {path}")
                        logging.debug(f"Failed edits for {path}: {failed_edits}")
                        results.append({
                            "path": path,
                            "status": "partial_success",
                            "message": f"Some changes applied to {path}, but some edits failed.",
                            "failed_edits": failed_edits,
                            "edited_content": edited_content
                        })
                    else:
                        results.append({
                            "path": path,
                            "status": "success",
                            "message": f"All changes successfully applied to {path}",
                            "edited_content": edited_content
                        })
                else:
                    logging.warning(f"No changes applied to file: {path}")
                    results.append({
                        "path": path,
                        "status": "no_changes",
                        "message": f"No changes could be applied to {path}. Please review the edit instructions and try again."
                    })
            else:
                logging.warning(f"No edit instructions generated for file: {path}")
                results.append({
                    "path": path,
                    "status": "no_instructions",
                    "message": f"No edit instructions generated for {path}"
                })
        except Exception as e:
            logging.error(f"Error editing/applying to file {path}: {str(e)}")
            logging.exception("Full traceback:")
            error_message = f"Error editing/applying to file {path}: {str(e)}"
            results.append({
                "path": path,
                "status": "error",
                "message": error_message
            })
            console_outputs.append(error_message)
    logging.info("Completed edit_and_apply_multiple")
    logging.debug(f"Results: {results}")
    return results, "\n".join(console_outputs)