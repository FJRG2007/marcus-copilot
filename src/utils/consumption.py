from src.utils.basics import console
from src.lib.globals import main_model_tokens, tool_checker_tokens, code_editor_tokens, code_execution_tokens

def display_token_usage():
    from rich.table import Table
    from rich.box import ROUNDED
    table = Table(box=ROUNDED)
    table.add_column("Model", style="cyan")
    table.add_column("Input", style="magenta")
    table.add_column("Output", style="magenta")
    table.add_column("Cache Write", style="blue")
    table.add_column("Cache Read", style="blue")
    table.add_column("Total", style="green")
    table.add_column(f"% of Context ({200000:,})", style="yellow")
    table.add_column("Cost ($)", style="red")
    model_costs = {
        "Main Model": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30, "has_context": True},
        "Tool Checker": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30, "has_context": False},
        "Code Editor": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30, "has_context": True},
        "Code Execution": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30, "has_context": False}
    }
    total_input = 0
    total_output = 0
    total_cache_write = 0
    total_cache_read = 0
    total_cost = 0
    total_context_tokens = 0
    for model, tokens in [("Main Model", main_model_tokens), ("Tool Checker", tool_checker_tokens), ("Code Editor", code_editor_tokens), ("Code Execution", code_execution_tokens)]:
        input_tokens = tokens["input"]
        output_tokens = tokens["output"]
        cache_write_tokens = tokens["cache_write"]
        cache_read_tokens = tokens["cache_read"]
        total_tokens = input_tokens + output_tokens + cache_write_tokens + cache_read_tokens
        total_input += input_tokens
        total_output += output_tokens
        total_cache_write += cache_write_tokens
        total_cache_read += cache_read_tokens
        input_cost = (input_tokens / 1_000_000) * model_costs[model]["input"]
        output_cost = (output_tokens / 1_000_000) * model_costs[model]["output"]
        cache_write_cost = (cache_write_tokens / 1_000_000) * model_costs[model]["cache_write"]
        cache_read_cost = (cache_read_tokens / 1_000_000) * model_costs[model]["cache_read"]
        model_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
        total_cost += model_cost
        if model_costs[model]["has_context"]:
            total_context_tokens += total_tokens
            percentage = (total_tokens / 200000) * 100
        else: percentage = 0
        table.add_row(model, f"{input_tokens:,}", f"{output_tokens:,}", f"{cache_write_tokens:,}", f"{cache_read_tokens:,}", f"{total_tokens:,}", f"{percentage:.2f}%" if model_costs[model]["has_context"] else "Doesn't save context", f"${model_cost:.3f}")
    grand_total = total_input + total_output + total_cache_write + total_cache_read
    total_percentage = (total_context_tokens / 200000) * 100
    table.add_row("Total", f"{total_input:,}", f"{total_output:,}", f"{total_cache_write:,}", f"{total_cache_read:,}", f"{grand_total:,}", f"{total_percentage:.2f}%", f"${total_cost:.3f}", style="bold")
    console.print(table)