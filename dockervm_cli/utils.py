
import subprocess
import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

def run_command(command: str, desc: str = None, error_msg: str = None, check: bool = True) -> bool:
    """
    Runs a shell command and handles output/errors nicely with Rich.
    """
    if desc:
        console.print(f"[bold blue]ℹ️  {desc}...[/bold blue]")

    try:
        subprocess.run(
            command,
            shell=True,
            check=check,
            executable="/bin/bash",
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        if desc:
            console.print(f"[bold green]✔️  {desc} abgeschlossen.[/bold green]")
        return True
    except subprocess.CalledProcessError:
        if error_msg:
            console.print(f"[bold red]❌  {error_msg}[/bold red]")
        else:
            console.print(f"[bold red]❌  Befehl fehlgeschlagen: {command}[/bold red]")
        return False

def print_header(title: str):
    console.print(Panel(f"[bold yellow]{title}[/bold yellow]", expand=False))
