
import typer
from typing import Optional
from dockervm_cli.utils import console

from dockervm_cli.commands import update, install, network

app = typer.Typer(
    name="dockervm",
    help="DockerVM Management CLI - A modern, centralized tool for managing your Docker VM.",
    add_completion=False,
    no_args_is_help=True
)

app.add_typer(update.app, name="update")
app.add_typer(install.app, name="install")
app.add_typer(network.app, name="network")

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
    table.add_row("dockervm system update", "Manuelles System-Update (apt update & upgrade)")
    table.add_row("dockervm update auto", "Automatische Updates aktivieren (Unattended-Upgrades)")
    table.add_row("dockervm update mail", "E-Mail Benachrichtigungen konfigurieren (SMTP)")
    table.add_row("dockervm update dockhand", "Dockhand Container aktualisieren")
    
    # Installation
    table.add_row("dockervm install docker", "Docker Engine & Compose installieren")
    table.add_row("dockervm install dockhand", "Dockhand installieren (mit Postgres)")
    
    # Network
    table.add_row("dockervm network ip", "Statische IP konfigurieren (Netplan)")
    table.add_row("dockervm network ipvlan", "IPVLAN Docker Netzwerk einrichten")
    
    # Misc
    table.add_row("dockervm update self", "Dieses CLI-Tool aktualisieren")
    table.add_row("dockervm commands", "Diese Liste anzeigen")
    
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
        console.print("DockerVM CLI Version: [bold cyan]0.1.0[/bold cyan]")
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
                    "Docker installieren",
                    "Dockhand installieren",
                    "Netzwerk konfigurieren (Statische IP)",
                    "IPVLAN konfigurieren",
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
            elif choice == "Docker installieren":
                install.install_docker()
            elif choice == "Dockhand installieren":
                install.install_dockhand()
            elif choice == "Netzwerk konfigurieren (Statische IP)":
                network.configure_static_ip()
            elif choice == "IPVLAN konfigurieren":
                network.configure_ipvlan()
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
