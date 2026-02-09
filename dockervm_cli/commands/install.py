
import typer
from dockervm_cli.utils import run_command, console

app = typer.Typer(help="Install applications and services.")

@app.command("docker")
def install_docker():
    """
    Installiert Docker Engine und Docker Compose.
    """
    console.print("[bold green]Installiere Docker...[/bold green]")
    
    commands = [
        "sudo apt update",
        "sudo apt install -y ca-certificates curl gnupg lsb-release",
        "sudo mkdir -p /etc/apt/keyrings",
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
        "sudo apt update",
        "sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        "sudo usermod -aG docker $USER"
    ]
    
    for cmd in commands:
        if not run_command(cmd, desc=f"Führe aus: {cmd[:40]}..."):
            console.print("[bold red]Fehler bei der Installation von Docker.[/bold red]")
            raise typer.Exit(code=1)

    console.print("[bold green]Docker erfolgreich installiert![/bold green]")

@app.command("dockhand")
def install_dockhand():
    """
    Installiert Dockhand (Alternative zu Portainer) mit Postgres.
    """
    import questionary
    import os
    
    console.print("[bold blue]Dockhand Installation[/bold blue]")
    
    if not questionary.confirm("Möchtest du Dockhand und Postgres installieren?").ask():
        raise typer.Exit()
        
    # Postgres Configuration
    console.print("\n[yellow]Konfiguriere Postgres Datenbank-Zugangsdaten:[/yellow]")
    pg_user = questionary.text("Postgres Benutzer:", default="dockhand").ask()
    pg_password = questionary.password("Postgres Passwort:").ask()
    pg_db = questionary.text("Postgres Datenbankname:", default="dockhand").ask()
    
    if not pg_password:
        console.print("[red]Passwort darf nicht leer sein![/red]")
        raise typer.Exit(code=1)
        
    # Prepare directory
    install_dir = "/mnt/volumes/dockhand"
    run_command(f"sudo mkdir -p {install_dir}", desc=f"Erstelle Installationsverzeichnis: {install_dir}")
    
    # Docker Compose Content
    # Using bind mounts relative to the compose file to store data in /mnt/volumes/dockhand
    compose_content = f"""services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: {pg_user}
      POSTGRES_PASSWORD: {pg_password}
      POSTGRES_DB: {pg_db}
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
    restart: always

  dockhand:
    image: fnsys/dockhand:latest
    ports:
      - 3000:3000
    environment:
      DATABASE_URL: postgres://{pg_user}:{pg_password}@postgres:5432/{pg_db}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./dockhand_data:/app/data
    depends_on:
      - postgres
    restart: always
"""
    
    # Write docker-compose.yml
    try:
        with open("docker-compose.yml", "w") as f:
            f.write(compose_content)
        run_command(f"sudo mv docker-compose.yml {install_dir}/docker-compose.yml", desc="Schreibe docker-compose.yml")
    except Exception as e:
        console.print(f"[bold red]Fehler beim Schreiben der Konfiguration: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # Start Dockhand
    console.print("[bold blue]Starte Dockhand...[/bold blue]")
    if run_command(f"cd {install_dir} && sudo docker compose up -d", desc="Führe docker compose up aus"):
        console.print(f"[bold green]Dockhand erfolgreich installiert![/bold green]")
        console.print(f"Zugriff unter: [link]http://<deine-ip>:3000[/link]")
    else:
        console.print("[bold red]Fehler beim Starten von Dockhand.[/bold red]")
        raise typer.Exit(code=1)
