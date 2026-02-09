
import typer
from dockervm_cli.utils import run_command, console

app = typer.Typer(help="System- und Anwendungs-Updates verwalten.")

@app.command("system")
def update_system():
    """
    Aktualisiert Ubuntu Systempakete und Kernel.
    Entspricht apt update && apt upgrade.
    """
    import re
    
    console.print("[bold green]Starte System-Update...[/bold green]")
    
    # Apply Blacklist Holds from Unattended-Upgrades Config
    blacklist_file = "/etc/apt/apt.conf.d/51unattended-upgrades-blacklist"
    if os.path.exists(blacklist_file):
        try:
            with open(blacklist_file, "r") as f:
                content = f.read()
            
            # Extract regex patterns (simple parsing)
            # Looks for "package-name"; inside Unattended-Upgrade::Package-Blacklist { ... };
            # We assume standard formatting we wrote
            matches = re.findall(r'"([^"]+)";', content)
            
            if matches:
                console.print(f"[blue]Gefundene Blacklist-Muster: {len(matches)}. Setze Hold...[/blue]")
                
                # Get all installed packages
                result = subprocess.run("dpkg-query -f '${Package}\n' -W", shell=True, capture_output=True, text=True)
                installed_packages = result.stdout.splitlines()
                
                packages_to_hold = []
                for pattern in matches:
                    regex = re.compile(pattern)
                    for pkg in installed_packages:
                        if regex.match(pkg):
                            packages_to_hold.append(pkg)
                
                if packages_to_hold:
                    # Deduplicate
                    packages_to_hold = list(set(packages_to_hold))
                    
                    console.print(f"[yellow]Folgende Pakete auf der Blacklist wurden gefunden:[/yellow] {', '.join(packages_to_hold)}")
                    import questionary
                    if questionary.confirm("Möchtest du diese Pakete trotzdem aktualisieren? (Blacklist ignorieren)", default=False).ask():
                        console.print("[red]Entferne Hold für Update...[/red]")
                        unhold_cmd = f"sudo apt-mark unhold {' '.join(packages_to_hold)}"
                        run_command(unhold_cmd, desc="Entferne Hold Status")
                    else:
                        hold_cmd = f"sudo apt-mark hold {' '.join(packages_to_hold)}"
                        if run_command(hold_cmd, desc=f"Setze Hold für {len(packages_to_hold)} Pakete der Blacklist"):
                            console.print(f"[yellow]Gehaltene Pakete:[/yellow] {', '.join(packages_to_hold)}")
        except Exception as e:
            console.print(f"[red]Fehler beim Anwenden der Blacklist Holds: {e}[/red]")

    # Check for root privileges (can be done in a decorator, but simple check here first)
    # in real scenarios, use os.geteuid() == 0 check or similar
    
    # 1. Clean
    run_command("sudo apt clean -y", desc="Bereinige apt Cache")
    run_command("sudo apt autoremove -y", desc="Entferne ungenutzte Pakete")
    
    # 2. Update
    if not run_command("sudo apt update -y", desc="Aktualisiere Paketlisten"):
        raise typer.Exit(code=1)
    
    # 3. Upgrade
    if not run_command("sudo apt upgrade -y", desc="Aktualisiere Pakete"):
        raise typer.Exit(code=1)
        
    console.print("[bold green]System-Update abgeschlossen![/bold green]")


@app.command("self")
def update_self():
    """
    Aktualisiert das dockervm CLI Tool selbst via Git und reinstalliert es.
    """
    console.print("[bold blue]Aktualisiere dockervm CLI...[/bold blue]")
    
    if run_command("git pull", desc="Ziehe neueste Änderungen von Git"):
        # Re-install the package to apply changes
        if run_command("pip install .", desc="Installiere aktualisiertes Paket"):
             console.print("[bold green]Update erfolgreich! Bitte starten Sie das CLI neu.[/bold green]")
        else:
             console.print("[bold red]Fehler bei der Installation des Updates.[/bold red]")
             raise typer.Exit(code=1)
    else:
        console.print("[bold red]Fehler beim Git Pull.[/bold red]")
        raise typer.Exit(code=1)


@app.command("auto")
def configure_unattended():
    """
    Aktiviert automatische Sicherheitsupdates mittels unattended-upgrades (Empfohlen).
    """
    import questionary
    
    console.print("[bold blue]Aktiviere Unattended Upgrades...[/bold blue]")
    
    if run_command("sudo apt install -y unattended-upgrades", desc="Installiere unattended-upgrades"):
        # We use a simple non-interactive enablement
        # This creates /etc/apt/apt.conf.d/20auto-upgrades if not present
        # This creates /etc/apt/apt.conf.d/20auto-upgrades if not present
        config_content = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        
        try:
            with open("20auto-upgrades.tmp", "w") as f:
                f.write(config_content)
            
            if run_command("sudo mv 20auto-upgrades.tmp /etc/apt/apt.conf.d/20auto-upgrades", desc="Konfiguriere zuverlässige Auto-Upgrades"):
            # Ensure service is running
            run_command("sudo systemctl enable --now unattended-upgrades", desc="Starte unattended-upgrades Service")
            console.print("[bold green]Unattended Upgrades erfolgreich aktiviert![/bold green]")
        except Exception as e:
            console.print(f"[bold red]Fehler beim Konfigurieren: {e}[/bold red]")
            if os.path.exists("20auto-upgrades.tmp"):
                os.remove("20auto-upgrades.tmp")
            
            # Blacklist Configuration
            console.print("\n[bold yellow]Paket Blacklist Konfiguration[/bold yellow]")
            console.print("Du kannst verhindern, dass bestimmte Pakete automatisch aktualisiert werden, um die Stabilität zu gewährleisten.")
            
            common_packages = [
                questionary.Choice("NVIDIA Treiber (nvidia-driver, libnvidia-.*)", checked=True),
                questionary.Choice("CUDA Toolkit (cuda, libcuda.*)", checked=True),
                questionary.Choice("Docker Engine (docker-ce, docker-ce-cli)", checked=False),
                questionary.Choice("Containerd (containerd.io)", checked=False),
            ]
            
            selected = questionary.checkbox(
                "Wähle Pakete für die Blacklist:",
                choices=common_packages
            ).ask()
            
            blacklist_regex = []
            if "NVIDIA Treiber (nvidia-driver, libnvidia-.*)" in selected:
                blacklist_regex.append('"nvidia-driver";')
                blacklist_regex.append('"libnvidia-.*";')
            if "CUDA Toolkit (cuda, libcuda.*)" in selected:
                blacklist_regex.append('"cuda";')
                blacklist_regex.append('"libcuda.*";')
            if "Docker Engine (docker-ce, docker-ce-cli)" in selected:
                blacklist_regex.append('"docker-ce";')
                blacklist_regex.append('"docker-ce-cli";')

            if "Containerd (containerd.io)" in selected:
                blacklist_regex.append('"containerd.io";')
                
            # Custom Regex Input
            custom = questionary.text("Gib eigene Regex für die Blacklist ein (kommagetrennt, leer lassen zum Überspringen):").ask()
            if custom:
                for item in custom.split(","):
                    clean_item = item.strip()
                    if clean_item:
                        blacklist_regex.append(f'"{clean_item}";')

            # Package Search
            if questionary.confirm("Möchtest du nach installierten Paketen für die Blacklist suchen?").ask():
                console.print("[blue]Lade installierte Pakete...[/blue]")
                try:
                    # Get list of installed packages
                    result = subprocess.run("dpkg-query -f '${Package}\n' -W", shell=True, capture_output=True, text=True)
                    installed_packages = result.stdout.splitlines()
                    
                    while True:
                        pkg = questionary.autocomplete(
                            "Tippe zum Suchen eines Pakets (TAB zum Vervollständigen):",
                            choices=installed_packages
                        ).ask()
                        
                        if pkg:
                            console.print(f"[green]{pkg} zur Blacklist hinzugefügt.[/green]")
                            blacklist_regex.append(f'"{pkg}";')
                        
                        if not questionary.confirm("Nach einem weiteren Paket suchen?").ask():
                            break
                except Exception as e:
                    console.print(f"[bold red]Fehlerbeim Abrufen der Pakete: {e}[/bold red]")
            
            if blacklist_regex:
                blacklist_content = 'Unattended-Upgrade::Package-Blacklist {\n' + '\n    '.join(blacklist_regex) + '\n};\n'
                
                # Write to a separate file to avoid overwriting default config
                blacklist_file = "/etc/apt/apt.conf.d/51unattended-upgrades-blacklist"
                
                # Using a temporary file approach to write with sudo
                try:
                    with open("blacklist.tmp", "w") as f:
                        f.write(blacklist_content)
                    
                    run_command(f"sudo mv blacklist.tmp {blacklist_file}", desc="Schreibe Blacklist Konfiguration")
                    console.print(f"[bold green]Blacklist gespeichert in {blacklist_file}[/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Fehler beim Schreiben der Blacklist: {e}[/bold red]")
            else:
                 console.print("[yellow]Keine Pakete für die Blacklist ausgewählt.[/yellow]")

        else:
            console.print("[bold red]Fehler beim Konfigurieren der Auto-Upgrades.[/bold red]")
    else:
        console.print("[bold red]Fehler beim Installieren von unattended-upgrades.[/bold red]")

@app.command("dockhand")
def update_dockhand():
    """
    Aktualisiert Dockhand Container (pull & up -d).
    """
    import os
    
    install_dir = "/mnt/volumes/dockhand"
    
    if not os.path.isdir(install_dir):
        console.print(f"[bold red]Dockhand Verzeichnis nicht gefunden unter {install_dir}. Ist es installiert?[/bold red]")
        raise typer.Exit(code=1)
        
    console.print("[bold blue]Aktualisiere Dockhand...[/bold blue]")
    
    # Docker Compose Pull
    if not run_command(f"cd {install_dir} && sudo docker compose pull", desc="Ziehe neueste Images"):
        raise typer.Exit(code=1)
        
    # Docker Compose Up
    if run_command(f"cd {install_dir} && sudo docker compose up -d", desc="Starte Container neu"):
        console.print("[bold green]Dockhand erfolgreich aktualisiert![/bold green]")
    else:
        raise typer.Exit(code=1)


@app.command("mail")
def configure_mail():
    """
    Konfiguriert E-Mail-Benachrichtigungen (via msmtp SMTP-Relay).
    """
    import questionary
    
    console.print("[bold blue]Konfiguration E-Mail Benachrichtigungen (SMTP)[/bold blue]")
    
    # 1. Install Dependencies
    if not run_command("sudo apt install -y msmtp msmtp-mta bsd-mailx", desc="Installiere Mail-Tools (msmtp, bsd-mailx)"):
        console.print("[bold red]Fehler bei der Installation der Abhängigkeiten.[/bold red]")
        raise typer.Exit(code=1)
        
    # 2. SMTP Configuration
    console.print("\n[yellow]SMTP Server Daten:[/yellow]")
    smtp_host = questionary.text("SMTP Server (z.B. smtp.gmail.com):").ask()
    smtp_port = questionary.text("SMTP Port:", default="587").ask()
    smtp_user = questionary.text("SMTP Benutzer / E-Mail:").ask()
    smtp_pass = questionary.password("SMTP Passwort:").ask()
    from_addr = questionary.text("Absender E-Mail:", default=smtp_user).ask()
    
    if not smtp_host or not smtp_user or not smtp_pass:
        console.print("[red]Alle Felder sind erforderlich![/red]")
        raise typer.Exit(code=1)
        
    msmtp_config = f"""# Set default values for all following accounts.
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        /var/log/msmtp.log

# Account
account        default
host           {smtp_host}
port           {smtp_port}
from           {from_addr}
user           {smtp_user}
password       {smtp_pass}
"""
    
    # Write msmtprc
    try:
        with open("msmtprc.tmp", "w") as f:
            f.write(msmtp_config)
            
        run_command("sudo mv msmtprc.tmp /etc/msmtprc", desc="Schreibe SMTP Konfiguration")
        run_command("sudo chmod 600 /etc/msmtprc", desc="Setze Berechtigungen (600)")
        run_command("sudo ln -sf /usr/bin/msmtp /usr/sbin/sendmail", desc="Verlinke sendmail zu msmtp")
    except Exception as e:
        console.print(f"[bold red]Fehler beim Speichern der Konfiguration: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # 3. Notification Preferences
    console.print("\n[yellow]Benachrichtigungs-Einstellungen:[/yellow]")
    recipient = questionary.text("Empfänger E-Mail:", default=from_addr).ask()
    only_on_error = questionary.confirm("Nur bei Fehlern benachrichtigen?", default=True).ask()
    
    apt_conf_content = f'Unattended-Upgrade::Mail "{recipient}";\n'
    if only_on_error:
        apt_conf_content += 'Unattended-Upgrade::MailOnlyOnError "true";\n'
    else:
        apt_conf_content += 'Unattended-Upgrade::MailOnlyOnError "false";\n'
        
    try:
        with open("51unattended-upgrades-email.tmp", "w") as f:
            f.write(apt_conf_content)
        run_command("sudo mv 51unattended-upgrades-email.tmp /etc/apt/apt.conf.d/51unattended-upgrades-email", desc="Aktiviere Unattended-Upgrades Benachrichtigung")
    except Exception as e:
         console.print(f"[bold red]Fehler: {e}[/bold red]")
         
    console.print("[bold green]Konfiguration abgeschlossen![/bold green]")
    
    # 4. Test Email
    if questionary.confirm("Test-E-Mail senden?").ask():
        console.print(f"[blue]Sende Test-E-Mail an {recipient}...[/blue]")
        test_cmd = f"echo 'Dies ist eine Test-Nachricht von DockerVM.' | mail -s 'DockerVM SMTP Test' {recipient}"
        if run_command(test_cmd, desc="Sende E-Mail"):
            console.print("[bold green]E-Mail gesendet! Bitte Posteingang prüfen.[/bold green]")
        else:
            console.print("[bold red]Fehler beim Senden. Bitte Serverdaten prüfen.[/bold red]")
