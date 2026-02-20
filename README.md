# Automatic_DockerVM / dvm CLI

Ein modernes Python-basiertes CLI-Tool zur Verwaltung Ihrer Docker-VM, das die alten Shell-Skripte ersetzt.

## Features

*   **System Updates**: Automatische (unattended-upgrades) und manuelle Updates.
*   **Container Management**: Installation und Updates für Dockhand (Portainer Alternative).
*   **Netzwerk**: Einfache Konfiguration von Statischen IPs (Netplan) und IPVLANs.
*   **Sicherheit**: Integrierte Blacklist für Updates (z.B. NVIDIA Treiber).
*   **Benachrichtigungen**: E-Mail-Alarmierung bei Fehlern.

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
