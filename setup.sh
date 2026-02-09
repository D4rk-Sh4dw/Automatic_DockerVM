#!/bin/bash
# DockerVM Installer Script

set -e

echo "Starting DockerVM CLI Installation..."

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
echo "Installing DockerVM CLI..."
pip install --upgrade pip
pip install .

# 4. Create Symlink
echo "Creating global command 'dockervm'..."
# Create a wrapper script that uses the venv python
cat <<EOF | sudo tee /usr/local/bin/dockervm > /dev/null
#!/bin/bash
source $(pwd)/.venv/bin/activate
exec dockervm "\$@"
EOF

sudo chmod +x /usr/local/bin/dockervm

echo ""
echo "Installation complete! 🎉"
echo "You can now use the command: dockervm"
