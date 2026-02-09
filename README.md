# Automatic_DockerVM / dockervm CLI

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
pip install .
```

## Nutzung

Starten Sie das interaktive Menü:

```bash
dockervm
```

Oder nutzen Sie direkte Befehle:

```bash
dockervm commands  # Zeigt eine Übersicht aller Befehle
```
