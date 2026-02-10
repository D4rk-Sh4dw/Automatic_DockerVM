#!/bin/bash
# DockerVM Installer Script

set -e

REPO_DIR="$(pwd)"

echo "Starting DVM CLI Installation..."

# 1. Install System Dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# 2. Setup Virtual Environment
echo "Setting up virtual environment..."
if [ -d ".venv" ]; then
    echo "Existing venv found."
else
    python3 -m venv .venv
fi

source .venv/bin/activate

# 3. Install Package
echo "Installing DVM CLI..."
pip install --upgrade pip
pip install .

# 4. Save repo path for 'dvm update self'
sudo mkdir -p /etc/dvm
echo "$REPO_DIR" | sudo tee /etc/dvm/repo_path > /dev/null

# 5. Create wrapper scripts with absolute paths
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
