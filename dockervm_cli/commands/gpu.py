import typer
import subprocess
import os
import sys
import questionary
from typing import Optional
from dockervm_cli.utils import print_status, print_error, print_success, run_command

app = typer.Typer(help="Verwaltung der NVIDIA GPU Einstellungen.")

@app.command("check")
def check():
    """Prüft, ob die VM die NVIDIA GPU sieht."""
    print_status("Prüfe auf NVIDIA GPU...", nl=False)
    try:
        # lspci | grep -i nvidia
        result = subprocess.run("lspci | grep -i nvidia", shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print_success(" NVIDIA GPU erkannt!")
            print(result.stdout)
        else:
            print_error(" Keine NVIDIA GPU erkannt.")
            print("Bitte Proxmox VM Konfiguration prüfen.")
            raise typer.Exit(code=1)
    except Exception as e:
        print_error(f" Fehler beim Prüfen der GPU: {e}")
        raise typer.Exit(code=1)

@app.command("install-driver")
def install_driver(url: Optional[str] = typer.Option(None, help="Benutzerdefinierte URL für den Treiber-Download")):
    """Installiert NVIDIA Treiber und Abhängigkeiten."""
    
    default_url = "https://uk.download.nvidia.com/XFree86/Linux-x86_64/580.119.02/NVIDIA-Linux-x86_64-580.119.02.run"

    if url is None:
        # Interaktive Abfrage mit Default-Wert
        url = questionary.text(
            "Bitte NVIDIA Treiber Download-Link eingeben:",
            default=default_url
        ).ask()
        
    if not url:
        print_error("Keine URL angegeben.")
        raise typer.Exit(code=1)

    print_status("Installiere Abhängigkeiten...")
    if not run_command("apt install -y make gcc build-essential dkms"):
         print_error("Fehler beim Installieren der Abhängigkeiten.")
         raise typer.Exit(code=1)
    
    filename = url.split("/")[-1]
    if not filename:
        filename = "nvidia-driver.run"

    print_status(f"Lade NVIDIA Treiber herunter ({filename})...")
    if not run_command(f"wget -O {filename} {url}"):
        print_error("Fehler beim Herunterladen des Treibers.")
        raise typer.Exit(code=1)
    
    run_command(f"chmod +x {filename}")

    print_status("Installiere NVIDIA Treiber (dies kann eine Weile dauern)...")
    try:
        # --dkms sorgt für automatische Updates bei Kernel-Updates
        subprocess.run([f"./{filename}", "--dkms"], check=True)
    except subprocess.CalledProcessError:
        print_error("Treiber-Installation fehlgeschlagen.")
        raise typer.Exit(code=1)

    print_status("Installiere nvtop...")
    run_command("apt install -y nvtop")
    
    print_success("Treiber-Installation abgeschlossen!")
    print("")
    print_error("WICHTIG: Ein Systemneustart ist ZWINGEND erforderlich, bevor die GPU genutzt werden kann.")
    
    if questionary.confirm("Möchtest du das System jetzt neu starten?", default=False).ask():
        print_status("System wird neu gestartet...")
        run_command("reboot")
    else:
        print_status("Bitte starte das System manuell neu (Befehl: reboot), bevor du 'dvm gpu setup-docker' ausführst.")
@app.command("setup-docker")
def setup_docker():
    """Konfiguriert Docker für die Nutzung der NVIDIA GPU."""
    print_status("Richte NVIDIA Container Toolkit ein...")

    # Repository hinzufügen
    print_status("Füge NVIDIA Container Toolkit Repository hinzu...")
    cmd1 = "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg"
    cmd2 = "curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list"
    
    try:
        subprocess.run(cmd1, shell=True, check=True)
        subprocess.run(cmd2, shell=True, check=True)
    except subprocess.CalledProcessError:
        print_error("Fehler beim Hinzufügen des NVIDIA Repositories.")
        raise typer.Exit(code=1)

    print_status("Aktualisiere apt und installiere nvidia-container-toolkit...")
    run_command("apt update")
    if not run_command("apt install -y nvidia-container-toolkit"):
        print_error("Fehler beim Installieren von nvidia-container-toolkit.")
        raise typer.Exit(code=1)

    print_status("Konfiguriere Docker Runtime...")
    if not run_command("nvidia-ctk runtime configure --runtime=docker"):
        print_error("Fehler beim Konfigurieren der Docker Runtime.")
        raise typer.Exit(code=1)
    
    print_status("Starte Docker neu...")
    run_command("systemctl restart docker")

    print_status("Teste GPU Durchreichung mit Docker Container...")
    try:
        subprocess.run(["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:12.3.0-base-ubuntu22.04", "nvidia-smi"], check=True)
        print_success("Docker GPU Durchreichung funktioniert!")
    except subprocess.CalledProcessError:
        print_error("Docker GPU Test fehlgeschlagen.")

@app.command("setup-persistence")
def setup_persistence():
    """Aktiviert den NVIDIA Persistence Modus via Cron."""
    print_status("Richte Persistence Modus Cronjob ein...")
    
    cron_cmd = "@reboot sleep 30 && /usr/bin/nvidia-smi -pm 1 >> /var/log/nvidia-persistence.log 2>&1"
    
    # Prüfen ob bereits vorhanden
    try:
        current_crontab = subprocess.check_output("crontab -l", shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        current_crontab = ""
    
    if cron_cmd in current_crontab:
        print_status("Persistence Cronjob existiert bereits.")
    else:
        new_crontab = f"{current_crontab}\n{cron_cmd}\n"
        try:
            process = subprocess.Popen("crontab -", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=new_crontab)
            if process.returncode == 0:
                print_success("Persistence Cronjob hinzugefügt.")
            else:
                print_error(f"Fehler beim Hinzufügen des Cronjobs: {stderr}")
                raise typer.Exit(code=1)
        except Exception as e:
            print_error(f"Fehler beim Aktualisieren der Crontab: {e}")
            raise typer.Exit(code=1)

@app.command("toggle-hold")
def toggle_update_hold():
    """Sperrt oder entsperrt NVIDIA Treiber für alle APT Updates (apt-mark hold/unhold)."""
    print_status("Prüfe aktuellen Hold-Status der NVIDIA Pakete...")
    
    try:
        # dpkg-query to find all installed nvidia/cuda packages
        result = subprocess.run("dpkg-query -f '${Package}\\n' -W", shell=True, capture_output=True, text=True)
        installed_packages = result.stdout.strip().splitlines()
        
        import re
        regexes = [re.compile(r'^nvidia-driver.*'), re.compile(r'^libnvidia-.*'), re.compile(r'^cuda.*'), re.compile(r'^libcuda.*')]
        
        nvidia_packages = []
        for pkg in installed_packages:
            if any(r.match(pkg) for r in regexes):
                nvidia_packages.append(pkg)
                
    except Exception as e:
        print_error(f"Fehler beim Suchen der NVIDIA Pakete: {e}")
        raise typer.Exit(code=1)
        
    if not nvidia_packages:
        print_error("Keine installierten NVIDIA bzw. CUDA Pakete gefunden.")
        raise typer.Exit(code=1)
        
    # Check if they are held
    held_result = subprocess.run("apt-mark showhold", shell=True, capture_output=True, text=True)
    held_packages = held_result.stdout.strip().splitlines()
    
    # Are any of our nvidia packages held?
    currently_held = [pkg for pkg in nvidia_packages if pkg in held_packages]
    
    if currently_held:
        print_status(f"Es sind aktuell [yellow]{len(currently_held)}[/yellow] NVIDIA Pakete gesperrt (Hold).")
        action = questionary.select(
            "Was möchtest du tun?",
            choices=["Nichts ändern", "Sperre aufheben (Bereit für Updates)"]
        ).ask()
        
        if action == "Sperre aufheben (Bereit für Updates)":
            cmd = f"apt-mark unhold {' '.join(currently_held)}"
            if run_command(cmd, desc="Hebe Hold-Status auf"):
                print_success("Sperre erfolgreich aufgehoben. Die Treiber werden beim nächsten 'apt upgrade' aktualisiert.")
            else:
                print_error("Fehler beim Aufheben der Sperre.")
    else:
        print_status(f"Es wurden [blue]{len(nvidia_packages)}[/blue] NVIDIA Pakete gefunden. Diese sind [bold green]NICHT gesperrt[/bold green] und werden bei 'apt upgrade' aktualisiert.")
        action = questionary.select(
            "Was möchtest du tun?",
            choices=["Sperren (generell bei allen Updates ausschließen)", "Nichts ändern"]
        ).ask()
        
        if action == "Sperren (generell bei allen Updates ausschließen)":
            cmd = f"apt-mark hold {' '.join(nvidia_packages)}"
            if run_command(cmd, desc="Setze Hold-Status"):
                print_success("Die Treiber wurden erfolgreich gesperrt und werden bei zukünftigen Updates (auch manuell) ignoriert.")
            else:
                print_error("Fehler beim Setzen der Sperre.")

