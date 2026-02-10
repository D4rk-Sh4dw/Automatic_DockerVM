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
    if not run_command(["apt", "install", "-y", "make", "gcc", "build-essential"]):
         print_error("Fehler beim Installieren der Abhängigkeiten.")
         raise typer.Exit(code=1)
    
    filename = url.split("/")[-1]
    if not filename:
        filename = "nvidia-driver.run"

    print_status(f"Lade NVIDIA Treiber herunter ({filename})...")
    if not run_command(["wget", "-O", filename, url]):
        print_error("Fehler beim Herunterladen des Treibers.")
        raise typer.Exit(code=1)
    
    run_command(["chmod", "+x", filename])

    print_status("Installiere NVIDIA Treiber (dies kann eine Weile dauern)...")
    try:
        # --dkms sorgt für automatische Updates bei Kernel-Updates
        subprocess.run([f"./{filename}", "--dkms"], check=True)
    except subprocess.CalledProcessError:
        print_error("Treiber-Installation fehlgeschlagen.")
        raise typer.Exit(code=1)

    print_status("Installiere nvtop...")
    run_command(["apt", "install", "-y", "nvtop"])
    
    print_success("Treiber-Installation abgeschlossen. Bitte das System neu starten, falls erforderlich.")

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
    run_command(["apt", "update"])
    if not run_command(["apt", "install", "-y", "nvidia-container-toolkit"]):
        print_error("Fehler beim Installieren von nvidia-container-toolkit.")
        raise typer.Exit(code=1)

    print_status("Konfiguriere Docker Runtime...")
    if not run_command(["nvidia-ctk", "runtime", "configure", "--runtime=docker"]):
        print_error("Fehler beim Konfigurieren der Docker Runtime.")
        raise typer.Exit(code=1)
    
    print_status("Starte Docker neu...")
    run_command(["systemctl", "restart", "docker"])

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
