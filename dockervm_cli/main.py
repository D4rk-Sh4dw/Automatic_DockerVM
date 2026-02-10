
import typer
from typing import Optional
from dockervm_cli.utils import console

from dockervm_cli.commands import update, install, network, gpu

app = typer.Typer(
    name="dvm",
    help="DockerVM Management CLI - Ein modernes Tool zur Verwaltung deiner Docker VM.",
    add_completion=False,
    no_args_is_help=True
)

app.add_typer(update.app, name="update")
app.add_typer(install.app, name="install")
app.add_typer(network.app, name="network")
app.add_typer(gpu.app, name="gpu")

@app.command("commands")
def list_commands():
    """
    Zeigt eine Übersicht aller verfügbaren Befehle.
    """
    from rich.table import Table
    from dockervm_cli.utils import console
    
    table = Table(title="DockerVM CLI Befehlsübersicht")
    
    table.add_column("Befehl", style="cyan")
    table.add_column("Beschreibung", style="white")
    
    # System Updates
    table.add_row("dvm update system", "Manuelles System-Update (apt update & upgrade)")
    table.add_row("dvm update auto", "Automatische Updates aktivieren (Unattended-Upgrades)")
    table.add_row("dvm update mail", "E-Mail Benachrichtigungen konfigurieren (SMTP)")
    table.add_row("dvm update dockhand", "Dockhand Container aktualisieren")
    
    # Installation
    table.add_row("dvm install dockhand", "Dockhand (Portainer Alternative) installieren")
    table.add_row("dvm install lazydocker", "Lazydocker (Terminal UI) installieren")
    table.add_row("dvm install zsh", "ZSH & Oh My Zsh installieren")
    table.add_row("dvm install container", "Container aus Template installieren (z.B. Unifi)")
    table.add_row("dvm install dns-server", "DNS Server installieren (AdGuard + Technitium)")
    
    # Network
    table.add_row("dvm network ip", "Statische IP konfigurieren (Netplan)")
    table.add_row("dvm network ipvlan", "IPVLAN Docker Netzwerk einrichten")
    table.add_row("dvm network create", "Docker Netzwerk erstellen (für external: true)")
    table.add_row("dvm network list", "Alle Docker Netzwerke anzeigen")
    
    # Misc
    table.add_row("dvm update self", "Dieses CLI-Tool aktualisieren")
    table.add_row("dvm commands", "Diese Liste anzeigen")
    
    console.print(table)


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
        console.print("DockerVM CLI Version: [bold cyan]0.1.0[/bold cyan] (Befehl: dvm)")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        import questionary
        from dockervm_cli.utils import print_header
        
        print_header("DockerVM Dashboard")
        

        while True:
            choice = questionary.select(
                "Was möchtest du tun?",
                choices=[
                    "Befehlsübersicht anzeigen",
                    "System Update (Manuell)",
                    "Automatische Updates aktivieren",
                    "E-Mail Benachrichtigungen konfigurieren",
                    "Dockhand aktualisieren",
                    "Dockhand installieren",
                    "Lazydocker installieren",
                    "ZSH (inkl. Oh My Zsh) installieren",
                    "Container aus Template installieren",
                    "DNS Server installieren",
                    "Netzwerk konfigurieren (Statische IP)",
                    "IPVLAN konfigurieren",
                    "Docker Netzwerk erstellen",
                    "Docker Netzwerke anzeigen",
                    "CLI aktualisieren",
                    "Beenden"
                ]
            ).ask()
            
            if choice == "Befehlsübersicht anzeigen":
                list_commands()
            elif choice == "System Update (Manuell)":
                update.update_system()
            elif choice == "Automatische Updates aktivieren":
                update.configure_unattended()
            elif choice == "E-Mail Benachrichtigungen konfigurieren":
                update.configure_mail()
            elif choice == "Dockhand aktualisieren":
                update.update_dockhand()
            elif choice == "Dockhand installieren":
                install.install_dockhand()
            elif choice == "Lazydocker installieren":
                install.install_lazydocker()
            elif choice == "ZSH (inkl. Oh My Zsh) installieren":
                install.install_zsh()
            elif choice == "Container aus Template installieren":
                install.install_container()
            elif choice == "DNS Server installieren":
                install.install_dns_server()
            elif choice == "Netzwerk konfigurieren (Statische IP)":
                network.configure_static_ip()
            elif choice == "IPVLAN konfigurieren":
                network.configure_ipvlan()
            elif choice == "Docker Netzwerk erstellen":
                network.create_network()
            elif choice == "Docker Netzwerke anzeigen":
                network.list_networks()
            elif choice == "CLI aktualisieren":
                update.update_self()
            elif choice == "Beenden":
                console.print("[bold blue]Auf Wiedersehen![/bold blue]")
                break
            
            console.print("\n")
            input("Press Enter to continue...")
            console.clear()
            print_header("DockerVM Dashboard")

if __name__ == "__main__":
    app()
