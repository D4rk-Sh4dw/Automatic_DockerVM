import typer
import questionary
import subprocess
import os
from dockervm_cli.utils import run_command, console

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
