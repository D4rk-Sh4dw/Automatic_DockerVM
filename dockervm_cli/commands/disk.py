import typer
import questionary
import subprocess
import os
import json
from dockervm_cli.utils import run_command, console, DVM_BASE_PATH

app = typer.Typer(help="Verwaltung von Festplatten und Laufwerken (vdisks).")

def get_available_disks():
    """Returns a list of available disks that are not mounted."""
    try:
        # Get disks using lsblk (excluding loop devices, only disks)
        result = subprocess.run(
            ['lsblk', '-d', '-n', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT'],
            capture_output=True, text=True, check=True
        )
        
        disks = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split()
            # If length is >= 3, name, size, type (and optionally mountpoint)
            if len(parts) >= 3:
                name = parts[0]
                size = parts[1]
                disk_type = parts[2]
                
                # We usually want to ignore cdroms and loops, only look at 'disk'
                if disk_type != 'disk':
                    continue
                
                # Check if it has a mountpoint in the output
                if len(parts) > 3:
                    continue  # already mounted at root level
                
                # Furthermore, check if partitions exist and are mounted
                part_result = subprocess.run(
                    ['lsblk', f'/dev/{name}', '-n', '-o', 'MOUNTPOINT'],
                    capture_output=True, text=True
                )
                if any(x.strip() for x in part_result.stdout.strip().split('\n')):
                    continue # Some partition is mounted
                    
                disks.append(f"/dev/{name} ({size})")
                
        return disks
    except Exception as e:
        console.print(f"[bold red]Fehler beim Abrufen der Festplatten: {e}[/bold red]")
        return []

@app.command("mount")
def mount_disk():
    """
    Formatiert eine neue vdisk und bindet sie automatisch ein.
    """
    console.print("[bold blue]Laufwerk einbinden und formatieren[/bold blue]")
    
    # 1. Festplattenauswahl
    disks = get_available_disks()
    
    if not disks:
        console.print("[yellow]Keine unformatierten/unmontierten Festplatten gefunden.[/yellow]")
        raise typer.Exit()
        
    selected_disk_str = questionary.select(
        "Welche Festplatte möchtest du formatieren und einbinden?",
        choices=disks
    ).ask()
    
    if not selected_disk_str:
        raise typer.Exit()
        
    selected_disk = selected_disk_str.split()[0]  # Get /dev/sdX
    
    # 2. Warnung und Bestätigung
    console.print(f"\n[bold red]WARNUNG:[/bold red] Alle Daten auf [cyan]{selected_disk}[/cyan] werden unwiderruflich gelöscht!")
    if not questionary.confirm("Bist du sicher, dass du diese Festplatte formatieren möchtest?", default=False).ask():
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    # 3. Mount-Point abfragen
    mount_point = questionary.text(
        "Wo soll die Festplatte eingebunden werden (z.B. /mnt/data)?",
        default="/mnt/volumes"
    ).ask()
    
    if not mount_point:
        raise typer.Exit()
        
    # 4. Formatieren (Ext4)
    console.print(f"\n[blue]Formatiere {selected_disk} mit ext4...[/blue]")
    if not run_command(f"sudo mkfs.ext4 -F {selected_disk}", desc="Formatiere Laufwerk"):
        console.print("[bold red]Fehler beim Formatieren der Festplatte.[/bold red]")
        raise typer.Exit(code=1)
        
    # 5. UUID ermitteln
    try:
        uuid_result = subprocess.run(
            ['sudo', 'blkid', '-s', 'UUID', '-o', 'value', selected_disk],
            capture_output=True, text=True, check=True
        )
        disk_uuid = uuid_result.stdout.strip()
    except Exception as e:
        console.print(f"[bold red]Konnte UUID nicht ermitteln: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # 6. Mountpoint erstellen
    run_command(f"sudo mkdir -p {mount_point}", desc=f"Erstelle Mountpoint {mount_point}")
    
    # 7. fstab Eintrag hinzufügen
    fstab_entry = f"UUID={disk_uuid} {mount_point} ext4 defaults 0 2\n"
    
    # Check if UUID already in fstab
    with open('/etc/fstab', 'r') as f:
        fstab_content = f.read()
        
    if disk_uuid not in fstab_content and mount_point not in fstab_content:
        console.print("[blue]Füge Eintrag zur /etc/fstab hinzu...[/blue]")
        # Write to temp file and move to avoid echo sudo permission issues
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fstab", delete=False) as tf:
            tf.write(fstab_content + fstab_entry)
            tmp_fstab = tf.name
            
        run_command(f"sudo cp /etc/fstab /etc/fstab.backup", desc="Erstelle Backup von /etc/fstab")
        run_command(f"sudo mv {tmp_fstab} /etc/fstab", desc="Aktualisiere /etc/fstab")
        run_command("sudo chown root:root /etc/fstab && sudo chmod 644 /etc/fstab", desc="Setze Berechtigungen für /etc/fstab")
    else:
        console.print("[yellow]Festplatte oder Mountpoint bereits in /etc/fstab vorhanden.[/yellow]")

    # 8. Mounten
    console.print(f"[blue]Binde Festplatte unter {mount_point} ein...[/blue]")
    if run_command("sudo mount -a", desc="Lade fstab neu und mounte"):
        # Zugriffsrechte anpassen (optional, aber hilfreich)
        run_command(f"sudo chown -R $USER:$USER {mount_point}", desc=f"Passe Zugriffsrechte für {mount_point} an")
        console.print(f"\n[bold green]Festplatte erfolgreich formatiert und unter {mount_point} eingebunden![/bold green]")
    else:
        console.print("[bold red]Fehler beim Einbinden der Festplatte.[/bold red]")
        raise typer.Exit(code=1)

@app.command("docker-storage")
def docker_storage():
    """
    Ändert den Docker Speicherort (data-root) für Images, Volumes etc.
    """
    console.print("[bold blue]Docker Speicherort ändern (data-root)[/bold blue]")
    
    # 1. Neuen Pfad abfragen
    default_new_path = f"{DVM_BASE_PATH}/docker_data"
    new_path = questionary.text(
        "Neuer Basis-Pfad für Docker (wird bei Bedarf erstellt):",
        default=default_new_path
    ).ask()
    
    if not new_path:
        raise typer.Exit()
        
    # 2. Aktuellen Pfad ermitteln
    current_path = "/var/lib/docker"
    try:
        # Falls Docker läuft, echten Pfad abfragen
        result = subprocess.run(
            ['sudo', 'docker', 'info', '-f', '{{.DockerRootDir}}'],
            capture_output=True, text=True, check=True
        )
        out_path = result.stdout.strip()
        if out_path:
            current_path = out_path
    except Exception:
        pass
        
    if current_path.rstrip('/') == new_path.rstrip('/'):
        console.print("[yellow]Der neue Pfad ist identisch mit dem aktuellen Pfad. Nichts zu tun.[/yellow]")
        raise typer.Exit()
        
    console.print(f"\n[bold yellow]WARNUNG:[/bold yellow] Docker wird gestoppt und alle Container werden kurzzeitig unterbrochen.")
    if not questionary.confirm("Möchtest du fortfahren?", default=True).ask():
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    # 3. Docker stoppen
    console.print("[blue]Stoppe Docker Dienste...[/blue]")
    run_command("sudo systemctl stop docker docker.socket containerd", desc="Stoppe Docker und Containerd")
    
    # 4. Daten kopieren
    console.print(f"[blue]Kopiere Docker Daten von {current_path} nach {new_path}... (Das kann je nach Datenmenge dauern!)[/blue]")
    run_command(f"sudo mkdir -p {new_path}", desc="Erstelle neues Verzeichnis")
    
    run_command("sudo apt-get update && sudo apt-get install -y rsync", desc="Installiere Abhängigkeit: rsync", check=False)
    
    # WICHTIG: -aP behält Rechte, Time, etc. rsync ist sicherer als cp
    if not run_command(f"sudo rsync -aP {current_path}/ {new_path}/", desc="Kopiere Dateien via rsync (bitte warten)"):
        console.print("[bold red]Fehler beim Kopieren der Daten. Starte Docker neu mit altem Pfad...[/bold red]")
        run_command("sudo systemctl start docker docker.socket containerd", desc="Recovery: Starte Docker")
        raise typer.Exit(code=1)
        
    # 5. daemon.json anpassen
    console.print("[blue]Passe /etc/docker/daemon.json an...[/blue]")
    daemon_json_path = "/etc/docker/daemon.json"
    
    # Lese aktuelle Datei, falls sie existiert
    daemon_data = {}
    try:
        result = subprocess.run(['sudo', 'cat', daemon_json_path], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            daemon_data = json.loads(result.stdout.strip())
    except Exception:
        pass # Ignorieren falls nicht da oder kein valides JSON
        
    daemon_data["data-root"] = new_path
    
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(daemon_data, tf, indent=4)
            tmp_daemon = tf.name
            
        run_command(f"sudo mkdir -p /etc/docker", desc="Stelle sicher, dass /etc/docker existiert")
        run_command(f"sudo mv {tmp_daemon} {daemon_json_path}", desc="Setze Konfiguration in daemon.json")
    except Exception as e:
        console.print(f"[bold red]Fehler beim Speichern der daemon.json: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # Optional: Altes Verzeichnis umbenennen als Backup
    if questionary.confirm(f"Soll das alte Verzeichnis ({current_path}) als Backup behalten werden? (Nein = Löschen)", default=True).ask():
        run_command(f"sudo mv {current_path} {current_path}.backup", desc="Erstelle Backup des alten Verzeichnisses")
    else:
        run_command(f"sudo rm -rf {current_path}", desc="Lösche altes Verzeichnis")
        
    # 6. Docker neu starten
    console.print("[blue]Starte Docker Dienste neu...[/blue]")
    if run_command("sudo systemctl start docker docker.socket containerd", desc="Starte Docker mit neuem Speicherort"):
        console.print(f"\n[bold green]Docker Speicherort erfolgreich auf {new_path} geändert![/bold green]")
    else:
        console.print("[bold red]Kritischer Fehler: Docker konnte nicht neu gestartet werden. Bitte manuell prüfen![/bold red]")
        raise typer.Exit(code=1)

@app.command("docker-clean-backup")
def docker_clean_backup():
    """
    Löscht ein altes Docker Volume Backup, falls dieses verschoben wurde.
    """
    console.print("[bold blue]Lösche Docker Backup[/bold blue]")
    
    backup_path = questionary.text(
        "Pfad zum alten Docker Backup:",
        default="/var/lib/docker.backup"
    ).ask()
    
    if not backup_path:
        raise typer.Exit()
        
    # Sicherheitsabfrage
    if backup_path == "/" or backup_path == "/var/lib/docker" or backup_path == "/var/lib":
        console.print(f"[bold red]WARNUNG: Der Pfad '{backup_path}' ist potenziell gefährlich und wurde abgelehnt![/bold red]")
        raise typer.Exit(code=1)
        
    # Check if exists (with sudo via ls)
    result = subprocess.run(["sudo", "test", "-d", backup_path])
    if result.returncode != 0:
        console.print(f"[yellow]Das Verzeichnis '{backup_path}' wurde nicht gefunden oder es ist kein Verzeichnis.[/yellow]")
        raise typer.Exit()
        
    console.print(f"\n[bold red]WARNUNG:[/bold red] Alle Dateien in [cyan]{backup_path}[/cyan] werden unwiderruflich gelöscht!")
    if not questionary.confirm("Bist du sicher, dass du das Backup löschen möchtest?", default=False).ask():
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    console.print(f"[blue]Lösche {backup_path}...[/blue]")
    if run_command(f"sudo rm -rf {backup_path}", desc="Lösche Backup-Verzeichnis"):
        console.print(f"[bold green]Backup erfolgreich gelöscht![/bold green]")
    else:
        console.print("[bold red]Fehler beim Löschen des Backups.[/bold red]")
        raise typer.Exit(code=1)


