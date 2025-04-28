import sys
from main import mcp
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

def main():
    console = Console()
    
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
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error starting service: {str(e)}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()