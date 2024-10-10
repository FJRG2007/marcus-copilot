import os, mimetypes
from src.lib.config import config
from src.utils.basics import terminal

def list_files(path="."):
    try: return "\n".join(os.listdir(path))
    except Exception as e: return f"Error listing files: {str(e)}"

def validate_files_structure(files):
    if not isinstance(files, (dict, list)): terminal("e", "Invalid 'files' structure. Expected a dictionary or a list of dictionaries.", exitScript=True)
    if isinstance(files, dict): files = [files]
    for file in files:
        if not isinstance(file, dict): terminal("e", "Each file must be a dictionary.", exitScript=True)
        if "path" not in file or "instructions" not in file: terminal("e", "Each file dictionary must contain 'path' and 'instructions' keys.", exitScript=True)
        if not isinstance(file["path"], str) or not isinstance(file["instructions"], str): terminal("e", "'path' and 'instructions' must be strings.", exitScript=True)
    return files

def scan_folder(folder_path: str, output_file: str) -> str:
    markdown_content = f"# Folder Scan: {folder_path}\n\n"
    total_chars = len(markdown_content)
    max_chars = 600000 # Approximating 150,000 tokens.
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in config.ignored_folders]
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, folder_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith("text"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    file_content = f"## {relative_path}\n\n```\n{content}\n```\n\n"
                    if total_chars + len(file_content) > max_chars:
                        remaining_chars = max_chars - total_chars
                        if remaining_chars > 0:
                            truncated_content = file_content[:remaining_chars]
                            markdown_content += truncated_content
                            markdown_content += "\n\n... Content truncated due to size limitations ...\n"
                        else: markdown_content += "\n\n... Additional files omitted due to size limitations ...\n"
                        break
                    else:
                        markdown_content += file_content
                        total_chars += len(file_content)
                except Exception as e:
                    error_msg = f"## {relative_path}\n\nError reading file: {str(e)}\n\n"
                    if total_chars + len(error_msg) <= max_chars:
                        markdown_content += error_msg
                        total_chars += len(error_msg)
        if total_chars >= max_chars: break
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    return f"Folder scan complete. Markdown file created at: {output_file}. Total characters: {total_chars}"

def create_folders(paths):
    results = []
    for path in paths:
        try:
            os.makedirs(path, exist_ok=True)
            results.append(f"Folder(s) created: {path}")
        except Exception as e: results.append(f"Error creating folder(s) {path}: {str(e)}")
    return "\n".join(results)