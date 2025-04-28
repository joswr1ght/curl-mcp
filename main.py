from mcp.server.fastmcp import FastMCP
import subprocess
import shlex 
import re
from urllib.parse import urlparse
import os 
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

mcp = FastMCP("curl-mcp")
console = Console()

# --- Helper Function for Sanitization (Example) ---
def sanitize_filename(filename: str) -> str:
    """Basic filename sanitization."""
    # Remove potentially dangerous characters
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # Prevent path traversal (optional, depends on desired behavior)
    filename = os.path.basename(filename)
    # Limit length (optional)
    max_len = 200
    if len(filename) > max_len:
        base, ext = os.path.splitext(filename)
        ext = ext[:max_len - len(base) - 1] # Truncate extension if needed
        filename = base[:max_len - len(ext)] + ext
    if not filename: # Handle empty filenames after sanitization
        return "sanitized_output"
    return filename

# --- Helper Function for Building Command List ---
def build_curl_command_list(options: dict, url: str) -> list:
    """Builds the list of arguments for subprocess from options dict."""
    command = ["curl"]
    for option, value in options.items():
        if isinstance(value, list): # Handle options that appear multiple times (e.g., -H)
            for item in value:
                command.append(option)
                if item is not True: # Avoid adding 'True' for boolean flags used in lists (unlikely)
                    command.append(str(item))
        elif value is True: # Boolean flags (like -L, -I, -v, -k)
            command.append(option)
        elif value is not False: # Other options with single values (like -X, -d, -o, -A, -u, -m, -x)
            command.append(option)
            command.append(str(value))
        # Ignore options explicitly set to False
    command.append(url)
    return command


@mcp.tool()
async def curl(instruction: str) -> str:
    """
    Execute a curl command based on natural language instructions.

    Args:
        instruction: A natural language description of the curl request to make.

    Returns:
        The output of the curl command execution status and results.
    """
    raw_output = re.search(r'\b(raw|crudo|consola|terminal)\b', instruction, re.IGNORECASE)

    try:
        curl_options_data = parse_instruction(instruction)

        # Check if parsing itself returned an error message
        if curl_options_data.get("error"):
            return f"Error parsing instruction: {curl_options_data['error']}\nInstruction: {instruction}"

        # Use display_options for the command string shown to the user
        options_for_display = curl_options_data.get("display_options", curl_options_data["options"])
        command_string_display = " ".join(build_curl_command_list(options_for_display, curl_options_data["url"]))


        # Execute the parsed curl command using the real options
        execution_result = execute_curl(curl_options_data["options"], curl_options_data["url"])

        # Combine command display with execution result
        if raw_output:
            # Even in raw mode, show command if execution failed
            if execution_result.get("error"):
                 return f"Failed Command: {command_string_display}\n\nError:\n{execution_result['error']}\nOutput:\n{execution_result.get('output', '')}"
            else:
                 return execution_result.get('output', '') # Return only output on success
        else:
            if execution_result.get("error"):
                 # Prioritize specific execution error over generic message
                 error_msg = execution_result['error']
                 output_msg = execution_result.get('output', '') # Include any partial output
                 return f"Failed Command: {command_string_display}\n\nError:\n{error_msg}\nOutput:\n{output_msg}"
            else:
                 output_msg = execution_result.get('output', 'No output received.')
                 return f"Command executed: {command_string_display}\n\nResult:\n{output_msg}"

    except Exception as e:
         # Catch unexpected errors during the whole process
         # Log the full error for debugging
         print(f"Unexpected error processing instruction: {instruction}\nError: {e}")
         # Provide a user-friendly message
         return f"Unexpected error processing instruction. Please check logs or try rephrasing. Error: {str(e)}"


def parse_instruction(instruction: str) -> dict:
    """Parse a natural language instruction into curl command options."""
    result_data = {
        "url": "",
        "options": {},
        "display_options": None, # Will be created if masking is needed
        "error": None
    }
    options = result_data["options"] # Shortcut

    try:
        # 1. Extract URL (More robustly)
        #    Prioritize explicit URLs, then keywords, then generic domain-like patterns.
        url_patterns = [
            r'https?://[^\s"\'<>]+',                      # Full URL (highest priority)
            r'(?:url|uri|site|sitio|endpoint|address)\s*[:=]?\s*\'?("?)(https?://[^\s"\'<>]+)\1\'?', # url: https://...
            r'(?:url|uri|site|sitio|endpoint|address)\s*[:=]?\s*\'?("?)([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s"\'<>]*)\1\'?', # url: example.com/path
            r'\bto\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s"\'<>]*)\b', # request to example.com
            r'\b(?:on|at|for)\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s"\'<>]*)\b', # get headers for example.com
            r'\b([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'          # Bare domain (lowest priority)
        ]
        extracted_url = None
        for i, pattern in enumerate(url_patterns):
            url_match = re.search(pattern, instruction, re.IGNORECASE)
            if url_match:
                # Find the right group (usually the last one with content)
                url = next((g for g in reversed(url_match.groups()) if g), url_match.group(0))
                url = url.strip('.,:;"\'') # Clean surrounding punctuation

                # Add http:// if no protocol is specified (check must be case-insensitive)
                if not re.match(r'^https?://', url, re.IGNORECASE):
                    # Avoid adding http:// if it looks like a filename for -d @filename or -F name=@filename
                    if not (url.startswith('@') or '=' in url): # Basic check, might need refinement
                         url = 'http://' + url

                extracted_url = url
                # Maybe remove the matched URL part from instruction to avoid re-parsing? (Careful)
                # instruction = instruction[:url_match.start()] + instruction[url_match.end():]
                break # Stop after first match (patterns ordered by priority)

        if not extracted_url:
            result_data["error"] = "Could not extract a valid URL."
            return result_data
        result_data["url"] = extracted_url

        # 2. Detect Method (HEAD, POST, PUT, DELETE) - Default GET
        # Use \b for word boundaries to avoid matching 'posting' as POST
        if re.search(r'\b(head|headers?|cabeceras?|encabezados?)\b', instruction, re.IGNORECASE) and \
           re.search(r'\b(only|just|solo|solamente|show|mostrar|obtener|get)\b', instruction, re.IGNORECASE):
             options["-I"] = True
        elif re.search(r'\bpost\b|\benví[ao](r)?\b|\bsubmit\b|\bsend\b', instruction, re.IGNORECASE):
            options["-X"] = "POST"
        elif re.search(r'\bput\b|\bactualiz[ao](r)?\b|\bupdate\b', instruction, re.IGNORECASE):
            options["-X"] = "PUT"
        elif re.search(r'\bdelete\b|\belimin[ao](r)?\b|\bremove\b', instruction, re.IGNORECASE):
            options["-X"] = "DELETE"
        elif re.search(r'\boptions\b', instruction, re.IGNORECASE):
            options["-X"] = "OPTIONS"
        elif re.search(r'\bpatch\b|\bparch[ea](r)?\b', instruction, re.IGNORECASE):
            options["-X"] = "PATCH"
        # GET is the default if no method specified and not -I

        # 3. Follow Redirects (-L) - Default ON unless HEAD or explicitly disabled
        if " -I" not in options and not re.search(r'\b(no|not|sin)\s+(follow|seguir)\s+redirects?', instruction, re.IGNORECASE):
            options["-L"] = True
        elif re.search(r'\b(follow|seguir)\s+redirects?', instruction, re.IGNORECASE):
             options["-L"] = True # Explicitly enable if requested


        # 4. Data Handling (-d, -d @file, --data-urlencode, -F) - Prioritize specific forms
        data_payload = None
        content_type_json = False

        # 4a. Form data (-F) - Higher priority
        form_match = re.search(r'(?:form|formulario)\s+(?:field|campo)\s+(["\']?)([^"\']+)\1\s+(?:with|con)\s+(?:file|archivo)\s+(["\']?)([^"\']+)\3', instruction, re.IGNORECASE)
        if form_match:
            field_name = form_match.group(2)
            file_path = form_match.group(4) # Needs validation/sanitization if path allowed
            options["-F"] = f"{field_name}=@{file_path}"
        else:
             # 4b. Data from file (-d @file)
             file_data_match = re.search(r'(?:data|datos)\s+(?:from|desde)\s+(?:file|archivo)\s+(["\']?)([^"\']+)\1', instruction, re.IGNORECASE)
             if file_data_match:
                 file_path = file_data_match.group(2) # Needs validation/sanitization
                 options["-d"] = f"@{file_path}"
             else:
                 # 4c. URL Encoded data (--data-urlencode)
                 urlencode_match = re.search(r'(?:urlencoded|encoded)\s+(?:data|datos)\s+(["\']?)(.+?)\1(?:\s|$)', instruction, re.IGNORECASE)
                 if urlencode_match:
                     # Use a non-greedy match for the data
                     options["--data-urlencode"] = urlencode_match.group(2).strip()
                 else:
                     # 4d. Inline data (-d) - Lowest priority for data types
                     # Look for explicit data keywords followed by quoted string or JSON structure
                     inline_data_match = re.search(
                         r'(?:data|datos|body|cuerpo|payload|json)\s*[:=]?\s*'
                         r'(?:(["\'])(.*?)\1|(\{.*?\})|(\[.*?\]))', # Quoted string OR {json} OR [json_array]
                         instruction, re.IGNORECASE | re.DOTALL # DOTALL for multiline JSON
                     )
                     if inline_data_match:
                         # Extract data from the correct group
                         data_payload = inline_data_match.group(2) or inline_data_match.group(3) or inline_data_match.group(4)
                         data_payload = data_payload.strip()
                         if data_payload:
                             options["-d"] = data_payload
                             # Check if it looks like JSON or was explicitly mentioned
                             if inline_data_match.group(3) or inline_data_match.group(4) or \
                                re.search(r'\bjson\b', inline_data_match.group(0) or '', re.IGNORECASE): # Check keyword near data
                                 content_type_json = True


        # 5. Headers (-H) - Detect multiple headers, including common ones
        # Initialize headers list (crucial for append logic)
        headers_list = []

        # Add Content-Type if JSON data was detected
        if content_type_json:
            headers_list.append("Content-Type: application/json")

        # General Header Pattern
        header_pattern = r'(?:header|cabecera|encabezado)\s*[:=]?\s*(["\']?)([\w-]+:\s*.*?)\1(?=[\s,\.]|$)' # Header: Value (non-greedy value)
        for match in re.finditer(header_pattern, instruction, re.IGNORECASE):
            header = match.group(2).strip()
            if header not in headers_list: # Avoid duplicates
                headers_list.append(header)

        # Specific Header Patterns (like Authorization)
        auth_header_match = re.search(r'(?:auth(?:orization)?|autorizaci[oó]n)\s*[:=]?\s*(["\']?)(\w+\s+[^"\']+?)\1', instruction, re.IGNORECASE)
        if auth_header_match:
            header = f"Authorization: {auth_header_match.group(2).strip()}"
            if header not in headers_list:
                headers_list.append(header)

        bearer_match = re.search(r'(?:bearer|token)\s*[:=]?\s*(["\']?)([^"\']+?)\1', instruction, re.IGNORECASE)
        if bearer_match and not any(h.lower().startswith("authorization:") for h in headers_list): # Avoid adding if already added via auth_header_match
             header = f"Authorization: Bearer {bearer_match.group(2).strip()}"
             if header not in headers_list:
                 headers_list.append(header)

        # Add detected headers to options (only if list is not empty)
        if headers_list:
            options["-H"] = headers_list


        # 6. User Agent (-A)
        ua_match = re.search(r'(?:user[-\s]*agent|agente\s*de\s*usuario|as|como)\s+["\']?(iphone|android|chrome|firefox|safari|bot|curl)[\'"]?', instruction, re.IGNORECASE)
        custom_ua_match = re.search(r'(?:user[-\s]*agent|agente\s*de\s*usuario)\s*[:=]?\s*(["\'])(.+?)\1', instruction, re.IGNORECASE)

        if ua_match:
            agent_key = ua_match.group(1).lower()
            user_agents = {
                "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "android": "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
                "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
                "bot": "Googlebot/2.1 (+http://www.google.com/bot.html)",
                 "curl": f"curl/{subprocess.check_output(['curl', '--version']).decode().split()[1]}" # Get actual curl version
            }
            options["-A"] = user_agents.get(agent_key, user_agents["chrome"]) # Default to Chrome if unknown keyword
        elif custom_ua_match:
            options["-A"] = custom_ua_match.group(2).strip()

        # 7. Save to File (-o)
        save_match = re.search(r'(?:save|guardar|salvar|write|escribir)\s+(?:to|en|as|como)\s+(?:file|archivo)?\s*["\']?([^"\']+)["\']?', instruction, re.IGNORECASE)
        if save_match:
             filename = save_match.group(1).strip()
             options["-o"] = sanitize_filename(filename) # Sanitize the filename
        elif re.search(r'\b(save|guardar|salvar|output|salida)\b', instruction, re.IGNORECASE): # Save without specific name
            path = urlparse(result_data["url"]).path
            filename = path.split('/')[-1] if path and path != '/' else "output.html"
            if not filename: filename = "output.html"
            options["-o"] = sanitize_filename(filename) # Sanitize default name too


        # 8. Verbose (-v)
        if re.search(r'\b(verbose|detallado|details|detalles)\b', instruction, re.IGNORECASE):
            options["-v"] = True

        # 9. Silent (-s) - Can override verbose if specified
        if re.search(r'\b(silent|silencioso|quiet|callado)\b', instruction, re.IGNORECASE):
            options["-s"] = True
            if "-v" in options: del options["-v"] # -s usually overrides -v

        # 10. Include Headers in Output (-i)
        if re.search(r'\b(include|incluir|show|mostrar|with)\s+headers\b', instruction, re.IGNORECASE) and "-I" not in options:
             options["-i"] = True


        # 11. Authentication (-u user:pass)
        # Pattern 1: user X and password Y
        auth_match1 = re.search(r'(?:user|usuario)\s+["\']?([^"\']+)["\']?\s+(?:and|y|with|con)\s+(?:password|pass|contraseña)\s+["\']?([^"\']+)["\']?', instruction, re.IGNORECASE)
        # Pattern 2: auth user:pass
        auth_match2 = re.search(r'(?:auth(?:entication)?|autenticaci[oó]n)\s*[:=]?\s*["\']?([^:"]+):([^"\']+)["\']?', instruction, re.IGNORECASE)

        username, password = None, None
        if auth_match1:
            username, password = auth_match1.group(1), auth_match1.group(2)
        elif auth_match2:
            username, password = auth_match2.group(1), auth_match2.group(2) # Corrected group indices

        if username and password:
            options["-u"] = f"{username}:{password}"
            # Create display_options ONLY if needed (i.e., auth found)
            result_data["display_options"] = options.copy() # Start with a copy of real options
            result_data["display_options"]["-u"] = f"{username}:********" # Mask password


        # 12. Insecure SSL (-k)
        if re.search(r'(?:insecure|unsafe|skip|salta(?:r)?|ignore|ignora(?:r)?)\s+(?:ssl|cert|verification|verificaci[oó]n)', instruction, re.IGNORECASE):
            options["-k"] = True

        # 13. Timeout (-m seconds)
        timeout_match = re.search(r'(?:timeout|wait|espera|limit(?:e)?)\s*(?:of|de)?\s*(\d+)\s*(?:s|sec|segundos?)?', instruction, re.IGNORECASE)
        if timeout_match:
            options["-m"] = timeout_match.group(1)

        # 14. Proxy (-x host:port)
        proxy_match = re.search(r'(?:proxy|through|via|trav[eé]s\s+de)\s+["\']?([\w.-]+:\d+)["\']?', instruction, re.IGNORECASE)
        if proxy_match:
            options["-x"] = proxy_match.group(1)

        # --- Final check and return ---
        return result_data

    except Exception as e:
         # Log the detailed error server-side
         print(f"Error during parsing instruction: '{instruction}'\n{type(e).__name__}: {e}")
         # Return a dictionary indicating failure
         result_data["error"] = f"Internal error during parsing: {str(e)}"
         return result_data


def execute_curl(options: dict, url: str) -> dict:
    """Execute the curl command with the parsed options and return structured result."""
    result_info = {
        "output": "",
        "error": None,
        "return_code": None
    }
    try:
        # Build command list using the helper
        curl_command_list = build_curl_command_list(options, url)

        # Execute the command
        process = subprocess.run(
            curl_command_list,
            capture_output=True,
            text=True,
            check=False, # Don't raise exception on non-zero exit code
            timeout=int(options.get("-m", 30)) + 5 # Set a process timeout slightly larger than curl's -m
        )

        result_info["return_code"] = process.returncode
        result_info["output"] = process.stdout

        # Handle errors - check return code first
        if process.returncode != 0:
            # Prepend stderr to stdout if there's an error message
            error_output = process.stderr.strip()
            if error_output:
                 # Try to give a more specific error if possible
                 if "Could not resolve host" in error_output:
                      result_info["error"] = f"DNS Error: Could not resolve host '{urlparse(url).hostname}'."
                 elif "Connection refused" in error_output:
                      result_info["error"] = f"Connection Error: Connection refused by server."
                 elif "timed out" in error_output:
                      result_info["error"] = f"Timeout Error: The connection timed out."
                 else:
                      result_info["error"] = f"Curl Error (Exit Code {process.returncode}): {error_output}"
                 # Append stderr to the main output for context
                 result_info["output"] += f"\n--- STDERR ---\n{error_output}"
            else:
                result_info["error"] = f"Curl failed with exit code {process.returncode} (no stderr message)."

        # Specific handling for HEAD (-I) redirects (informational, not an error)
        elif "-I" in options and not options.get("-L", False): # If -I used and -L not explicitly requested
            if any(f"HTTP/{v} 30" in process.stdout for v in ["1.0", "1.1", "2"]): # Check for 30x status codes
                 location = None
                 for line in process.stdout.splitlines():
                     if line.lower().startswith("location:"):
                         location = line.split(":", 1)[1].strip()
                         break
                 if location:
                     # Append info message to the output, don't set as error
                     result_info["output"] += f"\n--- Info ---\nRedirect detected to: {location}\n(Use '-L' or 'follow redirects' to follow)"

        return result_info

    except subprocess.TimeoutExpired:
        result_info["error"] = f"Process Timeout: The curl command took too long to execute (exceeded timeout)."
        result_info["return_code"] = -1 # Indicate timeout
        return result_info
    except FileNotFoundError:
        result_info["error"] = "Execution Error: 'curl' command not found. Is curl installed and in the system's PATH?"
        result_info["return_code"] = -1
        return result_info
    except Exception as e:
        # Catch other potential errors during execution (e.g., invalid arguments passed somehow)
        print(f"Error executing curl command: {curl_command_list}\n{type(e).__name__}: {e}")
        result_info["error"] = f"Internal error during execution: {str(e)}"
        result_info["return_code"] = -1
        return result_info

if __name__ == "__main__":
    # Create welcome banner
    title = Text("Curl MCP Service", style="bold magenta")
    subtitle = Text("Natural Language Curl Command Interface", style="cyan")
    
    # Show startup banner
    console.print(Panel.fit(
        f"{title}\n{subtitle}",
        border_style="bright_blue",
        padding=(1, 2)
    ))
    
    try:
        console.print("[green]Starting MCP service...[/]")
        mcp.run(transport="stdio")
        console.print("[green]Service running. Press Ctrl+C to stop.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down service...[/]")
        exit(0)
    except Exception as e:
        console.print(f"[red]Error starting service: {str(e)}[/]")
        exit(1)