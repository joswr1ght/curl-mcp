# Curl MCP - Natural Language Curl Commander

Execute curl commands using natural language in English.

## Prerequisites

- Python 3.13 or higher
- curl installed on the system
  - On Windows: You can download curl from https://curl.se/windows/ or install it via winget
  - On Linux: Usually pre-installed, or install via your package manager
- Git

## Installation

1. Clone the repository:
```bash
git clone https://github.com/MartinPSDev/curl-mcp.git
cd curl-mcp
```

2. Create and activate a virtual environment (recommended):
```bash
# On Windows:
python -m venv .venv
.venv\Scripts\activate

# On Linux/macOS:
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. To use this MCP server in your development environment (VSCode, Cursor, Claude Desktop, etc.), you need to add the following configuration to your MCP settings:

For Windows:
```json
{
    "mcpServers": {
        "curl-mcp": {
            "command": "python",
            "args": [
                "C:\\path\\to\\your\\curl-mcp\\main.py"
            ],
            "env": {}
        }
    }
}
```

For Linux/macOS:
```json
{
    "mcpServers": {
        "curl-mcp": {
            "command": "/usr/bin/python3",
            "args": [
                "/path/to/your/curl-mcp/main.py"
            ],
            "env": {}
        }
    }
}
```

Note: Replace the path in the `args` section with the actual path where you cloned the repository, using the appropriate path format for your operating system.

2. The MCP server is now ready to use with your preferred development environment.

## Usage

1. Start the MCP server:
```bash
# On any platform:
python main.py
```

2. The server can now receive natural language commands. Here are some examples:

### Examples:
- "Make a POST request to https://example.com/api with data name=John and age=25"
- "Download https://example.com and save it as page.html"
- "Make a GET request to https://api.example.com/data and show the headers"