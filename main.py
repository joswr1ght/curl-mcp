from mcp.server.fastmcp import FastMCP
import subprocess
import json
import re

# Initialize FastMCP server
mcp = FastMCP("curl-mcp")

@mcp.tool()
async def natural_language_curl(instruction: str) -> str:
    """
    Execute a curl command based on natural language instructions in English or Spanish.
    
    Args:
        instruction: A natural language description (English or Spanish) of the curl request to make.
        
    Returns:
        The output of the curl command and the actual command executed.
    """
    # Parse the natural language instruction
    curl_options = parse_instruction(instruction)
    
    # Execute the parsed curl command
    result = execute_curl(curl_options)
    
    # Return both the command executed and the result
    return f"Command executed: {curl_options['command_string']}\n\nResult:\n{result}"

def parse_instruction(instruction: str) -> dict:
    """Parse a natural language instruction (English or Spanish) into curl command options."""
    curl_options = {
        "base_command": ["curl"],
        "url": "",
        "options": {},
        "command_string": ""
    }
    
    # Extract URL
    url_match = re.search(r'https?://\S+', instruction)
    if url_match:
        curl_options["url"] = url_match.group(0)
    
    # Detect request method - Spanish and English patterns
    post_pattern = r'(haz|has|hacer|realiza|realice|ejecuta|ejecute|make|do|perform|execute|send|post)\s+(un|una|a)?\s*(petición|solicitud|request|método|method)?\s*(post|POST)'
    put_pattern = r'(haz|has|hacer|realiza|realice|ejecuta|ejecute|make|do|perform|execute|send|put)\s+(un|una|a)?\s*(petición|solicitud|request|método|method)?\s*(put|PUT)'
    delete_pattern = r'(haz|has|hacer|realiza|realice|ejecuta|ejecute|make|do|perform|execute|send|delete)\s+(un|una|a)?\s*(petición|solicitud|request|método|method)?\s*(delete|DELETE)'
    get_pattern = r'(haz|has|hacer|realiza|realice|ejecuta|ejecute|make|do|perform|execute|send|get)\s+(un|una|a)?\s*(petición|solicitud|request|método|method)?\s*(get|GET)'
    
    if re.search(post_pattern, instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "POST"
    elif re.search(put_pattern, instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "PUT"
    elif re.search(delete_pattern, instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "DELETE"
    elif re.search(get_pattern, instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "GET"
    
    # Detect data to send with POST/PUT - Spanish and English patterns
    data_patterns = [
        r'(?:datos|con|data|with)\s+(?:de\s+)?(?:los siguientes datos|the following data)?:?\s*([^y]*?)(?:\s+y\s+|$)',
        r'(?:send|enviar?|añadir|add)\s+(?:the|los|estos)?\s*(?:datos|data|parameters|parámetros):?\s*([^y]*?)(?:\s+y\s+|$)',
        r'(?:body|cuerpo)\s+(?:del mensaje|of the message|of request)?:?\s*([^y]*?)(?:\s+y\s+|$)'
    ]
    
    for pattern in data_patterns:
        data_match = re.search(pattern, instruction, re.IGNORECASE)
        if data_match:
            data = data_match.group(1).strip()
            if data:
                # Try to extract key-value pairs or just use as raw data
                curl_options["options"]["-d"] = data
                break
    
    # Detect JSON data
    json_patterns = [
        r'(?:json|JSON)[\s:]+(\{[^}]+\})',
        r'(?:con|with)\s+(?:el|the)?\s*json\s*(?:data|datos)?[\s:]+(\{[^}]+\})'
    ]
    
    for pattern in json_patterns:
        json_match = re.search(pattern, instruction)
        if json_match:
            json_data = json_match.group(1).strip()
            curl_options["options"]["-H"] = "Content-Type: application/json"
            curl_options["options"]["-d"] = json_data
            break
    
    # Detect user agent changes - Spanish and English patterns
    ua_patterns = [
        r'(cambia|cambiar|cambie|usa|usar|use|change|set|modify)\s+(el|mi|un|the|my|a)?\s*(?:user\s*agent|agente)\s+(?:a|al|como|de|to|as|of)\s+(un\s+)?([^.,]+)',
        r'(?:user\s*agent|agente)[\s:]+([^.,]+)'
    ]
    
    for pattern in ua_patterns:
        ua_match = re.search(pattern, instruction, re.IGNORECASE)
        if ua_match:
            # Different group index based on the pattern
            agent_type = ua_match.group(4 if len(ua_match.groups()) >= 4 else 1).strip().lower()
            
            # Define common user agents
            user_agents = {
                "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "android": "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
                "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
            }
            
            # Match the requested agent to our predefined ones
            for agent_name, agent_string in user_agents.items():
                if agent_name in agent_type:
                    curl_options["options"]["-A"] = agent_string
                    break
            else:
                # If no match, just use the description as is
                curl_options["options"]["-A"] = agent_type
            break
    
    # Detect authentication needs - Spanish and English patterns
    auth_patterns = [
        r'(usuario|user|username)[\s:]+([^\s,]+)[\s,]+(?:y\s+)?(contraseña|password|pass)[\s:]+([^\s,]+)',
        r'(autenticar?|authenticate|login|iniciar sesión)\s+(?:con|como|as|with)?\s+([^\s,]+)[\s,]+(?:y\s+)?(?:contraseña|password|pass)[\s:]+([^\s,]+)'
    ]
    
    for pattern in auth_patterns:
        auth_match = re.search(pattern, instruction, re.IGNORECASE)
        if auth_match:
            if len(auth_match.groups()) == 4:  # First pattern
                username = auth_match.group(2)
                password = auth_match.group(4)
            else:  # Second pattern
                username = auth_match.group(2)
                password = auth_match.group(3)
                
            curl_options["options"]["-u"] = f"{username}:{password}"
            break
    
    # Detect header requests - Spanish and English patterns
    header_patterns = [
        r'(agrega|añade|añada|agrega|incluye|incluir|con|add|include|with)\s+(el\s+)?header\s+([^.,]+)',
        r'(header|cabecera)[\s:]+([^.,]+)'
    ]
    
    for pattern in header_patterns:
        header_match = re.search(pattern, instruction, re.IGNORECASE)
        if header_match:
            header_content = header_match.group(3 if len(header_match.groups()) >= 3 else 2).strip()
            curl_options["options"]["-H"] = header_content
            break
    
    # Detect output file request - Spanish and English patterns
    output_patterns = [
        r'(guardar?|salvar?|guarda|salva|almacenar?|save|store|output)\s+(?:en|como|al archivo|to|as|in file)\s+([^\s,]+)',
        r'(output|salida)[\s:]+([^\s,]+)'
    ]
    
    for pattern in output_patterns:
        output_match = re.search(pattern, instruction, re.IGNORECASE)
        if output_match:
            output_file = output_match.group(2).strip()
            curl_options["options"]["-o"] = output_file
            break
    
    # Additional common curl options
    # Verbose
    if re.search(r'(verbose|detallado)', instruction, re.IGNORECASE):
        curl_options["options"]["-v"] = True
    
    # Follow redirects
    if re.search(r'(seguir|follow)\s+(redirecciones|redirects)', instruction, re.IGNORECASE):
        curl_options["options"]["-L"] = True
    
    # Silent mode
    if re.search(r'(silencioso|silent|quiet)', instruction, re.IGNORECASE):
        curl_options["options"]["-s"] = True
    
    # Build the command string for display
    cmd_parts = curl_options["base_command"].copy()
    for option, value in curl_options["options"].items():
        cmd_parts.append(option)
        if value is not True:  # Skip value for boolean flags
            cmd_parts.append(str(value))
    if curl_options["url"]:
        cmd_parts.append(curl_options["url"])
    curl_options["command_string"] = " ".join(cmd_parts)
    
    return curl_options

def execute_curl(curl_options: dict) -> str:
    """Execute the curl command with the parsed options."""
    try:
        curl_command = curl_options["base_command"].copy()
        
        for option, value in curl_options["options"].items():
            curl_command.append(option)
            if value is not True:  # Skip value for boolean flags
                curl_command.append(str(value))
        
        if curl_options["url"]:
            curl_command.append(curl_options["url"])
        
        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            check=False  # Changed to False to get error output too
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error (code {result.returncode}):\n{result.stderr}"
    except Exception as e:
        return f"Exception occurred: {str(e)}"

@mcp.tool()
async def execute_raw_curl(command: str, options: dict = None) -> str:
    """Execute a raw curl command with various options (advanced usage).

    Args:
        command: The URL to request.
        options: A dictionary of curl options and their values.

    Returns:
        The output of the curl command.
    """
    try:
        curl_command = ["curl"]

        if options:
            for option, value in options.items():
                if value is True:  # For flags like -f, -s, -v
                    curl_command.append(option)
                elif value:  # For options with arguments like -d, -o, -A
                    curl_command += [option, str(value)]

        curl_command.append(command)
        
        # Create a command string for display
        command_string = " ".join(curl_command)

        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return f"Command executed: {command_string}\n\nResult:\n{result.stdout}"
        else:
            return f"Command executed: {command_string}\n\nError (code {result.returncode}):\n{result.stderr}"
    except Exception as e:
        return f"Exception occurred: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")