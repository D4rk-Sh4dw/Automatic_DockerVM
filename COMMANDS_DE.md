# DockerVM CLI - Befehlsreferenz

Diese Dokumentation beschreibt alle verfügbaren Befehle des `dvm` (DockerVM Management) CLI-Tools im Detail.

## 🔄 System Management (`dvm update`)

Diese Befehle dienen der Wartung und Aktualisierung des Host-Systems und der installierten Dienste.

### `dvm update system`
Führt ein manuelles System-Update durch.
- **Was passiert:**
  1. Validiert `sudo` Rechte.
  2. Prüft auf geblockte Pakete (Blacklist) aus der `unattended-upgrades` Konfiguration.
  3. Führt `apt clean` und `apt autoremove` durch, um Speicherplatz freizugeben.
  4. Führt `apt update` (Paketlisten aktualisieren) und `apt upgrade` (Pakete aktualisieren) durch.
- **Besonderheiten:** Wenn Pakete auf der Blacklist stehen (z.B. Nvidia-Treiber), werden diese vor dem Update auf "hold" gesetzt, um versehentliche Aktualisierungen zu verhindern, und danach wieder freigegeben (sofern nicht anders gewünscht).

### `dvm update auto`
Aktiviert und konfiguriert automatische Sicherheitsupdates (`unattended-upgrades`).
- **Was passiert:**
  1. Fragt ab, welche kritischen Pakete (Nvidia, CUDA, Docker) von automatischen Updates ausgeschlossen werden sollen (Blacklist).
  2. Erstellt/Aktualisiert `/etc/apt/apt.conf.d/20auto-upgrades` und `/etc/apt/apt.conf.d/51unattended-upgrades-blacklist`.
  3. Installiert und aktiviert den `unattended-upgrades` Dienst.
- **Warum:** Wichtig für die Sicherheit, ohne dabei kritische Treiber (wie GPU) automatisch zu zerschießen.

### `dvm update mail`
Konfiguriert E-Mail-Benachrichtigungen für System-Events (z.B. fehlgeschlagene Updates).
- **Was passiert:**
  1. Installiert `msmtp` (SMTP-Client) und `bsd-mailx`.
  2. Fragt interaktiv nach SMTP-Server-Daten (Host, Port, User, Passwort).
  3. Erstellt die Konfiguration unter `/etc/msmtprc` und verlinkt `sendmail` auf `msmtp`.
  4. Konfiguriert apt so, dass E-Mails bei Updates (oder nur bei Fehlern) gesendet werden.
  5. Sendet optional eine Test-E-Mail.

### `dvm update cron`
Richtet automatische Updates für das CLI-Tool selbst ein.
- **Was passiert:**
  1. Erstellt einen Cron-Job (`crontab`), der regelmäßig `dvm update self` ausführt.
  2. Intervalle: Täglich (04:00 Uhr) oder Wöchentlich (Sonntags 04:00 Uhr).
  3. Logs werden nach `~/dvm_update.log` oder `/var/log/dvm_update.log` geschrieben.

### `dvm update dockhand`
Aktualisiert den Dockhand-Container.
- **Was passiert:**
  1. Wechselt in das Dockhand-Verzeichnis.
  2. Führt `docker-compose pull` (Images aktualisieren) und `docker-compose up -d` (Neustart) aus.

### `dvm update self`
Aktualisiert das `dvm` CLI-Tool.
- **Was passiert:**
  1. Geht in das Git-Repository des Tools.
  2. Führt `git pull` aus.
  3. Installiert das Tool neu via `pip install --upgrade .`.

---

## 📥 Installation (`dvm install`)

Installiert Anwendungen, Dienste und Tools.

### `dvm install docker`
Installiert die Docker Engine.
- **Was passiert:**
  1. Fügt das offizielle Docker-Repository hinzu.
  2. Installiert `docker-ce`, `docker-ce-cli`, `containerd.io` und Plugins.
  3. Fügt den aktuellen Benutzer zur `docker` Gruppe hinzu.

### `dvm install dockhand`
Installiert Dockhand (Portainer-Alternative) mit PostgreSQL.
- **Was passiert:**
  1. Fragt Datenbank-Zugangsdaten ab.
  2. Erstellt ein Installationsverzeichnis und eine `docker-compose.yml`.
  3. Startet die Container.

### `dvm install lazydocker`
Installiert Lazydocker, ein Terminal-UI für Docker.
- **Was passiert:**
  1. Lädt das offizielle Installationsskript und führt es aus.
  2. Installiert das Binary nach `/usr/local/bin`.

### `dvm install zsh`
Richtet eine moderne Shell-Umgebung ein.
- **Was passiert:**
  1. Installiert `zsh`, `git`, `curl` und Schriften.
  2. Installiert **Oh My Zsh**.
  3. Klont Plugins (`zsh-autosuggestions`, `zsh-syntax-highlighting`) und aktiviert sie in der `.zshrc`.
  4. Ändert auf Wunsch die Standard-Shell des Benutzers.

### `dvm install container`
Installiert einen Docker-Container basierend auf einem Template.
- **Was passiert:**
  1. Listet verfügbare Templates aus dem `templates/` Ordner auf.
  2. Liest die `.env` des Templates und fragt die Werte interaktiv ab.
  3. Erstellt das Zielverzeichnis, kopiert `docker-compose.yml` und generiert die `.env`.
  4. Startet den Container.

### `dvm install dns-server`
Installiert einen DNS-Server Stack (AdGuard Home).
- **Was passiert:**
  1. Deaktiviert `systemd-resolved`, um Port 53 freizugeben (setzt stattdessen Cloudflare/Google DNS im Host).
  2. Lädt `docker-compose.yml` und Configs von GitHub.
  3. Startet den Stack.

---

## 🌐 Netzwerk (`dvm network`)

Tools zur Konfiguration von Host- und Docker-Netzwerken.

### `dvm network ip`
Konfiguriert eine statische IP-Adresse für den Host (Ubuntu/Debian via Netplan).
- **Was passiert:**
  1. Fragt IP, Gateway und DNS-Server ab.
  2. Erstellt ein Backup der aktuellen Netplan-Config in `/etc/netplan/backup/`.
  3. Schreibt eine neue Konfiguration (`01-netcfg.yaml`) und wendet sie mit `netplan apply` an.
  4. Bei Fehler wird das Backup automatisch wiederhergestellt.

### `dvm network ipvlan`
Erstellt ein Docker-Netzwerk mit dem `ipvlan` Treiber.
- **Was passiert:**
  1. Fragt Subnetz, Gateway, IP-Range und Parent-Interface ab.
  2. Führt `docker network create -d ipvlan ...` aus.

### `dvm network create`
Erstellt ein beliebiges Docker-Netzwerk.
- **Was passiert:**
  1. Erlaubt Auswahl eines vordefinierten Namens oder Eingabe eines eigenen.
  2. Wählt den Treiber (`bridge`, `overlay`, `macvlan`).
  3. Führt `docker network create` aus.

### `dvm network list`
- **Was passiert:** Zeigt alle Docker-Netzwerke tabellarisch an (`docker network ls`).

---

## 🎮 GPU (`dvm gpu`)

Verwaltung von NVIDIA Grafikkarten für Passthrough und Docker.

### `dvm gpu check`
- **Was passiert:** Prüft mittels `lspci`, ob eine NVIDIA GPU am PCI-Bus erkannt wird.

### `dvm gpu install-driver`
Installiert den NVIDIA-Treiber.
- **Was passiert:**
  1. Lädt wichtige Build-Tools (`build-essential`).
  2. Lädt den Treiber-Runfile herunter (URL kann angegeben werden, sonst Default).
  3. Führt die Installation mit DKMS-Support durch (damit Kernel-Updates den Treiber nicht brechen).
  4. Installiert `nvtop` zur Überwachung.

### `dvm gpu setup-docker`
Macht die GPU in Docker verfügbar.
- **Was passiert:**
  1. Installiert das Import `nvidia-container-toolkit`.
  2. Konfiguriert die Docker Runtime (`nvidia-ctk runtime configure`).
  3. Startet Docker neu und führt einen Test-Container (`nvidia-smi` im Container) aus.

### `dvm gpu setup-persistence`
Aktiviert den Persistence Mode (verhindert, dass der Treiber entladen wird, wenn keine Anwendung läuft).
- **Was passiert:** Erstellt einen Cron-Job (`@reboot`), der `nvidia-smi -pm 1` beim Start ausführt.

---

## ℹ️ Sonstiges

### `dvm commands`
Zeigt eine Übersicht aller Befehle direkt im Terminal an.
