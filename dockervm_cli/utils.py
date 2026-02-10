
import subprocess
import sys
import tempfile
from rich.console import Console
from rich.panel import Panel

console = Console()

# Zentraler Basispfad für alle DVM Installationen
import os
try:
    with open("/etc/dvm/base_path", "r") as f:
        DVM_BASE_PATH = f.read().strip()
except Exception:
    DVM_BASE_PATH = "/mnt/volumes"

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
            print_error(error_msg)
        else:
            print_error(f"Befehl fehlgeschlagen: {command}")
        return False

def print_status(msg: str, nl: bool = True):
    console.print(f"[bold blue]ℹ️  {msg}[/bold blue]", end="\n" if nl else "")

def print_success(msg: str, nl: bool = True):
    console.print(f"[bold green]✔️  {msg}[/bold green]", end="\n" if nl else "")

def print_error(msg: str, nl: bool = True):
    console.print(f"[bold red]❌  {msg}[/bold red]", end="\n" if nl else "")

def get_docker_compose_cmd() -> str:
    """
    Detects if 'docker compose' (V2) or 'docker-compose' (V1) should be used.
    Checks with sudo since installation commands run with sudo.
    """
    try:
        # Check for V2 first (with sudo)
        result = subprocess.run(["sudo", "docker", "compose", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "docker compose"
    except Exception:
        pass

    try:
        # Check for V2 without sudo (fallback)
        result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "docker compose"
    except Exception:
        pass

    try:
        # Fallback to V1
        result = subprocess.run(["sudo", "docker-compose", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "docker-compose"
    except Exception:
        pass

    try:
        # Fallback to V1 without sudo
        result = subprocess.run(["docker-compose", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return "docker-compose"
    except Exception:
        pass

    # Default to docker compose if detection fails
    return "docker compose"

def get_host_ip() -> str:
    """
    Attempts to get the host's primary IP address.
    """
    try:
        # Simple method using hostname -I (Linux specific)
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        if result.returncode == 0:
            # Returns all IPs, take the first one
            ips = result.stdout.strip().split()
            if ips:
                return ips[0]
    except Exception:
        pass
    
    return "<deine-ip>"

def print_header(title: str):
    console.print(Panel(f"[bold yellow]{title}[/bold yellow]", expand=False))
