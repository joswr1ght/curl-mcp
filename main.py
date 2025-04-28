from mcp.server.fastmcp import FastMCP
import subprocess
import json
import re

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
    # Parse the natural language instruction
    curl_options = parse_instruction(instruction)
    
    # Add common options that should be enabled by default
    curl_options["options"]["-L"] = True  # Follow redirects
    
    # Execute the parsed curl command
    result = execute_curl(curl_options)
    
    # Return both the command executed and the result
    return f"Command executed: {curl_options['command_string']}\n\nResult:\n{result}"

def parse_instruction(instruction: str) -> dict:
    """Parse a natural language instruction into curl command options."""
    curl_options = {
        "base_command": ["curl"],
        "url": "",
        "options": {},
        "command_string": ""
    }
    
    # Extract URL - be more aggressive in finding URLs
    url_patterns = [
        r'https?://[^\s"\'<>]+',  # Standard URL
        r'(?:site|sitio|website|web|url)[:\s]+([^\s"\'<>,]+)',  # Site: example.com
        r'(?:to|a)[:\s]+([^\s"\'<>,]+\.[a-z]{2,})' # to: example.com
    ]
    
    for pattern in url_patterns:
        url_match = re.search(pattern, instruction)
        if url_match:
            url = url_match.group(0) if '://' in url_match.group(0) else url_match.group(1)
            # Add http:// if no protocol is specified
            if not url.startswith('http'):
                url = 'http://' + url
            curl_options["url"] = url
            break
    
    # Detect request method - More inclusive patterns
    if re.search(r'post|POST|envía|enviar|send|submit', instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "POST"
    elif re.search(r'put|PUT|actualiza|actualizar|update', instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "PUT"
    elif re.search(r'delete|DELETE|elimina|eliminar|remove', instruction, re.IGNORECASE):
        curl_options["options"]["-X"] = "DELETE"
    elif re.search(r'head|HEAD|encabezado|headers|cabecera', instruction, re.IGNORECASE):
        curl_options["options"]["-I"] = True
    
    # Detect data to send with POST/PUT - More aggressive pattern
    data_match = re.search(r'(?:con|with|data|datos|body|cuerpo|parameters|parámetros)[:\s]+([^"\']*?)(?:$|\sy\s|and\s)', instruction, re.IGNORECASE)
    if data_match:
        data = data_match.group(1).strip()
        if data:
            # Try to auto-detect if it looks like JSON
            if (data.startswith('{') and data.endswith('}')) or (data.startswith('[') and data.endswith(']')):
                curl_options["options"]["-H"] = "Content-Type: application/json"
            curl_options["options"]["-d"] = data
    
    # Detect user agent changes 
    if re.search(r'(?:user\s*agent|agente)', instruction, re.IGNORECASE):
        # Common user agents
        user_agents = {
            "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "android": "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
            "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0",
            "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
        }
        
        # Match any known user agent type
        for agent_name, agent_string in user_agents.items():
            if agent_name in instruction.lower():
                curl_options["options"]["-A"] = agent_string
                break
        else:
            # Default to Chrome if no specific agent requested
            curl_options["options"]["-A"] = user_agents["chrome"]
    
    # Simplify header detection logic
    headers_only_pattern = re.search(r'(?:solo|solamente|only|just)\s+(?:headers|header|encabezado|cabecera|encabezados|cabeceras)', instruction, re.IGNORECASE)
    
    if headers_only_pattern:
        # Use -I for headers-only request and ensure -i is not set
        curl_options["options"]["-I"] = True
        curl_options["options"].pop("-i", None)
    else:
        # For normal requests, don't add any header flags
        curl_options["options"].pop("-I", None)
        curl_options["options"].pop("-i", None)
    
    if re.search(r'(?:save|guardar|salvar|file|archivo)', instruction, re.IGNORECASE):
        file_match = re.search(r'(?:as|como|to|en)[:\s]+([^\s"\'<>,]+\.[\w]+)', instruction, re.IGNORECASE)
        if file_match:
            curl_options["options"]["-o"] = file_match.group(1)
        else:
            # Default filename based on URL if available
            if curl_options["url"]:
                from urllib.parse import urlparse
                path = urlparse(curl_options["url"]).path
                filename = path.split('/')[-1] if path and path != '/' else "output.html"
                curl_options["options"]["-o"] = filename
    
    # Additional common curl options - always include useful ones without asking
    # Verbose if explicitly requested
    if re.search(r'(?:verbose|detallado|details|detalles)', instruction, re.IGNORECASE):
        curl_options["options"]["-v"] = True
    
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
            check=False
        )
        
        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"Error: {result.stderr}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")