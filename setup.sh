#!/bin/bash
# DockerVM Installer Script

set -e

REPO_DIR="$(pwd)"

echo "Starting DVM CLI Installation..."

# 1. Install System Dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates curl gnupg lsb-release

# 2. Install Docker (if not already installed)
if command -v docker &> /dev/null; then
    echo "Docker is already installed: $(docker --version)"
else
    echo "Installing Docker Engine & Compose..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "Docker installed successfully!"
fi

# 2.1 Verify Docker Compose and Install Manually if needed
if docker compose version &> /dev/null; then
    echo "Docker Compose is working: $(docker compose version)"
else
    echo "Docker Compose CLI plugin not found or not working. Installing manually..."
    DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
    
    # Also install globally
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    
    echo "Docker Compose plugin installed manually."
fi

# 3. Setup Virtual Environment
echo "Setting up virtual environment..."
if [ -d ".venv" ]; then
    echo "Existing venv found."
else
    python3 -m venv .venv
fi

source .venv/bin/activate

# 4. Install Package
echo "Installing DVM CLI..."
pip install --upgrade pip
pip install .

# 5. Save repo path & Configure Base Path
sudo mkdir -p /etc/dvm
echo "$REPO_DIR" | sudo tee /etc/dvm/repo_path > /dev/null

# Prompt for Installation Base Directory
read -p "Where should containers be installed? [Default: /mnt/volumes]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/mnt/volumes}
echo "$INSTALL_DIR" | sudo tee /etc/dvm/base_path > /dev/null
echo "Base path set to: $INSTALL_DIR"

# Ensure base directory exists
sudo mkdir -p "$INSTALL_DIR"


# 6. Create wrapper scripts with absolute paths
echo "Creating global commands 'dvm' and 'dockervm'..."

cat <<EOF | sudo tee /usr/local/bin/dockervm > /dev/null
#!/bin/bash
source ${REPO_DIR}/.venv/bin/activate
exec dockervm "\$@"
EOF
sudo chmod +x /usr/local/bin/dockervm

cat <<EOF | sudo tee /usr/local/bin/dvm > /dev/null
#!/bin/bash
source ${REPO_DIR}/.venv/bin/activate
exec dvm "\$@"
EOF
sudo chmod +x /usr/local/bin/dvm

echo ""
echo "Installation complete! 🎉"
echo "Repo path: $REPO_DIR"
echo "You can now use the command: dvm (or dockervm)"
