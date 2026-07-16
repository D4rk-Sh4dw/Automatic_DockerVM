
import typer
from typing import Optional
from dockervm_cli.utils import console

from dockervm_cli.commands import update, install, network, gpu, disk

app = typer.Typer(
    name="dvm",
    help="DockerVM Management CLI - Ein modernes Tool zur Verwaltung deiner Docker VM.",
    add_completion=False,
    no_args_is_help=False,
)

app.add_typer(update.app, name="update")
app.add_typer(install.app, name="install")
app.add_typer(network.app, name="network")
app.add_typer(gpu.app, name="gpu")
app.add_typer(disk.app, name="disk")

@app.command("commands")
def list_commands():
    """
    Zeigt eine Übersicht aller verfügbaren Befehle.
    """
    from rich.table import Table
    from dockervm_cli.utils import console
    
    table = Table(title="DockerVM CLI Befehlsübersicht", show_header=True, header_style="bold magenta")
    
    table.add_column("Kategorie", style="dim", width=20)
    table.add_column("Befehl", style="cyan")
    table.add_column("Beschreibung", style="white")
    
    # System Updates
    table.add_row("System Management", "dvm update system", "Manuelles System-Update (apt update & upgrade)")
    table.add_row("", "dvm update auto", "Automatische Updates aktivieren (Unattended-Upgrades)")
    table.add_row("", "dvm update blacklist", "Gezielte Ausnahmen für System-Updates (Blacklist) konfigurieren")
    table.add_row("", "dvm update mail", "E-Mail Benachrichtigungen konfigurieren (SMTP)")
    table.add_row("", "dvm update cron", "Automatische Self-Updates konfigurieren (Cron)")
    table.add_row("", "dvm update dockhand", "Dockhand Container aktualisieren")
    table.add_row("", "dvm update compose", "Docker Compose Update Cronjob einrichten (pull + up -d + prune)")
    table.add_row("", "dvm update compose-list", "Compose Update Cronjobs anzeigen und verwalten")
    table.add_section()
    
    # Installation
    table.add_row("Installation", "dvm install dockhand", "Dockhand (Portainer Alternative) installieren")
    table.add_row("", "dvm install lazydocker", "Lazydocker (Terminal UI) installieren")
    table.add_row("", "dvm install zsh", "ZSH & Oh My Zsh installieren")
    table.add_row("", "dvm install container", "Container aus Template installieren (z.B. Unifi)")
    table.add_row("", "dvm install dns-server", "DNS Server installieren (AdGuard + Technitium)")
    table.add_row("", "dvm install netbird", "Netbird VPN Client installieren")
    table.add_section()
    
    # Network
    table.add_row("Netzwerk", "dvm network ip", "Statische IP konfigurieren (Netplan)")
    table.add_row("", "dvm network ipvlan", "IPVLAN Docker Netzwerk einrichten")
    table.add_row("", "dvm network create", "Docker Netzwerk erstellen (für external: true)")
    table.add_row("", "dvm network list", "Alle Docker Netzwerke anzeigen")
    table.add_section()

    # GPU
    table.add_row("GPU", "dvm gpu check", "NVIDIA GPU Erkennung prüfen")
    table.add_row("", "dvm gpu install-driver", "NVIDIA Treiber installieren")
    table.add_row("", "dvm gpu setup-docker", "Docker für GPU konfigurieren")
    table.add_row("", "dvm gpu setup-persistence", "GPU Persistence Mode (Autostart) aktivieren")
    table.add_row("", "dvm gpu toggle-hold", "NVIDIA Treiber Updates sperren/entsperren (Hold)")
    table.add_section()
    
    # Disk
    table.add_row("Laufwerke", "dvm disk mount", "Neue (unformatierte) Festplatte formatieren und einbinden")
    table.add_row("", "dvm disk mount-cifs", "CIFS/SMB Netzlaufwerk einbinden")
    table.add_row("", "dvm disk mount-nfs", "NFS Netzlaufwerk einbinden")
    table.add_row("", "dvm disk expand", "Bestehende Festplatte (Partition) interaktiv vergrößern")
    table.add_row("", "dvm disk remount", "Defekte Mounts reparieren (geänderte Festplatten-UUIDs anpassen)")
    table.add_row("", "dvm disk docker-storage", "Docker Speicherort (data-root) interaktiv ändern")
    table.add_row("", "dvm disk docker-clean-backup", "Altes Docker Speicherort-Backup bereinigen")
    table.add_row("", "dvm disk usage", "Speicherplatz analysieren (gdu)")
    table.add_row("", "dvm disk docker-prune-cron", "Automatisches Docker Image Prune (Cron) konfigurieren")
    table.add_section()
    
    # Misc
    table.add_row("Sonstiges", "dvm update self", "Dieses CLI-Tool aktualisieren")
    table.add_row("", "dvm commands", "Diese Liste anzeigen")
    
    console.print(table)


# --------------------------------------------------------------------------
# Interaktives Menü (kategoriebasiert, mit Beschreibungstexten)
# --------------------------------------------------------------------------

def _build_menu():
    """
    Liefert die Menüstruktur:
        {Kategorie: [(Label, Beschreibung, Callable_oder_None), ...]}

    Ein Callable == None bedeutet: Eintrag verweist auf eine interne Aktion
    (siehe unten in run_interactive_menu).
    """
    return {
        "System Management": [
            ("System Update (Manuell)",
             "Führt apt update & upgrade aus (interaktiv, mit Blacklist-Prüfung).",
             update.update_system),
            ("Automatische Updates aktivieren",
             "Konfiguriert Unattended-Upgrades für Hintergrund-Updates.",
             update.configure_unattended),
            ("Update Blacklist konfigurieren",
             "Pakete gezielt von automatischen Updates ausnehmen (Muster).",
             update.configure_blacklist),
            ("E-Mail Benachrichtigungen konfigurieren",
             "SMTP-Zugang für Benachrichtigungen zu Updates einrichten.",
             update.configure_mail),
            ("Automatische Self-Updates (Cron)",
             "Dieses CLI-Tool regelmäßig via Cron aktualisieren.",
             update.configure_self_cron),
            ("Dockhand aktualisieren",
             "Zieht das neueste Dockhand-Image und startet den Container neu.",
             update.update_dockhand),
            ("Compose Update Cronjob einrichten",
             "Cron für 'docker compose pull + up -d + prune' pro Stack anlegen.",
             update.configure_compose_cron),
            ("Compose Update Cronjobs verwalten",
             "Vorhandene Compose-Update-Cronjobs anzeigen und löschen.",
             update.manage_compose_cron),
        ],
        "Installation": [
            ("Dockhand installieren",
             "Dockhand (Portainer-Alternative) via Docker installieren.",
             install.install_dockhand),
            ("Lazydocker installieren",
             "Terminal-UI zum Verwalten von Docker-Containern.",
             install.install_lazydocker),
            ("ZSH (inkl. Oh My Zsh) installieren",
             "Bessere Shell inkl. Framework, Plugins & Themes.",
             install.install_zsh),
            ("Container aus Template installieren",
             "Vorgefertigte docker-compose Templates deployen (z.B. Unifi).",
             install.install_container),
            ("DNS Server installieren",
             "AdGuard Home + Technitium DNS Server einrichten.",
             install.install_dns_server),
            ("Netbird VPN Client installieren",
             "Netbird (WireGuard-basierter Mesh-VPN) Client installieren.",
             install.install_netbird),
        ],
        "Netzwerk": [
            ("Statische IP konfigurieren",
             "IP-Adresse, Gateway und DNS via Netplan festlegen.",
             network.configure_static_ip),
            ("IPVLAN konfigurieren",
             "IPVLAN Docker-Netzwerk (L2) einrichten für native IPs.",
             network.configure_ipvlan),
            ("Docker Netzwerk erstellen",
             "Bridge/Overlay/... Docker-Netzwerk (für 'external: true') anlegen.",
             network.create_network),
            ("Docker Netzwerke anzeigen",
             "Übersicht aller vorhandenen Docker-Netzwerke.",
             network.list_networks),
        ],
        "GPU": [
            ("GPU prüfen",
             "NVIDIA GPU Erkennung + Treiber-Status testen.",
             gpu.check),
            ("NVIDIA Treiber installieren",
             "Aktuellen NVIDIA Treiber installieren (inkl. optionaler URL).",
             gpu.install_driver),
            ("Docker GPU Setup",
             "NVIDIA Container Toolkit installieren & Docker konfigurieren.",
             gpu.setup_docker),
            ("GPU Persistence aktivieren",
             "Aktiviert den Persistence Mode als Autostart-Service.",
             gpu.setup_persistence),
            ("NVIDIA Treiber Updates sperren/entsperren (Hold)",
             "apt-mark hold für NVIDIA-/CUDA-Pakete umschalten.",
             gpu.toggle_update_hold),
        ],
        "Laufwerke": [
            ("Festplatte formatieren & einbinden",
             "Neue, unformatierte Festplatte einrichten und in fstab eintragen.",
             disk.mount_disk),
            ("CIFS/SMB Netzlaufwerk einbinden",
             "Windows-/Samba-Freigabe dauerhaft mounten.",
             disk.mount_cifs),
            ("NFS Netzlaufwerk einbinden",
             "NFS-Freigabe dauerhaft mounten.",
             disk.mount_nfs),
            ("Festplatte (Partition) vergrößern",
             "Bestehende Partition interaktiv per growpart erweitern.",
             disk.expand_disk),
            ("Defekte Mounts reparieren (geänderte UUID)",
             "fstab-Einträge bei geänderten Festplatten-UUIDs anpassen.",
             disk.remount_disk),
            ("Docker Speicherort ändern (data-root)",
             "Docker data-root interaktiv auf anderen Pfad verschieben.",
             disk.docker_storage),
            ("Altes Docker Backup löschen",
             "Backup des alten data-root Verzeichnisses entfernen.",
             disk.docker_clean_backup),
            ("Speicherplatz analysieren (gdu)",
             "Interaktive Speicherbelegung mit gdu untersuchen.",
             disk.cmd_usage),
            ("Automatische Docker Bereinigung (Cron)",
             "Regelmäßiges 'docker image prune' per Cron einrichten.",
             disk.docker_prune_cron),
        ],
        "Sonstiges": [
            ("Befehlsübersicht anzeigen",
             "Zeigt die komplette Tabelle aller verfügbaren CLI-Befehle.",
             list_commands),
            ("CLI aktualisieren",
             "dvm selbst auf die neueste Version aus dem Git-Repo bringen.",
             update.update_self),
        ],
    }


def _format_choice(label: str, description: str, width: int) -> str:
    """
    Formatiert einen Eintrag als 'Label   —  Beschreibung' mit passender
    Ausrichtung der Beschreibung.
    """
    pad = max(width - len(label), 1)
    return f"{label}{' ' * pad}—  {description}"


def run_interactive_menu():
    """
    Startet das zweistufige interaktive Menü:
      1. Kategorie auswählen
      2. Befehl aus der Kategorie mit Beschreibung auswählen
    """
    import questionary
    from questionary import Separator, Choice
    from dockervm_cli.utils import print_header

    menu = _build_menu()

    def show_header():
        console.clear()
        print_header("DockerVM Dashboard")

    show_header()

    while True:
        category_choices = [
            Choice(title=_format_choice(cat, f"{len(entries)} Befehle", 22), value=cat)
            for cat, entries in menu.items()
        ]
        category_choices.append(Separator())
        category_choices.append(Choice(title="Beenden", value="__exit__"))

        category = questionary.select(
            "Kategorie wählen:",
            choices=category_choices,
            use_shortcuts=True,
        ).ask()

        if category in (None, "__exit__"):
            console.print("[bold blue]Auf Wiedersehen![/bold blue]")
            break

        # Untermenü der Kategorie
        while True:
            entries = menu[category]
            label_width = max(len(label) for label, _, _ in entries) + 2

            entry_choices = [
                Choice(
                    title=_format_choice(label, desc, label_width),
                    value=idx,
                )
                for idx, (label, desc, _) in enumerate(entries)
            ]
            entry_choices.append(Separator())
            entry_choices.append(Choice(title="← Zurück zur Kategorieauswahl", value="__back__"))
            entry_choices.append(Choice(title="Beenden", value="__exit__"))

            selection = questionary.select(
                f"[{category}] Was möchtest du tun?",
                choices=entry_choices,
            ).ask()

            if selection is None or selection == "__back__":
                show_header()
                break

            if selection == "__exit__":
                console.print("[bold blue]Auf Wiedersehen![/bold blue]")
                return

            label, _desc, action = entries[selection]
            console.print(f"\n[bold cyan]▶ {label}[/bold cyan]\n")
            try:
                action()
            except KeyboardInterrupt:
                console.print("\n[bold yellow]⚠  Abgebrochen.[/bold yellow]")
            except Exception as exc:  # noqa: BLE001
                from dockervm_cli.utils import print_error
                print_error(f"Fehler beim Ausführen: {exc}")

            console.print("\n")
            try:
                input("Drücke Enter, um fortzufahren...")
            except (EOFError, KeyboardInterrupt):
                console.print("[bold blue]Auf Wiedersehen![/bold blue]")
                return
            show_header()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Zeige die Anwendungsversion und beende."
    )
):
    """
    Verwalte deine Docker VM ganz einfach.
    """
    if version:
        console.print("DockerVM CLI Version: [bold cyan]0.2.0[/bold cyan] (Befehl: dvm)")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        run_interactive_menu()

if __name__ == "__main__":
    app()
