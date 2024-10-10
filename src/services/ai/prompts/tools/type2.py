import json, importlib

tools = [
    {
        "worker": "src.utils.local.folders",
        "name": "create_folders",
        "description": "Create new folders at the specified paths, including nested directories. This tool should be used when you need to create one or more directories (including nested ones) in the project structure. It will create all necessary parent directories if they don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "An array of absolute or relative paths where the folders should be created. Use forward slashes (/) for path separation, even on Windows systems. For nested directories, simply include the full path (e.g., 'parent/child/grandchild')."
                }
            },
            "required": ["paths"]
        }
    },
    {
        "worker": "src.utils.local.files",
        "name": "scan_folder",
        "description": "Scan a specified folder and create a Markdown file with the contents of all coding text files, excluding binary files and common ignored folders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "The absolute or relative path of the folder to scan. Use forward slashes (/) for path separation, even on Windows systems."
                },
                "output_file": {
                    "type": "string",
                    "description": "The name of the output Markdown file to create with the scanned contents."
                }
            },
            "required": ["folder_path", "output_file"]
        }
    },
    {
        "worker": "src.utils.local.files",
        "name": "create_files",
        "description": "Create one or more new files with the given contents. This tool should be used when you need to create files in the project structure. It will create all necessary parent directories if they don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "A single file path to create an empty file."
                        },
                        {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"}
                            },
                            "required": ["path"]
                        },
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"}
                                },
                                "required": ["path"]
                            }
                        }
                    ]
                }
            },
            "required": ["files"]
        }
    },
    {
        "worker": "src.utils.local.worker",
        "name": "edit_and_apply_multiple",
        "description": "Apply AI-powered improvements to multiple files based on specific instructions and detailed project context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "The absolute or relative path of the file to edit."
                            },
                            "instructions": {
                                "type": "string",
                                "description": "Specific instructions for editing this file."
                            }
                        },
                        "required": ["path", "instructions"]
                    }
                },
                "project_context": {
                    "type": "string",
                    "description": "Comprehensive context about the project, including recent changes, new variables or functions, interconnections between files, coding standards, and any other relevant information that might affect the edits."
                }
            },
            "required": ["files", "project_context"]
        }
    },
    {
        "worker": "src.utils.local.terminal",
        "name": "execute_code",
        "description": "Execute Python code in the 'code_execution_env' virtual environment and return the output. This tool should be used when you need to run code and see its output or check for errors. All code execution happens exclusively in this isolated environment. The tool will return the standard output, standard error, and return code of the executed code. Long-running processes will return a process ID for later management.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute in the 'code_execution_env' virtual environment. Include all necessary imports and ensure the code is complete and self-contained."
                }
            },
            "required": ["code"]
        }
    },
    {
        "worker": "src.utils.local.terminal",
        "name": "stop_process",
        "description": "Stop a running process by its ID. This tool should be used to terminate long-running processes that were started by the execute_code tool. It will attempt to stop the process gracefully, but may force termination if necessary. The tool will return a success message if the process is stopped, and an error message if the process doesn't exist or can't be stopped.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "The ID of the process to stop, as returned by the execute_code tool for long-running processes."
                }
            },
            "required": ["process_id"]
        }
    },
    {
        "worker": "src.utils.local.files",
        "name": "read_multiple_files",
        "description": "Read the contents of one or more existing files, supporting wildcards and recursive directory reading.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "A single file path, directory path, or wildcard pattern."
                        },
                        {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "An array of file paths, directory paths, or wildcard patterns."
                        }
                    ],
                    "description": "The path(s) of the file(s) to read. Use forward slashes (/) for path separation, even on Windows systems. Supports wildcards (e.g., '*.py') and directory paths."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, read files recursively from directories. Default is false.",
                    "default": False
                }
            },
            "required": ["paths"]
        }
    },
    {
        "worker": "src.utils.local.folders",
        "name": "list_files",
        "description": "List all files and directories in the specified folder. This tool should be used when you need to see the contents of a directory. It will return a list of all files and subdirectories in the specified path. If the directory doesn't exist or can't be read, an appropriate error message will be returned.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The absolute or relative path of the folder to list. Use forward slashes (/) for path separation, even on Windows systems. If not provided, the current working directory will be used."
                }
            }
        }
    },
    {
        "worker": "src.utils.local.terminal",
        "name": "tavily_search",
        "description": "Perform a web search using the Tavily API to get up-to-date information or additional context. This tool should be used when you need current information or feel a search could provide a better answer to the user's query. It will return a summary of the search results, including relevant snippets and source URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be as specific and detailed as possible to get the most relevant results."
                }
            },
            "required": ["query"]
        }
    },
    {
        "worker": "src.utils.local.terminal",
        "name": "run_shell_command",
        "description": "Execute a shell command and return its output. This tool should be used when you need to run system commands or interact with the operating system. It will return the standard output, standard error, and return code of the executed command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute. Ensure the command is safe and appropriate for the current operating system."
                }
            },
            "required": ["command"]
        }
    }
]

def get_tools():
    no_worker_tools = []
    for tool_ in json.loads(json.dumps(tools.copy(), ensure_ascii=False)):
        tool_.pop("worker")
        no_worker_tools.append(tool_)
    return no_worker_tools

def get_worker(name):
    return importlib.import_module(list(filter(lambda x: x["function"]["name"] == name, tools))[0]["worker"]).main