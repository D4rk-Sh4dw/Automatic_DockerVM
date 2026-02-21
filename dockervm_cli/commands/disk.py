import typer
import questionary
import subprocess
import os
import json
from dockervm_cli.utils import run_command, console, DVM_BASE_PATH

app = typer.Typer(help="Verwaltung von Festplatten und Laufwerken (vdisks).")

def get_expandable_partitions():
    """Returns a list of mounted partitions that could potentially be expanded."""
    try:
        # Get disks and partitions using lsblk
        result = subprocess.run(
            ['lsblk', '-P', '-b', '-o', 'NAME,TYPE,MOUNTPOINT,FSTYPE,SIZE,PKNAME,PARTN'],
            capture_output=True, text=True, check=True
        )
        
        partitions = []
        import shlex
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            # Simple parsing of KEY="VALUE" format
            props = {}
            parts = shlex.split(line)
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    props[k] = v
            
            # We want partitions (TYPE="part") OR full disks (TYPE="disk") that have a MOUNTPOINT and FSTYPE
            disk_type = props.get('TYPE')
            if disk_type in ('part', 'disk') and props.get('MOUNTPOINT') and props.get('FSTYPE'):
                size_bytes = int(props.get('SIZE', 0))
                # Convert bytes to human readable roughly for display
                if size_bytes > 1024**3:
                    size_str = f"{size_bytes / (1024**3):.1f} GB"
                elif size_bytes > 1024**2:
                    size_str = f"{size_bytes / (1024**2):.1f} MB"
                else:
                    size_str = f"{size_bytes} B"
                    
                name = props.get('NAME')
                mountpoint = props.get('MOUNTPOINT')
                fstype = props.get('FSTYPE')
                pkname = props.get('PKNAME', '')
                partn = props.get('PARTN', '')
                is_disk = (disk_type == 'disk')
                
                display_str = f"/dev/{name} ({size_str}) eingebunden auf {mountpoint} [{fstype}]"
                partitions.append({
                    "name": display_str,
                    "value": {
                        "dev": f"/dev/{name}",
                        "pkname": f"/dev/{pkname}" if pkname else "",
                        "partn": partn,
                        "mountpoint": mountpoint,
                        "fstype": fstype,
                        "is_disk": is_disk
                    }
                })
                
        return partitions
    except Exception as e:
        console.print(f"[bold red]Fehler beim Abrufen der Partitionen: {e}[/bold red]")
        return []

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
        
    # 4. Dateisystem abfragen
    fstype = questionary.select(
        "Welches Dateisystem soll verwendet werden?",
        choices=["ext4", "xfs", "btrfs"]
    ).ask()
    
    if not fstype:
        raise typer.Exit()
        
    # 5. Formatieren
    console.print(f"\n[blue]Formatiere {selected_disk} mit {fstype}...[/blue]")
    if fstype == "xfs":
        subprocess.run(["sudo", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_command("sudo apt-get install -y xfsprogs", desc="Installiere xfsprogs", check=False)
        format_cmd = f"sudo mkfs.xfs -f {selected_disk}"
    elif fstype == "btrfs":
        subprocess.run(["sudo", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_command("sudo apt-get install -y btrfs-progs", desc="Installiere btrfs-progs", check=False)
        format_cmd = f"sudo mkfs.btrfs -f {selected_disk}"
    else:
        format_cmd = f"sudo mkfs.ext4 -F {selected_disk}"

    if not run_command(format_cmd, desc=f"Formatiere Laufwerk ({fstype})"):
        console.print(f"[bold red]Fehler beim Formatieren der Festplatte mit {fstype}.[/bold red]")
        raise typer.Exit(code=1)
        
    # 6. UUID ermitteln
    try:
        uuid_result = subprocess.run(
            ['sudo', 'blkid', '-s', 'UUID', '-o', 'value', selected_disk],
            capture_output=True, text=True, check=True
        )
        disk_uuid = uuid_result.stdout.strip()
    except Exception as e:
        console.print(f"[bold red]Konnte UUID nicht ermitteln: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # 7. Mountpoint erstellen
    run_command(f"sudo mkdir -p {mount_point}", desc=f"Erstelle Mountpoint {mount_point}")
    
    # 8. fstab Eintrag hinzufügen
    fstab_entry = f"UUID={disk_uuid} {mount_point} {fstype} defaults 0 2\n"
    
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

    # 9. Mounten
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

@app.command("expand")
def expand_disk():
    """
    Vergrößert eine eingebundene Partition und deren Dateisystem (z.B. nach Vergrößerung der vdisk).
    """
    console.print("[bold blue]Laufwerk / Partition erweitern[/bold blue]")
    
    # 1. Partitionen abfragen
    partitions = get_expandable_partitions()
    
    if not partitions:
        console.print("[yellow]Keine erweiterbaren Partitionen gefunden.[/yellow]")
        raise typer.Exit()
        
    # 2. Auswahl
    selected = questionary.select(
        "Welche Partition möchtest du vergrößern?",
        choices=[p["name"] for p in partitions]
    ).ask()
    
    if not selected:
        raise typer.Exit()
        
    part_info = next((p["value"] for p in partitions if p["name"] == selected), None)
    if not part_info:
        raise typer.Exit()
        
    dev = part_info["dev"]
    pkname = part_info["pkname"]
    partn = part_info["partn"]
    mountpoint = part_info["mountpoint"]
    fstype = part_info["fstype"]
    is_disk = part_info.get("is_disk", False)
    
    console.print(f"\nDu hast [cyan]{dev}[/cyan] ausgewählt ({mountpoint}, [yellow]{fstype}[/yellow]).")
    if is_disk:
        console.print("Es handelt sich um ein vollständiges Laufwerk (keine Partitionen).")
    else:
        console.print(f"Diese Partition liegt auf [cyan]{pkname}[/cyan] (Partition {partn}).")
        
    console.print(f"\n[bold yellow]HINWEIS:[/bold yellow] Diese Aktion vergrößert den Speicherplatz auf den maximal verfügbaren Bereich.")
    if not questionary.confirm("Möchtest du fortfahren?", default=False).ask():
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    if not is_disk and pkname and partn:
        # 3. Abhängigkeit prüfen/installieren
        console.print("[blue]Prüfe Abhängigkeiten (cloud-guest-utils für growpart)...[/blue]")
        subprocess.run(["sudo", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_command("sudo apt-get install -y cloud-guest-utils", desc="Installiere cloud-guest-utils", check=False)
        
        # 4. Partition erweitern mit growpart
        console.print(f"[blue]Erweitere Partition {partn} auf {pkname}...[/blue]")
        # growpart liefert Exit Code 1, wenn kein Platz mehr da ist (NOCHANGE). Das ist normal und kein echter "Fehler", wenn man's wiederholt.
        growpart_result = subprocess.run(['sudo', 'growpart', pkname, partn], capture_output=True, text=True)
        if growpart_result.returncode == 0:
            console.print("[green]Partition erfolgreich vergrößert![/green]")
        elif "NOCHANGE" in growpart_result.stdout or "NOCHANGE" in growpart_result.stderr:
            console.print("[yellow]Die Partition belegt bereits den maximal verfügbaren Platz. Dateisystem wird trotzdem überprüft...[/yellow]")
        else:
            console.print(f"[bold red]Fehler bei growpart:[/bold red]\n{growpart_result.stderr or growpart_result.stdout}")
            # Wir machen trotzdem weiter, evtl. ist growpart gescheitert weil xfs_growfs reicht oder FS resize fehlt
        
    # 5. Dateisystem vergrößern
    console.print(f"[blue]Passe Dateisystem ({fstype}) an...[/blue]")
    if fstype in ['ext2', 'ext3', 'ext4']:
        cmd = f"sudo resize2fs {dev}"
    elif fstype == 'xfs':
        cmd = f"sudo xfs_growfs {mountpoint}"
    elif fstype == 'btrfs':
        cmd = f"sudo btrfs filesystem resize max {mountpoint}"
    else:
        console.print(f"[bold red]Dateisystem '{fstype}' wird für automatische Vergrößerung nicht unterstützt.[/bold red]")
        console.print("Bitte vergrößere das Dateisystem manuell.")
        raise typer.Exit(code=1)
        
    if run_command(cmd, desc=f"Vergrößere {fstype} Dateisystem"):
        console.print(f"\n[bold green]Erfolgreich! Das Netzwerk-Dateisystem wurde erweitert.[/bold green]")
        # Zeige den neuen Speicherstand an
        run_command(f"df -h {mountpoint}", desc="Neuer Speicherplatz", check=False)
    else:
        console.print("[bold red]Fehler bei der Erweiterung des Dateisystems.[/bold red]")
        raise typer.Exit(code=1)

@app.command("usage")
def cmd_usage():
    """
    Speicherplatz analysieren (gdu)
    """
    console.print("[bold blue]Laufwerk Speicherplatz analysieren[/bold blue]")
    
    # 1. Speicherplatz auslesen
    console.print("[blue]Lese Mountpoints...[/blue]")
    result = subprocess.run(
        ["df", "-h", "-x", "tmpfs", "-x", "devtmpfs", "-x", "overlay", "-x", "squashfs", "-x", "efivarfs"], 
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        console.print(f"[bold red]Fehler beim Auslesen der Festplatten: {result.stderr}[/bold red]")
        raise typer.Exit(code=1)
        
    lines = result.stdout.strip().split("\n")
    if len(lines) < 2:
        console.print("[yellow]Keine passenden Laufwerke gefunden.[/yellow]")
        raise typer.Exit()
        
    # Header überspringen und Spalten ausrichten
    choices = []
    parsed_lines = []
    
    max_mount_len = 0
    max_size_len = 0
    max_used_len = 0
    max_pcent_len = 0
    
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            size = parts[1]
            used = parts[2]
            use_percent = parts[4]
            mountpoint = " ".join(parts[5:])
            
            parsed_lines.append({
                "mountpoint": mountpoint,
                "size": size,
                "used": used,
                "use_percent": use_percent
            })
            
            max_mount_len = max(max_mount_len, len(mountpoint))
            max_size_len = max(max_size_len, len(size))
            max_used_len = max(max_used_len, len(used))
            max_pcent_len = max(max_pcent_len, len(use_percent))
            
    for item in parsed_lines:
        mnt_padded = item["mountpoint"].ljust(max_mount_len + 2)
        size_padded = item["size"].rjust(max_size_len)
        used_padded = item["used"].rjust(max_used_len)
        pcent_padded = item["use_percent"].rjust(max_pcent_len)
        
        display_str = f"{mnt_padded} [Größe: {size_padded} | Belegt: {pcent_padded} ({used_padded})]"
        choices.append({"name": display_str, "value": item["mountpoint"]})
            
    choices.append({"name": "Eigener Pfad... (Manuelle Eingabe)", "value": "custom"})
    
    # 2. Frage ob gdu gestartet werden soll / Mountpoint Auswahl
    console.print("")
    selected_path = questionary.select(
        "Wähle den Pfad, den du mit gdu analysieren möchtest:",
        choices=choices
    ).ask()
    
    if not selected_path:
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    if selected_path == "custom":
        selected_path = questionary.text(
            "Gib den absoluten Pfad ein (z.B. /var/log):",
            default="/"
        ).ask()
        if not selected_path:
            raise typer.Exit()
    
    # Check if gdu is installed
    check_gdu = subprocess.run(["dpkg", "-s", "gdu"], capture_output=True, text=True)
    if check_gdu.returncode != 0:
        console.print("[yellow]gdu ist nicht installiert. Installiere...[/yellow]")
        success = run_command("sudo apt-get update && sudo apt-get install -y gdu", desc="Installiere gdu")
        if not success:
            console.print("[bold red]Fehler bei der Installation von gdu.[/bold red]")
            raise typer.Exit(code=1)
    
    console.print(f"[green]Starte gdu für {selected_path}... (Bitte warten)[/green]")
    try:
        subprocess.run(["sudo", "gdu", selected_path])
    except Exception as e:
        console.print(f"[bold red]Fehler beim Starten von gdu: {e}[/bold red]")
        raise typer.Exit(code=1)


