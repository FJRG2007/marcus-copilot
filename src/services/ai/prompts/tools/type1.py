import json
import importlib
from typing import List, Dict, Any

tools = [
    {
        "worker": "src.utils.local.folders",
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path where the folder should be created"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "worker": "src.utils.local.files",
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file at the specified path with the given content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path where the file should be created"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "worker": "src.utils.local.worker",
        "type": "function",
        "function": {
            "name": "edit_and_apply",
            "description": "Apply AI-powered improvements to a file based on specific instructions and project context",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path of the file to edit"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Detailed instructions for the changes to be made"
                    },
                    "project_context": {
                        "type": "string",
                        "description": "Comprehensive context about the project"
                    }
                },
                "required": ["path", "instructions", "project_context"]
            }
        }
    },
    {
        "worker": "src.utils.local.files",
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path of the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "worker": "src.utils.local.files",
        "type": "function",
        "function": {
            "name": "read_multiple_files",
            "description": "Read the contents of multiple files at the specified paths",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "An array of absolute or relative paths of the files to read"
                    }
                },
                "required": ["paths"]
            }
        }
    },
    {
        "worker": "src.utils.local.folders",
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories in the specified folder",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path of the folder to list"
                    }
                }
            }
        }
    },
    {
        "worker": "src.utils.local.terminal",
        "type": "function",
        "function": {
            "name": "tavily_search",
            "description": "Perform a web search using the Tavily API",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def get_tools() -> List[Dict[str, Any]]:
    # Return tools without including the worker module reference
    return [{**tool, "worker": None} for tool in tools]

def get_worker(name: str):
    matching_tools = list(filter(lambda x: x["function"]["name"] == name, tools))
    if not matching_tools: 
        raise ValueError(f"No worker found for function name: {name}")
    
    # Import the module without including it in the tools list
    worker_module = importlib.import_module(matching_tools[0]["worker"])
    return worker_module.main