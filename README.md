# Automatic_DockerVM / dvm CLI

Ein modernes Python-basiertes CLI-Tool zur Verwaltung Ihrer Docker-VM, das die alten Shell-Skripte ersetzt.

## Features

*   **System Updates**: Automatische (unattended-upgrades) und manuelle Updates inkl. E-Mail-Benachrichtigungen.
*   **Container Management**: Installation von Dockhand, Lazydocker, Container-Templates (z.B. Unifi) und DNS-Server (AdGuard).
*   **Netzwerk**: Konfiguration von Statischen IPs (Netplan), IPVLANs und Netbird VPN Client.
*   **GPU Management**: Automatische Treiber-Installation, Docker-GPU-Setup, Persistence Mode und Update-Sperren (Hold).
*   **Laufwerke (Disk)**: Einbinden von Festplatten/Netzlaufwerken (ext4, CIFS/SMB, NFS), Speicher erweitern (growpart) und Docker-Speicherort verschieben.
*   **Sicherheit**: Integrierte Update-Blacklist zum Schutz von NVIDIA-Treibern oder eigenen Systemkomponenten.

## Installation

```bash
git clone https://github.com/D4rk-Sh4dw/Automatic_DockerVM.git
cd Automatic_DockerVM
chmod +x setup.sh
./setup.sh
```

## Nutzung

Starten Sie das interaktive Menü:

```bash
dvm
```

Oder nutzen Sie direkte Befehle:

```bash
dvm commands  # Zeigt eine Übersicht aller Befehle
```
Eine Erklärung aller Punkte findet ihr hier:
https://github.com/D4rk-Sh4dw/Automatic_DockerVM/blob/main/COMMANDS_DE.md

## Fehlerbehebung (Troubleshooting)

### Befehle fehlen (z.B. nach einem Update)
Falls nach einem `dvm update self` neue Befehle (wie z.B. `dvm disk`) immer noch fehlen sollten, liegt das in der Regel an einem Konflikt der lokalen Version mit GitHub. Dies kann durch einen manuellen Reset behoben werden.

Gehe dazu in das Verzeichnis, in das du `dvm` geklont/installiert hast (z.B. `/mnt/dvm/Automatic_DockerVM`), und führe folgendes aus:

```bash
cd /DEIN/INSTALLATIONS/PFAD
git fetch origin
git reset --hard origin/main
dvm update self
```
Dadurch wird dein lokales Repository hart auf den aktuellen Stand von GitHub gesetzt und alle Befehle sollten wieder funktionieren.

## FAQ

### Was ist der Unterschied zwischen `dvm gpu toggle-hold` und `dvm update blacklist`?

Beide Befehle können Pakete vor Updates schützen (per `apt-mark hold`), haben aber unterschiedliche Einsatzgebiete:

*   **`dvm update blacklist` (Der intelligente Schutz)**: Dies ist dein flexibles Sicherheitsnetz für System-Updates. Du definierst hier Muster (wie z.B. für Docker, NVIDIA oder eigene Dienste). Automatische Hintergrund-Updates (`unattended-upgrades`) ignorieren diese Pakete komplett. Wenn du das System manuell über `dvm update system` aktualisierst, wird die Blacklist ausgelesen und du wirst *interaktiv* gefragt, ob du den Schutz für dieses Update ausnahmsweise aufheben möchtest.
*   **`dvm gpu toggle-hold` (Die manuelle Handbremse)**: Ein direkter Ein-/Ausschalter, der *ausschließlich* für NVIDIA- und CUDA-Treiber zuständig ist. Er schreibt keine Config-Dateien, sondern setzt einfach sofort den harten Sperr-Status im direkten System. Er fragt beim Update nicht dynamisch nach. Sehr nützlich, wenn du bei Treiberarbeiten die GPU mal eben schnell manuell festsetzen oder befreien willst.
