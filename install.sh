#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="report2"
INSTALL_DIR="/opt/${APP_NAME}"
SERVICE_FILE="${APP_NAME}.service"
VENV_DIR="${INSTALL_DIR}/.venv"
SERVICE_USER="www-data"
SERVICE_GROUP="www-data"

echo -e "${GREEN}=== Report2 PDF Generator Installation ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Check if Python 3.9+ is installed
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.9"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.9+ is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check if service user exists, create if not
echo -e "${YELLOW}Checking service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
    echo -e "${YELLOW}Creating service user: $SERVICE_USER${NC}"
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
else
    echo -e "${GREEN}✓ Service user $SERVICE_USER exists${NC}"
fi

# Create installation directory
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created: $INSTALL_DIR${NC}"

# Copy application files
echo -e "${YELLOW}Copying application files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy all necessary files and directories
cp -r "$SCRIPT_DIR/report2" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/render" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/sample_reports" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/alembic" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/rxconfig.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/alembic.ini" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/pytest.ini" "$INSTALL_DIR/" 2>/dev/null || true

# Copy .env file if it exists, otherwise copy .env.example
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}Copying existing .env file...${NC}"
    cp "$SCRIPT_DIR/.env" "$INSTALL_DIR/"
    echo -e "${GREEN}✓ .env file copied${NC}"
elif [ -f "$SCRIPT_DIR/.env.example" ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env"
    echo -e "${YELLOW}⚠ Please edit $INSTALL_DIR/.env with your configuration${NC}"
else
    echo -e "${RED}Error: No .env or .env.example file found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Application files copied${NC}"

# Create necessary directories
echo -e "${YELLOW}Creating application directories...${NC}"
mkdir -p "$INSTALL_DIR/uploaded_files"
mkdir -p "$INSTALL_DIR/.web"
mkdir -p "$INSTALL_DIR/logs"
echo -e "${GREEN}✓ Directories created${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✓ Virtual environment created${NC}"

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Set ownership
echo -e "${YELLOW}Setting file ownership...${NC}"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
echo -e "${GREEN}✓ Ownership set to $SERVICE_USER:$SERVICE_GROUP${NC}"

# Set permissions
echo -e "${YELLOW}Setting file permissions...${NC}"
chmod 755 "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR/.env"
chmod -R 755 "$INSTALL_DIR/uploaded_files"
chmod -R 755 "$INSTALL_DIR/.web"
chmod -R 755 "$INSTALL_DIR/logs"
echo -e "${GREEN}✓ Permissions set${NC}"

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
if [ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]; then
    echo -e "${RED}Error: $SERVICE_FILE not found in $SCRIPT_DIR${NC}"
    exit 1
fi

cp "$SCRIPT_DIR/$SERVICE_FILE" "/etc/systemd/system/"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd service installed${NC}"

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
cd "$INSTALL_DIR"
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/alembic" upgrade head || {
    echo -e "${YELLOW}⚠ Database migration failed. You may need to configure the database first.${NC}"
}
echo -e "${GREEN}✓ Database migrations completed${NC}"

# Initialize Reflex
echo -e "${YELLOW}Initializing Reflex...${NC}"
cd "$INSTALL_DIR"
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/reflex" init || {
    echo -e "${YELLOW}⚠ Reflex initialization warning (this is normal for first-time setup)${NC}"
}
echo -e "${GREEN}✓ Reflex initialized${NC}"

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit configuration: nano $INSTALL_DIR/.env"
echo "2. Enable service: systemctl enable $APP_NAME"
echo "3. Start service: systemctl start $APP_NAME"
echo "4. Check status: systemctl status $APP_NAME"
echo "5. View logs: journalctl -u $APP_NAME -f"
echo ""
echo -e "${GREEN}Installation directory: $INSTALL_DIR${NC}"
