
import typer
import questionary
from dockervm_cli.utils import run_command, console, print_header

app = typer.Typer(help="Netzwerkeinstellungen konfigurieren.")

@app.command("ip")
def configure_static_ip():
    """
    Konfiguriert eine statische IP via Netplan (Interaktiv).
    """
    
    console.print("[bold blue]Konfiguration Statische IP (Netplan)[/bold blue]")
    
    # 1. Ask for details
    ip_address = questionary.text("IP Adresse (z.B. 192.168.178.200/24):").ask()
    gateway = questionary.text("Gateway (z.B. 192.168.178.1):").ask()
    dns = questionary.text("DNS Server (kommagetrennt, z.B. 1.1.1.1,8.8.8.8):").ask()
    
    if not ip_address or not gateway or not dns:
        console.print("[red]Alle Felder müssen ausgefüllt werden![/red]")
        raise typer.Exit(code=1)
        
    dns_list = [d.strip() for d in dns.split(",")]
    dns_formatted = str(dns_list).replace("'", '"')
    
    # 2. Backup existing netplan
    console.print("[blue]Erstelle Backup der bestehenden Netplan Konfiguration...[/blue]")
    run_command("sudo mkdir -p /etc/netplan/backup", desc="Erstelle Backup Verzeichnis")
    run_command("sudo cp /etc/netplan/*.yaml /etc/netplan/backup/", desc="Kopiere YAML Dateien")
    
    # 3. Create new config
    # Note: We hardcode 'eth0' here for simplicity based on the old script, 
    # but a robust solution would list interfaces.
    interface = "eth0" 
    
    netplan_content = f"""network:
  version: 2
  ethernets:
    {interface}:
      addresses:
        - {ip_address}
      routes:
        - to: default
          via: {gateway}
      nameservers:
        addresses: {dns_formatted}
"""
    
    console.print(f"\n[cyan]Vorschau der neuen Konfiguration:[/cyan]\n{netplan_content}")
    
    if questionary.confirm("Möchtest du diese Konfiguration anwenden?").ask():
        try:
            with open("01-netcfg.yaml", "w") as f:
                f.write(netplan_content)
            
            # Move and Apply
            run_command("sudo rm -f /etc/netplan/*.yaml", desc="Entferne alte Konfigurationen")
            run_command(f"sudo mv 01-netcfg.yaml /etc/netplan/01-netcfg.yaml", desc="Schreibe neue Konfiguration")
            run_command("sudo chmod 600 /etc/netplan/01-netcfg.yaml", desc="Setze Berechtigungen")
            
            if run_command("sudo netplan apply", desc="Wende Netplan an"):
                console.print("[bold green]Netzwerk erfolgreich konfiguriert![/bold green]")
            else:
                console.print("[bold red]Fehler beim Anwenden von Netplan. Stelle Backup wieder her...[/bold red]")
                run_command("sudo cp /etc/netplan/backup/*.yaml /etc/netplan/", desc="Stelle Backup wieder her")
                run_command("sudo netplan apply", desc="Wende Backup an")
        except Exception as e:
            console.print(f"[bold red]Fehler: {e}[/bold red]")
    else:
        console.print("[yellow]Abgebrochen.[/yellow]")

@app.command("ipvlan")
def configure_ipvlan():
    """
    Richtet ein Docker IPVLAN Netzwerk ein.
    """
    
    console.print("[bold blue]IPVLAN Einrichtung[/bold blue]")
    
    subnet = questionary.text("Subnetz (z.B. 192.168.178.0/24):").ask()
    gateway = questionary.text("Gateway (z.B. 192.168.178.1):").ask()
    ip_range = questionary.text("IP Range für Docker (CIDR, z.B. 192.168.178.240/28):").ask()
    parent = questionary.text("Parent Interface (z.B. eth0):", default="eth0").ask()
    
    cmd = f"docker network create -d ipvlan --subnet={subnet} --gateway={gateway} --ip-range={ip_range} -o parent={parent} ipvlan_network"
    
    console.print(f"\n[cyan]Befehl:[/cyan] {cmd}")
    
    if questionary.confirm("Soll das Netzwerk erstellt werden?").ask():
        if run_command(cmd, desc="Erstelle Docker Netzwerk"):
            console.print("[bold green]IPVLAN Netzwerk erstellt![/bold green]")
        else:
            console.print("[bold red]Fehler beim Erstellen des Netzwerks.[/bold red]")
