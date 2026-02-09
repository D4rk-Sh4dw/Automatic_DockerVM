
import typer
from dockervm_cli.utils import run_command, console

app = typer.Typer(help="Anwendungen und Dienste installieren.")

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
      - /mnt/volumes/postgres_data:/var/lib/postgresql/data
    restart: always

  dockhand:
    image: fnsys/dockhand:latest
    ports:
      - 3000:3000
    environment:
      DATABASE_URL: postgres://{pg_user}:{pg_password}@postgres:5432/{pg_db}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /mnt/volumes/dockhand_data:/app/data
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


@app.command("lazydocker")
def install_lazydocker():
    """
    Installiert Lazydocker (Terminal UI für Docker).
    """
    console.print("[bold blue]Installiere Lazydocker...[/bold blue]")
    
    # Official install script - force installation to /usr/local/bin
    cmd = "export DIR=/usr/local/bin && curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash"
    
    if run_command(cmd, desc="Führe Lazydocker Installationsskript aus"):
        console.print("[bold green]Lazydocker erfolgreich installiert![/bold green]")
        console.print("Starte es mit dem Befehl: [bold cyan]lazydocker[/bold cyan]")
    else:
        console.print("[bold red]Fehler bei der Installation von Lazydocker.[/bold red]")
        raise typer.Exit(code=1)


@app.command("zsh")
def install_zsh():
    """
    Installiert ZSH und optional Oh My Zsh + Plugins.
    """
    import questionary
    import os
    
    console.print("[bold blue]Installation von ZSH & Oh My Zsh[/bold blue]")
    
    # 1. Install ZSH and dependencies
    if not run_command("sudo apt update && sudo apt install -y zsh git curl fonts-powerline", desc="Installiere ZSH Basispakete"):
        raise typer.Exit(code=1)
        
    console.print("[green]ZSH installiert.[/green]")
    
    # 2. Install Oh My Zsh
    if questionary.confirm("Möchtest du 'Oh My Zsh' installieren? (Empfohlen)", default=True).ask():
        # Check if already installed
        if os.path.exists(os.path.expanduser("~/.oh-my-zsh")):
             console.print("[yellow]Oh My Zsh ist bereits installiert.[/yellow]")
        else:
            # Run install script (unattended to avoid exit, but we want to configure it)
            # We use --unattended to prevent it from launching zsh immediately and stopping our script
            cmd = 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'
            if run_command(cmd, desc="Installiere Oh My Zsh"):
                console.print("[green]Oh My Zsh installiert![/green]")
            else:
                console.print("[red]Fehler bei der Installation von Oh My Zsh.[/red]")
    
    # 3. Plugins (Autosuggestions & Syntax Highlighting)
    if questionary.confirm("Sollen nützliche Plugins (Autosuggestions, Syntax Highlighting) installiert werden?", default=True).ask():
        zsh_custom = os.path.expanduser("~/.oh-my-zsh/custom")
        
        # Autosuggestions
        if not os.path.exists(f"{zsh_custom}/plugins/zsh-autosuggestions"):
            run_command(f"git clone https://github.com/zsh-users/zsh-autosuggestions {zsh_custom}/plugins/zsh-autosuggestions", desc="Klone zsh-autosuggestions")
            
        # Syntax Highlighting
        if not os.path.exists(f"{zsh_custom}/plugins/zsh-syntax-highlighting"):
            run_command(f"git clone https://github.com/zsh-users/zsh-syntax-highlighting.git {zsh_custom}/plugins/zsh-syntax-highlighting", desc="Klone zsh-syntax-highlighting")
            
        console.print("\n[bold yellow]Hinweis:[/bold yellow] Um die Plugins zu aktivieren, füge sie in deiner [bold]~/.zshrc[/bold] hinzu:")
        console.print("plugins=(git zsh-autosuggestions zsh-syntax-highlighting)")
        
        # Try to patch .zshrc automatically?
        if questionary.confirm("Soll ich die Plugins automatisch in die ~/.zshrc eintragen?", default=True).ask():
            zshrc_path = os.path.expanduser("~/.zshrc")
            try:
                with open(zshrc_path, "r") as f:
                    content = f.read()
                
                # Simple replacement for default config
                if "plugins=(git)" in content:
                    new_content = content.replace("plugins=(git)", "plugins=(git zsh-autosuggestions zsh-syntax-highlighting)")
                    with open(zshrc_path, "w") as f:
                        f.write(new_content)
                    console.print("[green]Plugins in .zshrc eingetragen![/green]")
                else:
                     console.print("[yellow]Konnte 'plugins=(git)' nicht finden. Bitte manuell anpassen.[/yellow]")
            except Exception as e:
                console.print(f"[red]Fehler beim Bearbeiten der .zshrc: {e}[/red]")

    # 4. Set Default Shell
    if questionary.confirm("Möchtest du ZSH als Standard-Shell setzen?", default=True).ask():
        # chsh requires password usually, run_command might prompt or fail if non-interactive sudo?
        # chsh -s $(which zsh) usually works for current user.
        user = os.environ.get("USER")
        zsh_path = "/usr/bin/zsh" # Standard path
        
        console.print("[blue]Setze Standard-Shell... (Passwort ggf. erforderlich)[/blue]")
        # We try without sudo first for current user
        if run_command(f"sudo chsh -s {zsh_path} {user}", desc=f"Setze Shell für {user}"):
            console.print("[bold green]Standard-Shell geändert! Bitte neu anmelden.[/bold green]")
        else:
             console.print("[bold red]Konnte Shell nicht ändern. Bitte manuell 'chsh -s $(which zsh)' ausführen.[/bold red]")


@app.command("container")
def install_container():
    """
    Installiert einen Container aus einem Template (z.B. Unifi Controller).
    """
    import questionary
    import os
    import sys
    import shutil
    
    console.print("[bold blue]Container Installation aus Template[/bold blue]")
    
    # 1. Find Templates
    # Assuming standard package structure: dockervm_cli/templates
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
    
    if not os.path.isdir(templates_dir):
        # Fallback for development / running from source root without install
        # Try local ./dockervm_cli/templates if running from repo root
        if os.path.isdir("dockervm_cli/templates"):
            templates_dir = "dockervm_cli/templates"
        else:
            console.print(f"[bold red]Template-Verzeichnis nicht gefunden: {templates_dir}[/bold red]")
            raise typer.Exit(code=1)
            
    # List subdirectories
    templates = [d for d in os.listdir(templates_dir) if os.path.isdir(os.path.join(templates_dir, d))]
    
    if not templates:
        console.print("[yellow]Keine Templates gefunden.[/yellow]")
        raise typer.Exit()
        
    # 2. Select Template
    selected_template = questionary.select(
        "Wähle einen Dienst zum Installieren:",
        choices=templates
    ).ask()
    
    template_path = os.path.join(templates_dir, selected_template)
    env_path = os.path.join(template_path, ".env")
    compose_path = os.path.join(template_path, "docker-compose.yml")
    
    if not os.path.exists(compose_path):
        console.print(f"[red]Fehler: docker-compose.yml fehlt im Template {selected_template}[/red]")
        raise typer.Exit(code=1)

    # 3. Parse .env and Prompt User
    user_env_values = {}
    
    if os.path.exists(env_path):
        console.print(f"\n[yellow]Konfiguration für {selected_template}:[/yellow]")
        with open(env_path, "r") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, default_value = line.split("=", 1)
                key = key.strip()
                default_value = default_value.strip()
                
                # Ask user
                value = questionary.text(f"{key}:", default=default_value).ask()
                user_env_values[key] = value
                
    # 4. Installation Directory
    default_install_dir = f"/mnt/volumes/{selected_template}"
    install_dir = questionary.text("Installationsverzeichnis:", default=default_install_dir).ask()
    
    if os.path.exists(install_dir):
        if not questionary.confirm(f"Verzeichnis {install_dir} existiert bereits. Überschreiben?", default=False).ask():
            console.print("[yellow]Abbruch.[/yellow]")
            raise typer.Exit()
            
    # 5. Deploy
    console.print(f"\n[blue]Installiere {selected_template} nach {install_dir}...[/blue]")
    run_command(f"sudo mkdir -p {install_dir}", desc="Erstelle Verzeichnis")
    
    # Copy docker-compose.yml
    # We use sudo cp via utils.run_command or just python shutil if we have permissions?
    # Better use sudo for /mnt/volumes
    
    # Temporary file approach for write/copy
    try:
        # Write new .env
        with open(".env.tmp", "w") as f:
            for k, v in user_env_values.items():
                f.write(f"{k}={v}\n")
        
        run_command(f"sudo mv .env.tmp {install_dir}/.env", desc="Schreibe .env Konfiguration")
        
        # Copy docker-compose.yml
        # Read content and write to tmp, then move
        with open(compose_path, "r") as f:
            compose_content = f.read()
            
        with open("docker-compose.yml.tmp", "w") as f:
            f.write(compose_content)
            
        run_command(f"sudo mv docker-compose.yml.tmp {install_dir}/docker-compose.yml", desc="Kopiere docker-compose.yml")
        
        # Start container
        if run_command(f"cd {install_dir} && sudo docker compose up -d", desc="Starte Container"):
            console.print(f"[bold green]{selected_template} erfolgreich installiert![/bold green]")
        else:
            console.print(f"[bold red]Fehler beim Starten des Containers.[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]Systemfehler: {e}[/bold red]")
        # Cleanup tmp files
        if os.path.exists(".env.tmp"): os.remove(".env.tmp")
        if os.path.exists("docker-compose.yml.tmp"): os.remove("docker-compose.yml.tmp")
