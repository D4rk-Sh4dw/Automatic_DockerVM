import typer
import questionary
import subprocess
import os
import json
import re
import tempfile
import subprocess
import os
import json
from dockervm_cli.utils import run_command, console, DVM_BASE_PATH

app = typer.Typer(help="Verwaltung von Festplatten und Laufwerken (vdisks).")

def get_expandable_partitions():
    """Returns a list of mounted partitions that could potentially be expanded."""
    EXPANDABLE_FSTYPES = {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'vfat'}

    # --- Step 1: Read /proc/mounts (kernel ground truth) ---
    mounts = []
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                source, target, fstype = parts[0], parts[1], parts[2]
                if not source.startswith('/dev/'):
                    continue
                if fstype not in EXPANDABLE_FSTYPES:
                    continue
                mounts.append((source, target, fstype))
    except Exception as e:
        console.print(f"[bold red]Fehler beim Lesen von /proc/mounts: {e}[/bold red]")
        return []

    # --- Step 2: Build size/metadata lookup from lsblk ---
    import shlex
    size_map = {}
    try:
        lb_result = subprocess.run(
            ['lsblk', '-P', '-b', '-o', 'NAME,SIZE,PKNAME,PARTN,TYPE'],
            capture_output=True, text=True
        )
        for lb_line in lb_result.stdout.strip().split('\n'):
            if not lb_line:
                continue
            lb_props = {}
            for part in shlex.split(lb_line):
                if '=' in part:
                    k, v = part.split('=', 1)
                    lb_props[k] = v
            if lb_props.get('NAME'):
                size_map[lb_props['NAME']] = lb_props
    except Exception:
        pass

    def get_size_str(dev_path):
        name = os.path.basename(dev_path)
        lb = size_map.get(name, {})
        if not lb:
            try:
                real_name = os.path.basename(os.path.realpath(dev_path))
                lb = size_map.get(real_name, {})
            except Exception:
                pass
        if not lb:
            try:
                real_name = os.path.basename(os.path.realpath(dev_path))
                with open(f'/sys/class/block/{real_name}/size') as sf:
                    size_bytes = int(sf.read().strip()) * 512
                    if size_bytes > 1024**3:
                        return f"{size_bytes / (1024**3):.1f} GB"
                    elif size_bytes > 1024**2:
                        return f"{size_bytes / (1024**2):.1f} MB"
                    return f"{size_bytes} B"
            except Exception:
                return "? GB"
        size_bytes = int(lb.get('SIZE', 0))
        if size_bytes > 1024**3:
            return f"{size_bytes / (1024**3):.1f} GB"
        elif size_bytes > 1024**2:
            return f"{size_bytes / (1024**2):.1f} MB"
        return f"{size_bytes} B"

    # --- Step 3: Build partition list ---
    partitions = []
    seen = set()
    for source, target, fstype in mounts:
        key = f"{source}:{target}"
        if key in seen:
            continue
        seen.add(key)

        is_lvm = source.startswith('/dev/mapper/')
        is_disk = False
        pkname = ''
        partn = ''

        lb_name = os.path.basename(source)
        lb = size_map.get(lb_name, {})
        if not lb and is_lvm:
            try:
                real_name = os.path.basename(os.path.realpath(source))
                lb = size_map.get(real_name, {})
            except Exception:
                pass
        if lb:
            is_disk = lb.get('TYPE', '') == 'disk'
            pkname = lb.get('PKNAME', '')
            partn = lb.get('PARTN', '')

        size_str = get_size_str(source)
        display_str = f"{source} ({size_str}) eingebunden auf {target} [{fstype}]"
        partitions.append({
            "name": display_str,
            "value": {
                "dev": source,
                "pkname": f"/dev/{pkname}" if pkname else "",
                "partn": partn,
                "mountpoint": target,
                "fstype": fstype,
                "is_disk": is_disk,
                "is_lvm": is_lvm
            }
        })

    return partitions


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
    is_lvm = part_info.get("is_lvm", False)
    
    console.print(f"\nDu hast [cyan]{dev}[/cyan] ausgewählt ({mountpoint}, [yellow]{fstype}[/yellow]).")
    if is_lvm:
        console.print("Es handelt sich um ein LVM Logical Volume. pvresize + lvextend werden ausgeführt, anschließend wird das Dateisystem angepasst.")
    elif is_disk:
        console.print("Es handelt sich um ein vollständiges Laufwerk (keine Partitionen).")
    else:
        console.print(f"Diese Partition liegt auf [cyan]{pkname}[/cyan] (Partition {partn}).")
        
    console.print(f"\n[bold yellow]HINWEIS:[/bold yellow] Diese Aktion vergrößert den Speicherplatz auf den maximal verfügbaren Bereich.")
    if not questionary.confirm("Möchtest du fortfahren?", default=False).ask():
        console.print("[yellow]Vorgang abgebrochen.[/yellow]")
        raise typer.Exit()
        
    if is_lvm:
        # 3a. LVM: growpart auf PV-Partition → pvresize → lvextend
        console.print("[blue]Installiere Abhängigkeiten (cloud-guest-utils für growpart)...[/blue]")
        subprocess.run(["sudo", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_command("sudo apt-get install -y cloud-guest-utils", desc="Installiere cloud-guest-utils", check=False)

        # VG des LV ermitteln
        vg_name = ''
        try:
            lvs_result = subprocess.run(
                ['sudo', 'lvs', '--noheadings', '-o', 'vg_name,lv_name', dev],
                capture_output=True, text=True
            )
            console.print(f"[dim]lvs stdout: {lvs_result.stdout.strip()!r}  stderr: {lvs_result.stderr.strip()!r}[/dim]")
            if lvs_result.returncode == 0 and lvs_result.stdout.strip():
                parts_lv = lvs_result.stdout.strip().split()
                if len(parts_lv) >= 2:
                    vg_name = parts_lv[0]
            console.print(f"[dim]VG ermittelt: {vg_name!r}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warnung: LV-Info konnte nicht gelesen werden: {e}[/yellow]")

        if vg_name:
            # PVs der VG ermitteln (--select ist zuverlässiger als Positionsarg)
            pv_list = []
            try:
                pvs_result = subprocess.run(
                    ['sudo', 'pvs', '--noheadings', '-o', 'pv_name', '--select', f'vg_name={vg_name}'],
                    capture_output=True, text=True
                )
                console.print(f"[dim]pvs stdout: {pvs_result.stdout.strip()!r}  stderr: {pvs_result.stderr.strip()!r}[/dim]")
                pv_list = [l.strip() for l in pvs_result.stdout.strip().splitlines() if l.strip()]
                console.print(f"[dim]PVs gefunden: {pv_list}[/dim]")
            except Exception as e:
                console.print(f"[yellow]pvs Fehler: {e}[/yellow]")

            for pv in pv_list:
                # Schritt 1: Parent-Disk + Partitionsnummer via lsblk (funktioniert für sda3 UND nvme0n1p3)
                parent_disk = ''
                part_num = ''
                try:
                    lb = subprocess.run(
                        ['lsblk', '-no', 'PKNAME,PARTN', pv],
                        capture_output=True, text=True
                    )
                    console.print(f"[dim]lsblk für {pv}: {lb.stdout.strip()!r}[/dim]")
                    if lb.returncode == 0 and lb.stdout.strip():
                        cols = lb.stdout.strip().split()
                        if len(cols) >= 2:
                            parent_disk = f"/dev/{cols[0]}"
                            part_num = cols[1]
                except Exception as e:
                    console.print(f"[yellow]lsblk Fehler: {e}[/yellow]")

                if parent_disk and part_num:
                    console.print(f"[blue]Erweitere Partition {part_num} auf {parent_disk} (growpart)...[/blue]")
                    gp_result = subprocess.run(
                        ['sudo', 'growpart', parent_disk, part_num],
                        capture_output=True, text=True
                    )
                    console.print(f"[dim]growpart rc={gp_result.returncode} out={gp_result.stdout.strip()!r} err={gp_result.stderr.strip()!r}[/dim]")
                    if gp_result.returncode == 0:
                        console.print("[green]growpart: Partition erfolgreich erweitert.[/green]")
                    elif "NOCHANGE" in (gp_result.stdout + gp_result.stderr):
                        console.print("[yellow]growpart: Partition bereits auf Maximum. Weiter mit pvresize...[/yellow]")
                    else:
                        console.print(f"[yellow]growpart Fehler – Weiter trotzdem: {gp_result.stderr.strip() or gp_result.stdout.strip()}[/yellow]")
                else:
                    console.print(f"[dim]PV {pv} – kein Partitions-Parent erkannt (ganze Disk?), growpart übersprungen.[/dim]")

                # Schritt 2: pvresize
                console.print(f"[blue]Passe Physical Volume {pv} an neue Größe an (pvresize)...[/blue]")
                pv_result = subprocess.run(['sudo', 'pvresize', pv], capture_output=True, text=True)
                console.print(f"[dim]pvresize rc={pv_result.returncode} out={pv_result.stdout.strip()!r} err={pv_result.stderr.strip()!r}[/dim]")
                if pv_result.returncode == 0:
                    console.print(f"[green]pvresize {pv} erfolgreich.[/green]")
                else:
                    console.print(f"[yellow]pvresize {pv}: {pv_result.stderr.strip() or pv_result.stdout.strip()}[/yellow]")

            # Schritt 3: lvextend
            console.print(f"[blue]Erweitere Logical Volume {dev} (lvextend -l +100%FREE)...[/blue]")
            lv_result = subprocess.run(
                ['sudo', 'lvextend', '-l', '+100%FREE', dev],
                capture_output=True, text=True
            )
            console.print(f"[dim]lvextend rc={lv_result.returncode} out={lv_result.stdout.strip()!r} err={lv_result.stderr.strip()!r}[/dim]")
            if lv_result.returncode == 0:
                console.print("[green]Logical Volume erfolgreich erweitert![/green]")
            elif 'matches existing' in (lv_result.stdout + lv_result.stderr).lower() or \
                 'already' in (lv_result.stdout + lv_result.stderr).lower() or \
                 'no free' in (lv_result.stdout + lv_result.stderr).lower():
                console.print("[yellow]LV bereits auf maximalem freien Speicher. Dateisystem wird trotzdem angepasst...[/yellow]")
            else:
                console.print(f"[bold red]Fehler bei lvextend:[/bold red] {lv_result.stderr.strip() or lv_result.stdout.strip()}")
        else:
            console.print("[yellow]VG konnte nicht ermittelt werden. LVM-Schritte werden übersprungen.[/yellow]")

    elif not is_disk and pkname and partn:
        # 3b. Normales Partition-Layout: growpart
        console.print("[blue]Prüfe Abhängigkeiten (cloud-guest-utils für growpart)...[/blue]")
        subprocess.run(["sudo", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_command("sudo apt-get install -y cloud-guest-utils", desc="Installiere cloud-guest-utils", check=False)

        console.print(f"[blue]Erweitere Partition {partn} auf {pkname}...[/blue]")
        growpart_result = subprocess.run(['sudo', 'growpart', pkname, partn], capture_output=True, text=True)
        if growpart_result.returncode == 0:
            console.print("[green]Partition erfolgreich vergrößert![/green]")
        elif "NOCHANGE" in growpart_result.stdout or "NOCHANGE" in growpart_result.stderr:
            console.print("[yellow]Die Partition belegt bereits den maximal verfügbaren Platz. Dateisystem wird trotzdem überprüft...[/yellow]")
        else:
            console.print(f"[bold red]Fehler bei growpart:[/bold red]\n{growpart_result.stderr or growpart_result.stdout}")
            # Wir machen trotzdem weiter
        
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

@app.command("docker-prune-cron")
def docker_prune_cron():
    """
    Konfiguriert einen automatischen Cronjob zur regelmäßigen Bereinigung von Docker (image prune).
    """
    import questionary
    import getpass
    import shutil
    
    console.print("[bold blue]Konfiguration Automatische Docker Bereinigung (Cron)[/bold blue]")
    
    # Check for docker command
    if not shutil.which("docker"):
        console.print("[bold red]Docker nicht gefunden. Bitte sicherstellen, dass Docker installiert ist.[/bold red]")
        raise typer.Exit(code=1)
        
    user = getpass.getuser()
    log_file = f"/home/{user}/dvm_docker_prune.log" if user != "root" else "/var/log/dvm_docker_prune.log"
    
    # 1. Frequency
    frequency = questionary.select(
        "Wie oft soll die Docker Bereinigung (image prune -a -f) durchgeführt werden?",
        choices=[
            "Täglich (um 03:00 Uhr)",
            "Wöchentlich (Sonntags um 03:00 Uhr)",
            "Deaktivieren (Cron entfernen)"
        ]
    ).ask()
    
    if not frequency:
        raise typer.Exit()
        
    cron_cmd = f"docker image prune -a -f >> {log_file} 2>&1"
    
    # 2. Manage Crontab
    try:
        # Get current crontab
        result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
        current_crontab = result.stdout.strip().splitlines()
        
        # Filter out existing docker prune jobs
        new_crontab = [line for line in current_crontab if "docker image prune" not in line and "dvm_docker_prune.log" not in line]
        
        if frequency == "Deaktivieren (Cron entfernen)":
            if len(new_crontab) < len(current_crontab):
                console.print("[yellow]Bestehender Cron-Job entfernt.[/yellow]")
            else:
                console.print("[dim]Kein bestehender Cron-Job gefunden.[/dim]")
        else:
            # Add new job
            if frequency == "Täglich (um 03:00 Uhr)":
                schedule = "0 3 * * *"
            else: # Weekly
                schedule = "0 3 * * 0"
                
            job = f"{schedule} {cron_cmd}"
            new_crontab.append(job)
            new_crontab.append("") # Ensure newline at end
            
            console.print(f"[green]Füge Cron-Job hinzu:[/green] {job}")
            console.print(f"[dim]Log-Datei: {log_file}[/dim]")
            
        # Write back
        new_crontab_str = "\n".join(new_crontab) + "\n"
        
        run_result = subprocess.run(
            "crontab -", 
            input=new_crontab_str, 
            shell=True, 
            text=True, 
            capture_output=True
        )
        
        if run_result.returncode == 0:
            console.print("[bold green]Crontab erfolgreich aktualisiert![/bold green]")
        else:
            console.print(f"[bold red]Fehler beim Schreiben der Crontab: {run_result.stderr}[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]Fehler bei der Cron-Konfiguration: {e}[/bold red]")

@app.command("remount")
def remount_disk():
    """
    Repariert defekte Mounts (z.B. nach Änderung der vdisk UUID) und bindet sie neu ein.
    """
    console.print("[bold blue]Defekte Mounts reparieren (UUIDs anpassen)[/bold blue]")
    
    # 1. Read current fstab
    try:
        with open('/etc/fstab', 'r') as f:
            fstab_lines = f.readlines()
    except Exception as e:
        console.print(f"[bold red]Fehler beim Lesen der /etc/fstab: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    # 2. Get all existing UUIDs using blkid
    try:
        result = subprocess.run(['sudo', 'blkid', '-s', 'UUID', '-o', 'export'], capture_output=True, text=True)
        
        existing_uuids = set()
        current_dev = None
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('DEVNAME='):
                current_dev = line.split('=', 1)[1]
            elif line.startswith('UUID=') and current_dev:
                uid = line.split('=', 1)[1]
                existing_uuids.add(uid)
    except Exception as e:
        console.print(f"[bold red]Fehler beim Auslesen der UUIDs: {e}[/bold red]")
        raise typer.Exit(code=1)

    broken_entries = []
    fstab_uuids = []
    
    for i, line in enumerate(fstab_lines):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('#'):
            continue
            
        if line_stripped.startswith('UUID='):
            parts = line_stripped.split()
            if len(parts) >= 2:
                uuid = parts[0].split('=', 1)[1]
                mountpoint = parts[1]
                fstab_uuids.append(uuid)
                
                if uuid not in existing_uuids:
                    broken_entries.append({
                        "line_index": i,
                        "uuid": uuid,
                        "mountpoint": mountpoint,
                        "line": line
                    })

    if not broken_entries:
        console.print("[green]Alle Laufwerke in /etc/fstab haben momentan gültige UUIDs.[/green]")
        run_command("sudo mount -a", desc="Versuche alle in der /etc/fstab konfigurierten Laufwerke neu einzubinden", check=False)
        raise typer.Exit()
        
    # Find unassigned devices (have a UUID, but not in fstab)
    unassigned_devices = []
    try:
        lsblk_res = subprocess.run(['lsblk', '-P', '-b', '-o', 'NAME,UUID,FSTYPE,SIZE,MOUNTPOINT'], capture_output=True, text=True)
        import shlex
        for line in lsblk_res.stdout.strip().split('\n'):
            if not line: continue
            props = {}
            for part in shlex.split(line):
                if "=" in part:
                    k, v = part.split("=", 1)
                    props[k] = v
                    
            if props.get('UUID') and props.get('FSTYPE') and props.get('FSTYPE') != 'swap':
                uid = props['UUID']
                # Is it unused in fstab?
                if uid not in fstab_uuids:
                    size_bytes = int(props.get('SIZE', 0))
                    if size_bytes > 1024**3:
                        size_str = f"{size_bytes / (1024**3):.1f} GB"
                    else:
                        size_str = f"{size_bytes / (1024**2):.1f} MB"
                        
                    dev_path = f"/dev/{props['NAME']}"
                    unassigned_devices.append({
                        "dev": dev_path,
                        "uuid": uid,
                        "fstype": props['FSTYPE'],
                        "size": size_str
                    })
    except Exception as e:
        console.print(f"[yellow]Warnung: Konnte Details der freien Laufwerke nicht abrufen: {e}[/yellow]")
    
    modifications = False
    
    for b in broken_entries:
        console.print(f"\n[bold red]FEHLER:[/bold red] Altes Laufwerk (UUID [cyan]{b['uuid']}[/cyan]) für Mountpoint [yellow]{b['mountpoint']}[/yellow] nicht gefunden!")
        
        choices = [
            {"name": "Eintrag in /etc/fstab ignorieren (nichts tun)", "value": "ignore"},
            {"name": "Eintrag aus /etc/fstab LÖSCHEN", "value": "delete"}
        ]
        
        for d in unassigned_devices:
            desc = f"Ersetzen durch {d['dev']} (UUID: {d['uuid']}, FS: {d['fstype']}, Größe: {d['size']})"
            choices.append({"name": desc, "value": d})
            
        choice = questionary.select(
            f"Was möchtest du mit dem defekten Mountpoint {b['mountpoint']} tun?",
            choices=choices
        ).ask()
        
        if not choice:
            console.print("[yellow]Abbruch.[/yellow]")
            raise typer.Exit()
            
        if choice == "ignore":
            continue
        elif choice == "delete":
            fstab_lines[b["line_index"]] = f"# GELÖSCHT DURCH DVM REMOUNT: {fstab_lines[b['line_index']]}"
            modifications = True
        else:
            new_uuid = choice['uuid']
            old_line = fstab_lines[b["line_index"]]
            new_line = old_line.replace(f"UUID={b['uuid']}", f"UUID={new_uuid}")
            fstab_lines[b["line_index"]] = f"# ERSETZT DURCH DVM REMOUNT (Alte UUID: {b['uuid']})\n{new_line}"
            
            # remove from unassigned to avoid claiming the same disk twice
            unassigned_devices = [d for d in unassigned_devices if d['uuid'] != new_uuid]
            modifications = True

    if modifications:
        if questionary.confirm("\nÄnderungen an der /etc/fstab speichern und anwenden?", default=True).ask():
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".fstab", delete=False) as tf:
                tf.writelines(fstab_lines)
                tmp_fstab = tf.name
                
            run_command("sudo cp /etc/fstab /etc/fstab.backup", desc="Erstelle Backup von /etc/fstab")
            run_command(f"sudo mv {tmp_fstab} /etc/fstab", desc="Aktualisiere /etc/fstab")
            run_command("sudo chown root:root /etc/fstab && sudo chmod 644 /etc/fstab", desc="Setze Berechtigungen für /etc/fstab")
            
            run_command("sudo systemctl daemon-reload", desc="Lade systemd daemon neu", check=False)
            if run_command("sudo mount -a", desc="Lade fstab neu und mounte"):
                console.print("[bold green]Laufwerke erfolgreich aktualisiert und eingebunden![/bold green]")
            else:
                console.print("[bold red]Fehler beim Einbinden der Laufwerke (mount -a). Bitte Konfiguration prüfen![/bold red]")


@app.command("mount-cifs")
def mount_cifs():
    """
    Bindet ein CIFS/SMB Netzlaufwerk ein.
    """
    console.print("[bold blue]CIFS/SMB Laufwerk einbinden[/bold blue]")
    
    server_path = questionary.text(
        "Netzwerkpfad (z.B. //192.168.1.100/share):"
    ).ask()
    if not server_path:
        raise typer.Exit()
        
    mount_point = questionary.text(
        "Lokaler Mountpoint (z.B. /mnt/cifs):",
        default="/mnt/cifs"
    ).ask()
    if not mount_point:
        raise typer.Exit()
        
    username = questionary.text("Benutzername:").ask()
    if not username:
        raise typer.Exit()
        
    password = questionary.password("Passwort:").ask()
    if password is None:
        raise typer.Exit()
        
    # Install cifs-utils
    run_command("sudo apt-get update && sudo apt-get install -y cifs-utils", desc="Installiere cifs-utils", check=False)
    
    # Store credentials in a secure file
    creds_dir = "/etc/dvm-credentials"
    run_command(f"sudo mkdir -p {creds_dir}", desc="Erstelle Verzeichnis für Anmeldedaten")
    run_command(f"sudo chmod 700 {creds_dir}", desc="Sichere Verzeichnis")
    
    # Generate a name for the credentials file
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', server_path)
    creds_file = f"{creds_dir}/.smb_{safe_name}"
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
        tf.write(f"username={username}\npassword={password}\n")
        tmp_creds = tf.name
        
    run_command(f"sudo mv {tmp_creds} {creds_file}", desc="Speichere Anmeldedaten")
    run_command(f"sudo chown root:root {creds_file} && sudo chmod 600 {creds_file}", desc="Sichere Anmeldedaten-Datei")
    
    run_command(f"sudo mkdir -p {mount_point}", desc=f"Erstelle Mountpoint {mount_point}")
    
    # fstab entry
    fstab_entry = f"{server_path} {mount_point} cifs credentials={creds_file},uid=1000,gid=1000,x-systemd.automount,_netdev,nofail 0 0\n"
    
    with open('/etc/fstab', 'r') as f:
        fstab_content = f.read()
        
    if server_path not in fstab_content and mount_point not in fstab_content:
        console.print("[blue]Füge Eintrag zur /etc/fstab hinzu...[/blue]")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fstab", delete=False) as tf:
            tf.write(fstab_content + fstab_entry)
            tmp_fstab = tf.name
            
        run_command(f"sudo cp /etc/fstab /etc/fstab.backup", desc="Erstelle Backup von /etc/fstab")
        run_command(f"sudo mv {tmp_fstab} /etc/fstab", desc="Aktualisiere /etc/fstab")
        run_command("sudo chown root:root /etc/fstab && sudo chmod 644 /etc/fstab", desc="Setze Berechtigungen für /etc/fstab")
    else:
        console.print("[yellow]Netzwerkpfad oder Mountpoint bereits in /etc/fstab vorhanden.[/yellow]")
        
    console.print(f"[blue]Binde {server_path} unter {mount_point} ein...[/blue]")
    run_command("sudo systemctl daemon-reload", desc="Lade systemd daemon neu", check=False)
    if run_command("sudo mount -a", desc="Lade fstab neu und mounte"):
        console.print(f"\n[bold green]CIFS Laufwerk erfolgreich unter {mount_point} eingebunden![/bold green]")
    else:
        console.print("[bold red]Fehler beim Einbinden des Laufwerks.[/bold red]")
        raise typer.Exit(code=1)


@app.command("mount-nfs")
def mount_nfs():
    """
    Bindet ein NFS Netzlaufwerk ein.
    """
    console.print("[bold blue]NFS Laufwerk einbinden[/bold blue]")
    
    server_path = questionary.text(
        "Netzwerkpfad (z.B. 192.168.1.100:/volume1/share):"
    ).ask()
    if not server_path:
        raise typer.Exit()
        
    mount_point = questionary.text(
        "Lokaler Mountpoint (z.B. /mnt/nfs):",
        default="/mnt/nfs"
    ).ask()
    if not mount_point:
        raise typer.Exit()
        
    # Install nfs-common
    run_command("sudo apt-get update && sudo apt-get install -y nfs-common", desc="Installiere nfs-common", check=False)
    
    run_command(f"sudo mkdir -p {mount_point}", desc=f"Erstelle Mountpoint {mount_point}")
    
    # fstab entry
    fstab_entry = f"{server_path} {mount_point} nfs x-systemd.automount,_netdev,nofail 0 0\n"
    
    with open('/etc/fstab', 'r') as f:
        fstab_content = f.read()
        
    if server_path not in fstab_content and mount_point not in fstab_content:
        console.print("[blue]Füge Eintrag zur /etc/fstab hinzu...[/blue]")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fstab", delete=False) as tf:
            tf.write(fstab_content + fstab_entry)
            tmp_fstab = tf.name
            
        run_command(f"sudo cp /etc/fstab /etc/fstab.backup", desc="Erstelle Backup von /etc/fstab")
        run_command(f"sudo mv {tmp_fstab} /etc/fstab", desc="Aktualisiere /etc/fstab")
        run_command("sudo chown root:root /etc/fstab && sudo chmod 644 /etc/fstab", desc="Setze Berechtigungen für /etc/fstab")
    else:
        console.print("[yellow]Netzwerkpfad oder Mountpoint bereits in /etc/fstab vorhanden.[/yellow]")
        
    console.print(f"[blue]Binde {server_path} unter {mount_point} ein...[/blue]")
    run_command("sudo systemctl daemon-reload", desc="Lade systemd daemon neu", check=False)
    if run_command("sudo mount -a", desc="Lade fstab neu und mounte"):
        console.print(f"\n[bold green]NFS Laufwerk erfolgreich unter {mount_point} eingebunden![/bold green]")
    else:
        console.print("[bold red]Fehler beim Einbinden des Laufwerks.[/bold red]")
        raise typer.Exit(code=1)

