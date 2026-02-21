
import typer
from dockervm_cli.utils import run_command, console, get_docker_compose_cmd, get_host_ip, DVM_BASE_PATH

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

    # General Configuration
    console.print("\n[yellow]Allgemeine Konfiguration:[/yellow]")
    base_volume_path = questionary.text("Basis-Pfad für Volumes:", default=DVM_BASE_PATH).ask()
    gui_port = questionary.text("GUI Port für Dockhand:", default="3000").ask()
        
    # Prepare directory
    install_dir = f"{base_volume_path}/dockhand"
    run_command(f"sudo mkdir -p {install_dir}", desc=f"Erstelle Installationsverzeichnis: {install_dir}")
    
    # Docker Compose Content
    # Using bind mounts relative to the compose file to store data in the selected volume path
    compose_content = f"""services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: {pg_user}
      POSTGRES_PASSWORD: {pg_password}
      POSTGRES_DB: {pg_db}
    volumes:
      - {base_volume_path}/dockhand/postgres_data:/var/lib/postgresql/data
    restart: always

  dockhand:
    image: fnsys/dockhand:latest
    ports:
      - {gui_port}:3000
    environment:
      DATABASE_URL: postgres://{pg_user}:{pg_password}@postgres:5432/{pg_db}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - {base_volume_path}/dockhand/dockhand_data:/app/data
      - {base_volume_path}:{base_volume_path}
    depends_on:
      - postgres
    restart: always
"""
    
    # Write docker-compose.yml
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(compose_content)
            tmp_compose = f.name
        run_command(f"sudo mv {tmp_compose} {install_dir}/docker-compose.yml", desc="Schreibe docker-compose.yml")
    except Exception as e:
        console.print(f"[bold red]Fehler beim Schreiben der Konfiguration: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # Start Dockhand
    console.print("[bold blue]Starte Dockhand...[/bold blue]")
    compose_cmd = get_docker_compose_cmd()
    if run_command(f"cd {install_dir} && sudo {compose_cmd} up -d", desc=f"Führe {compose_cmd} up aus"):
        host_ip = get_host_ip()
        console.print(f"[bold green]Dockhand erfolgreich installiert![/bold green]")
        console.print(f"Zugriff unter: [link]http://{host_ip}:{gui_port}[/link]")
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
    Installiert ZSH, Oh My Zsh, Powerlevel10k und nützliche Plugins.
    Folgt dem Guide: Setup Zsh on Ubuntu (How and Why).
    """
    import questionary
    import os
    import re
    
    console.print("[bold blue]Installation von ZSH & Oh My Zsh (Ultimate Edition)[/bold blue]")
    
    # 1. System Update & Install Packages
    # Added dconf-cli as requested
    console.print("[blue]1. Aktualisiere System und installiere Pakete...[/blue]")
    if not run_command("sudo apt update && sudo apt install -y zsh git curl fonts-powerline dconf-cli", desc="Installiere ZSH, Git, Fonts, dconf-cli"):
        raise typer.Exit(code=1)
        
    console.print("[green]Pakete installiert.[/green]")
    
    # 2. Install Oh My Zsh
    if questionary.confirm("Möchtest du 'Oh My Zsh' installieren? (Erforderlich für Setup)", default=True).ask():
        # Check if already installed
        if os.path.exists(os.path.expanduser("~/.oh-my-zsh")):
             console.print("[yellow]Oh My Zsh ist bereits installiert.[/yellow]")
        else:
            # Run install script unattended
            console.print("[blue]2. Installiere Oh My Zsh...[/blue]")
            cmd = 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'
            if run_command(cmd, desc="Installiere Oh My Zsh"):
                console.print("[green]Oh My Zsh installiert![/green]")
            else:
                console.print("[red]Fehler bei der Installation von Oh My Zsh.[/red]")
                raise typer.Exit(code=1)
    
    zsh_custom = os.path.expanduser("~/.oh-my-zsh/custom")

    # 3. Install Powerlevel10k Theme
    p10k_path = f"{zsh_custom}/themes/powerlevel10k"
    if not os.path.exists(p10k_path):
        console.print("[blue]3. Installiere Powerlevel10k Theme...[/blue]")
        run_command(f"git clone --depth=1 https://github.com/romkatv/powerlevel10k.git {p10k_path}", desc="Klone Powerlevel10k")
    else:
        console.print("[yellow]Powerlevel10k ist bereits installiert.[/yellow]")

    # 4. Install Plugins
    console.print("[blue]4. Installiere Plugins (Autosuggestions & Syntax Highlighting)...[/blue]")
    
    # Autosuggestions
    if not os.path.exists(f"{zsh_custom}/plugins/zsh-autosuggestions"):
        run_command(f"git clone https://github.com/zsh-users/zsh-autosuggestions {zsh_custom}/plugins/zsh-autosuggestions", desc="Klone zsh-autosuggestions")
        
    # Syntax Highlighting
    if not os.path.exists(f"{zsh_custom}/plugins/zsh-syntax-highlighting"):
        run_command(f"git clone https://github.com/zsh-users/zsh-syntax-highlighting.git {zsh_custom}/plugins/zsh-syntax-highlighting", desc="Klone zsh-syntax-highlighting")

    # 5. Configure .zshrc
    console.print("[blue]5. Konfiguriere .zshrc...[/blue]")
    if questionary.confirm("Soll ich die .zshrc automatisch anpassen (Theme & Plugins)?", default=True).ask():
        zshrc_path = os.path.expanduser("~/.zshrc")
        try:
            with open(zshrc_path, "r") as f:
                content = f.read()
            
            # Update Theme
            # Replace ZSH_THEME="..." with ZSH_THEME="powerlevel10k/powerlevel10k"
            if "powerlevel10k/powerlevel10k" not in content:
                content = re.sub(r'ZSH_THEME=".*?"', 'ZSH_THEME="powerlevel10k/powerlevel10k"', content)
                console.print("[green]Theme auf Powerlevel10k gesetzt.[/green]")

            # Update Plugins
            # Replace plugins=(...) with plugins=(git zsh-autosuggestions zsh-syntax-highlighting)
            # We look for the standard plugins=(git) or similar
            if "plugins=(git)" in content:
                content = content.replace("plugins=(git)", "plugins=(git zsh-autosuggestions zsh-syntax-highlighting)")
                console.print("[green]Plugins aktiviert.[/green]")
            elif "zsh-autosuggestions" not in content:
                # Fallback: Try regex if it's not the default string
                console.print("[yellow]Konnte 'plugins=(git)' nicht exakt finden. Füge Plugins manuell hinzu oder prüfe .zshrc.[/yellow]")

            with open(zshrc_path, "w") as f:
                f.write(content)
            
            console.print("[green].zshrc erfolgreich aktualisiert![/green]")
            
        except Exception as e:
            console.print(f"[red]Fehler beim Bearbeiten der .zshrc: {e}[/red]")

    # 6. Set Default Shell
    if questionary.confirm("Möchtest du ZSH als Standard-Shell setzen?", default=True).ask():
        user = os.environ.get("USER")
        zsh_path = "/usr/bin/zsh"
        
        console.print(f"[blue]Setze Standard-Shell für {user}...[/blue]")
        # chsh -s /usr/bin/zsh
        # We try to run it directly for the user. It might ask for password.
        if run_command(f"sudo chsh -s {zsh_path} {user}", desc=f"Setze Shell auf {zsh_path}"):
             console.print("[bold green]Standard-Shell geändert! Bitte ab- und wieder anmelden.[/bold green]")
        else:
             console.print("[bold red]Konnte Shell nicht ändern. Bitte manuell 'chsh -s /usr/bin/zsh' ausführen.[/bold red]")

    console.print("\n[bold yellow]WICHTIG:[/bold yellow]")
    console.print("1. Schließe dieses Terminal und öffne ein neues.")
    console.print("2. Beim ersten Start wirst du gefragt, Powerlevel10k zu konfigurieren.")
    console.print("   Falls nicht, tippe: [bold]p10k configure[/bold]")
    console.print("3. Viel Spaß mit deiner neuen Shell! 🚀")


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
    # Resolve relative to the package location (works from any CWD)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
    
    if not os.path.isdir(templates_dir):
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
    default_install_dir = f"{DVM_BASE_PATH}/{selected_template}"
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
    
    # Use tempfile for CWD-independent tmp file handling
    try:
        import tempfile
        
        # Write new .env
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            for k, v in user_env_values.items():
                f.write(f"{k}={v}\n")
            tmp_env = f.name
        
        run_command(f"sudo mv {tmp_env} {install_dir}/.env", desc="Schreibe .env Konfiguration")
        
        # Copy docker-compose.yml
        with open(compose_path, "r") as f:
            compose_content = f.read()
            
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(compose_content)
            tmp_compose = f.name
            
        run_command(f"sudo mv {tmp_compose} {install_dir}/docker-compose.yml", desc="Kopiere docker-compose.yml")
        
        # Start container
        compose_cmd = get_docker_compose_cmd()
        if run_command(f"cd {install_dir} && sudo {compose_cmd} up -d", desc="Starte Container"):
            host_ip = get_host_ip()
            console.print(f"[bold green]{selected_template} erfolgreich installiert![/bold green]")
            console.print(f"Zugriff unter: [link]http://{host_ip}[/link] (Port siehe Template)")
        else:
            console.print(f"[bold red]Fehler beim Starten des Containers.[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]Systemfehler: {e}[/bold red]")


@app.command("dns-server")
def install_dns_server():
    """
    Installiert den Unified DNS Server (AdGuard + Technitium Dashboard).
    """
    import questionary
    import os
    import subprocess
    import tempfile
    
    console.print("[bold blue]DNS Server Installation[/bold blue]")
    
    BASE_URL = "https://raw.githubusercontent.com/D4rk-Sh4dw/dns-server/main"
    
    if not questionary.confirm("Möchtest du den DNS Server installieren?").ask():
        raise typer.Exit()
    
    # 1. Choose install path
    default_dir = f"{DVM_BASE_PATH}/dns-server"
    install_dir = questionary.text("Installationsverzeichnis:", default=default_dir).ask()
    
    if not install_dir:
        console.print("[red]Pfad darf nicht leer sein![/red]")
        raise typer.Exit(code=1)
    
    if os.path.exists(install_dir):
        if not questionary.confirm(f"Verzeichnis {install_dir} existiert bereits. Überschreiben?", default=False).ask():
            console.print("[yellow]Abbruch.[/yellow]")
            raise typer.Exit()
    
    # 2. Create directory structure
    run_command(f"sudo mkdir -p {install_dir}/config/adguard", desc="Erstelle Verzeichnisstruktur")
    run_command(f"sudo mkdir -p {install_dir}/data", desc="Erstelle Datenverzeichnis")
    
    # 3. Fix Port 53 (systemd-resolved)
    console.print("\n[yellow]Pruefe Port 53 (systemd-resolved)...[/yellow]")
    
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", "systemd-resolved"],
        capture_output=True
    )
    
    if result.returncode == 0:
        if questionary.confirm(
            "systemd-resolved ist aktiv und blockiert Port 53. Soll es deaktiviert werden? (Empfohlen)",
            default=True
        ).ask():
            run_command("sudo systemctl stop systemd-resolved", desc="Stoppe systemd-resolved")
            run_command("sudo systemctl disable systemd-resolved", desc="Deaktiviere systemd-resolved")
            run_command("sudo rm -f /etc/resolv.conf", desc="Entferne alte resolv.conf")
            
            # Write resolv.conf via tempfile (reliable across all shells)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
                f.write("nameserver 1.1.1.1\nnameserver 8.8.8.8\n")
                tmp_resolv = f.name
            run_command(f"sudo mv {tmp_resolv} /etc/resolv.conf", desc="Setze DNS Server (1.1.1.1, 8.8.8.8)")
            
            # Verify DNS works
            if not run_command("ping -c 1 -W 3 github.com", desc="Pruefe DNS Aufloesung", check=False):
                console.print("[yellow]DNS scheint noch nicht zu funktionieren. Bitte /etc/resolv.conf pruefen.[/yellow]")
        else:
            console.print("[yellow]Port 53 koennte blockiert sein. DNS Server startet ggf. nicht.[/yellow]")
    else:
        console.print("[green]systemd-resolved ist nicht aktiv - Port 53 ist frei.[/green]")
    
    # 4. Download files
    console.print("\n[blue]Lade Konfigurationsdateien herunter...[/blue]")
    if not run_command(
        f"sudo wget -O {install_dir}/docker-compose.yml '{BASE_URL}/docker-compose.yml'",
        desc="Lade docker-compose.yml"
    ):
        console.print("[bold red]Download fehlgeschlagen. Bitte Internetverbindung/DNS pruefen.[/bold red]")
        raise typer.Exit(code=1)
    
    if not run_command(
        f"sudo wget -O {install_dir}/config/adguard/AdGuardHome.yaml '{BASE_URL}/config/adguard/AdGuardHome.yaml'",
        desc="Lade AdGuard Home Konfiguration"
    ):
        console.print("[bold red]Download fehlgeschlagen.[/bold red]")
        raise typer.Exit(code=1)
    
    # 5. Start containers
    console.print("\n[bold blue]Starte DNS Server...[/bold blue]")
    compose_cmd = get_docker_compose_cmd()
    if run_command(f"cd {install_dir} && sudo {compose_cmd} up -d", desc=f"Fuehre {compose_cmd} up aus"):
        host_ip = get_host_ip()
        console.print(f"\n[bold green]DNS Server erfolgreich installiert![/bold green]")
        console.print(f"Dashboard: [link]http://{host_ip}/[/link]")
        console.print(f"Installationspfad: {install_dir}")
    else:
        console.print("[bold red]Fehler beim Starten des DNS Servers.[/bold red]")
        raise typer.Exit(code=1)


@app.command("gdu")
def install_gdu():
    """
    Installiert gdu (Go Disk Usage Analyzer).
    """
    console.print("[bold blue]Installiere gdu...[/bold blue]")
    
    if run_command("sudo apt update && sudo apt install -y gdu", desc="Installiere gdu"):
        console.print("[bold green]gdu erfolgreich installiert![/bold green]")
        console.print("Starte es mit dem Befehl: [bold cyan]gdu[/bold cyan]")
    else:
        console.print("[bold red]Fehler bei der Installation von gdu.[/bold red]")
        raise typer.Exit(code=1)


