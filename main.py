from mcp.server.fastmcp import FastMCP
import subprocess
import json
import re
from urllib.parse import urlparse 

mcp = FastMCP("curl-mcp")

@mcp.tool()
async def curl(instruction: str) -> str:
    """
    Execute a curl command based on natural language instructions.
    
    Args:
        instruction: A natural language description of the curl request to make.
        
    Returns:
        The output of the curl command and the actual command executed.
    """
    # Check if raw output is requested
    raw_output = re.search(r'(?:raw|crudo|consola|terminal)', instruction, re.IGNORECASE)
    
    # Parse the natural language instruction
    try:
        curl_options = parse_instruction(instruction)
        
        # Execute the parsed curl command
        result = execute_curl(curl_options)
        
        # Check if the result indicates an error happened during execution
        if result.startswith("Error executing curl:") or result.startswith("Error parsing instruction:"):
             return f"Failed Command: {curl_options.get('command_string', 'N/A')}\n\n{result}"

        if raw_output:
            return result
        else:
            # Ensure command_string is available even if parsing failed partially
            cmd_str = curl_options.get('command_string', 'Could not generate command string.')
            return f"Command executed: {cmd_str}\n\nResult:\n{result}"

    except Exception as e:
         # Catch potential errors during parsing itself
         return f"Error processing instruction: {str(e)}"


def parse_instruction(instruction: str) -> dict:
    """Parse a natural language instruction into curl command options."""
    curl_options = {
        "base_command": ["curl"],
        "url": "",
        "options": {},
        "command_string": "" # Initialize command_string
    }
    
    try:
        # Extract URL - be more aggressive in finding URLs
        url_patterns = [
            r'https?://[^\s"\'<>]+',  # Standard URL
            r'(?:site|sitio|website|web|url)[:\s]+([^\s"\'<>,]+)', # Site: example.com
            r'(?:to|a)[:\s]+([^\s"\'<>,]+\.[a-z]{2,})' # to: example.com
        ]
        
        extracted_url = None
        for pattern in url_patterns:
            url_match = re.search(pattern, instruction, re.IGNORECASE) # Ignore case here too
            if url_match:
                # Prefer group 1 if it exists (for patterns like 'site: example.com')
                url = url_match.group(1) if len(url_match.groups()) > 0 and url_match.group(1) else url_match.group(0)
                url = url.strip('.,:;"\'') # Clean trailing punctuation
                # Add http:// if no protocol is specified
                if not re.match(r'^https?://', url, re.IGNORECASE):
                    url = 'http://' + url
                extracted_url = url
                break # Stop after first match

        if not extracted_url:
             # Fallback: Try to find something that looks like a domain name if no explicit URL found
             domain_match = re.search(r'([\w-]+\.[\w.-]+)', instruction)
             if domain_match:
                  url = domain_match.group(1)
                  if not re.match(r'^https?://', url, re.IGNORECASE):
                      url = 'http://' + url
                  extracted_url = url

        if not extracted_url:
            raise ValueError("Could not extract a valid URL from the instruction.") # Raise error if no URL

        curl_options["url"] = extracted_url

        # --- Method and Header Logic ---
        is_head_request = False
        if re.search(r'\bhead\b|encabezado|cabecera', instruction, re.IGNORECASE):
             is_head_request = True
        if re.search(r'(?:solo|solamente|only|just)\s+(?:headers|header|encabezado|cabecera|encabezados|cabeceras)', instruction, re.IGNORECASE):
             is_head_request = True

        if is_head_request:
            curl_options["options"]["-I"] = True
            # Generally, don't follow redirects with HEAD, but could be made optional
            # curl_options["options"]["-L"] = False # Explicitly disable redirect following for HEAD?
        else:
             # Set method if not HEAD
            if re.search(r'post|POST|envía|enviar|send|submit', instruction, re.IGNORECASE):
                curl_options["options"]["-X"] = "POST"
            elif re.search(r'put|PUT|actualiza|actualizar|update', instruction, re.IGNORECASE):
                curl_options["options"]["-X"] = "PUT"
            elif re.search(r'delete|DELETE|elimina|eliminar|remove', instruction, re.IGNORECASE):
                curl_options["options"]["-X"] = "DELETE"
            # Default to GET if no other method specified and not HEAD
            
            # Add -L (follow redirects) by default for non-HEAD requests
            curl_options["options"]["-L"] = True


        # Detect data to send with POST/PUT - Improved Regex (needs refinement)
        # This regex is still basic. Consider more robust parsing if complex data is needed.
        data_match = re.search(r'(?:(?:con|with|using)\s+(?:data|datos|body|cuerpo|payload)|data|datos|body|cuerpo)[:=\s]+(["\']?)(.+?)\1(?:\s|$)|\b(json|JSON)[:=\s]+(["\']?)(.+?)\4(?:\s|$)', instruction, re.IGNORECASE | re.DOTALL)
        if data_match:
            data = data_match.group(2) or data_match.group(5) # Get data from either pattern part
            data = data.strip()
            if data:
                # If JSON keyword was used or data looks like JSON, add header
                if (data_match.group(3) and data_match.group(3).lower() == 'json') or \
                   (data.startswith('{') and data.endswith('}')) or \
                   (data.startswith('[') and data.endswith(']')):
                    # Handle multiple headers correctly
                    if "-H" in curl_options["options"]:
                         if isinstance(curl_options["options"]["-H"], list):
                              curl_options["options"]["-H"].append("Content-Type: application/json")
                         else: # Convert to list if it was a single string
                              curl_options["options"]["-H"] = [curl_options["options"]["-H"], "Content-Type: application/json"]
                    else:
                         curl_options["options"]["-H"] = "Content-Type: application/json"

                # Handle multiple data fields correctly (though curl usually takes one -d, use --data-urlencode for multiple)
                # This simplistic approach overwrites previous -d if multiple matches occur.
                curl_options["options"]["-d"] = data

        # Enhanced data handling
        data_patterns = [
            (r'(?:datos|data|body)\s+desde\s+archivo\s+(["\']?)([^"\']+)\1', 'file'),
            (r'(?:form|formulario)\s+(["\']?)([^"\']+)\1\s+(?:con|with)\s+archivo\s+(["\']?)([^"\']+)\3', 'form'),
            (r'(?:urlencoded|encoded)\s+data\s+(["\']?)([^"\']+)\1', 'urlencoded')
        ]
        
        for pattern, data_type in data_patterns:
            data_match = re.search(pattern, instruction, re.IGNORECASE)
            if data_match:
                if data_type == 'file':
                    curl_options["options"]["-d"] = f"@{data_match.group(2)}"
                elif data_type == 'form':
                    form_field = data_match.group(2)
                    filename = data_match.group(4)
                    curl_options["options"]["-F"] = f'{form_field}=@{filename}'
                elif data_type == 'urlencoded':
                    curl_options["options"]["--data-urlencode"] = data_match.group(2)
                break
        
        # Detect user agent changes 
        ua_match = re.search(r'(?:user\s*agent|agente\s*de\s*usuario|como|as)\s+(iphone|android|chrome|firefox|safari)', instruction, re.IGNORECASE)
        if ua_match:
            user_agents = {
                "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "android": "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
                "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
            }
            agent_name = ua_match.group(1).lower()
            curl_options["options"]["-A"] = user_agents.get(agent_name, user_agents["chrome"]) # Default to chrome if strange match
        # else: No default user-agent unless explicitly requested? Or keep chrome default?
        #     curl_options["options"]["-A"] = user_agents["chrome"] # Optional: uncomment to set default chrome always

        # Detect save to file
        if re.search(r'(?:save|guardar|salvar|file|archivo)\b', instruction, re.IGNORECASE):
            file_match = re.search(r'(?:as|como|to|en|llamado|named)\s+([^\s"\'<>,]+(?:\.[\w]+)?)', instruction, re.IGNORECASE)
            if file_match:
                filename = file_match.group(1)
                # Basic sanitization (replace potentially unsafe chars) - Needs more robust sanitization for security
                filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
                curl_options["options"]["-o"] = filename
            else:
                # Default filename based on URL if available and no name specified
                if curl_options["url"]:
                    path = urlparse(curl_options["url"]).path
                    # Basic filename extraction
                    filename = path.split('/')[-1] if path and path != '/' else "output.html"
                    filename = re.sub(r'[\\/*?:"<>|]', '_', filename) # Sanitize default name too
                    if not filename: # Handle case where path ends in /
                         filename = "output.html"
                    curl_options["options"]["-o"] = filename
                else:
                     curl_options["options"]["-o"] = "output.file" # Fallback filename

        # Detect verbose request
        if re.search(r'\b(verbose|detallado|details|detalles)\b', instruction, re.IGNORECASE):
            curl_options["options"]["-v"] = True

        # Enhanced header detection
        header_patterns = [
            r'(?:header|cabecera|encabezado)[:\s]+(["\']?)([\w-]+:\s*[^"\']+)\1',  # explicit headers
            r'(?:auth(?:orization)?|autorización)[:\s]+(["\']?)(\w+\s+[^"\']+)\1',  # auth headers
            r'(?:bearer|token)[:\s]+(["\']?)([^"\']+)\1'  # bearer tokens
        ]
        
        for pattern in header_patterns:
            header_matches = re.finditer(pattern, instruction, re.IGNORECASE)
            for match in header_matches:
                header_value = match.group(2).strip()
                
                # Handle special cases
                if match.re.pattern == header_patterns[1]:  # auth header
                    header_value = f"Authorization: {header_value}"
                elif match.re.pattern == header_patterns[2]:  # bearer token
                    header_value = f"Authorization: Bearer {header_value}"
                
                # Add to headers list
                if "-H" in curl_options["options"]:
                    if isinstance(curl_options["options"]["-H"], list):
                        if header_value not in curl_options["options"]["-H"]:
                            curl_options["options"]["-H"].append(header_value)
                    else:
                        curl_options["options"]["-H"] = [curl_options["options"]["-H"], header_value]
                else:
                    curl_options["options"]["-H"] = [header_value]

        # Authentication detection
        auth_patterns = [
            r'(?:con|with|usando|use)\s+(?:usuario|user|login)\s+(["\']?)([^"\']+)\1\s+(?:y|and|con|with)\s+(?:password|contraseña|pass)\s+(["\']?)([^"\']+)\3',
            r'(?:auth|authentication|autenticación)[:=\s]+(["\']?)([^:]+):([^"\']+)\1'
        ]
        
        for pattern in auth_patterns:
            auth_match = re.search(pattern, instruction, re.IGNORECASE)
            if auth_match:
                if len(auth_match.groups()) == 4:  # First pattern
                    username, password = auth_match.group(2), auth_match.group(4)
                else:  # Second pattern
                    username, password = auth_match.group(6), auth_match.group(7)
                
                curl_options["options"]["-u"] = f"{username}:{password}"
                # Mask sensitive info in command string
                curl_options["display_options"] = curl_options["options"].copy()
                curl_options["display_options"]["-u"] = f"{username}:****"
                break

        # --- Build the command string for display ---
        cmd_parts = curl_options["base_command"].copy()
        # Handle multiple headers (-H) and potentially other multi-value options
        for option, value in curl_options["options"].items():
             if isinstance(value, list): # Handle list values (e.g., multiple -H)
                  for item in value:
                       cmd_parts.append(option)
                       if item is not True:
                            # Basic quoting for display if value has spaces
                            cmd_parts.append(f'"{item}"' if ' ' in str(item) else str(item))
             elif value is True: # Boolean flags (like -L, -I, -v)
                  cmd_parts.append(option)
             else: # Single value options (like -X, -d, -o, -A)
                  cmd_parts.append(option)
                  # Basic quoting for display if value has spaces
                  cmd_parts.append(f'"{value}"' if ' ' in str(value) else str(value))

        if curl_options["url"]:
            cmd_parts.append(f'"{curl_options["url"]}"') # Quote URL for display
        curl_options["command_string"] = " ".join(cmd_parts)
        
        return curl_options
    
    except Exception as e:
         # If parsing fails, return a structure indicating failure
         curl_options["command_string"] = f"Error parsing instruction: {str(e)}"
         # Optionally, return the partially parsed options or raise the exception
         # For now, returning the dict with the error string
         print(f"Error during parsing: {e}") # Log error server-side
         # raise e # Or re-raise the exception
         return curl_options # Return dictionary even on partial failure for error reporting


def execute_curl(curl_options: dict) -> str:
    """Execute the curl command with the parsed options."""
    try:
        curl_command = curl_options["base_command"].copy()
        
        # Build command with options
        for option, value in curl_options["options"].items():
            curl_command.append(option)
            if value is not True:
                curl_command.append(str(value))
        
        curl_command.append(curl_options["url"])
        
        # First request - without following redirects
        if "-I" in curl_options["options"]:
            result = subprocess.run(
                curl_command,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.stdout:
                # Check for redirect
                if any(code in result.stdout for code in ["301", "302", "307", "308"]):
                    location = None
                    for line in result.stdout.splitlines():
                        if line.lower().startswith("location:"):
                            location = line.split(":", 1)[1].strip()
                            break
                    
                    if location and "-L" not in curl_options["options"]:
                        return (f"{result.stdout}\n"
                               f"Found redirect to: {location}\n"
                               f"Add -L to follow redirects.")
                return result.stdout
            return result.stderr
        
        # Non-header requests or requests with -L
        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            check=False
        )
        
        return result.stdout if result.stdout else result.stderr
        
    except Exception as e:
        return f"Error executing curl: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
