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

# Stop service if already running (safe no-op if not installed yet)
if systemctl is-active --quiet "$APP_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Stopping running $APP_NAME service...${NC}"
    systemctl stop "$APP_NAME"
    echo -e "${GREEN}✓ Service stopped${NC}"
fi

# Create installation directory
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created: $INSTALL_DIR${NC}"

# Copy application files
echo -e "${YELLOW}Copying application files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Sync code directories (--delete removes stale files from old releases)
rsync -a --delete "$SCRIPT_DIR/report2/"       "$INSTALL_DIR/report2/"
rsync -a --delete "$SCRIPT_DIR/render/"        "$INSTALL_DIR/render/"
rsync -a --delete "$SCRIPT_DIR/sample_reports/" "$INSTALL_DIR/sample_reports/"
rsync -a --delete "$SCRIPT_DIR/alembic/"       "$INSTALL_DIR/alembic/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/rxconfig.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/alembic.ini" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/pytest.ini" "$INSTALL_DIR/" 2>/dev/null || true

# Copy .env file only if one does not already exist in INSTALL_DIR
if [ -f "$INSTALL_DIR/.env" ]; then
    echo -e "${GREEN}✓ Existing $INSTALL_DIR/.env kept (not overwritten)${NC}"
elif [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}Copying .env file...${NC}"
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
mkdir -p "$INSTALL_DIR/.states"
echo -e "${GREEN}✓ Directories created${NC}"

# Create www-data home directory for Reflex
echo -e "${YELLOW}Setting up www-data home directory for Reflex...${NC}"
WWW_HOME="/var/www"
mkdir -p "$WWW_HOME/.local/share"
mkdir -p "$WWW_HOME/.cache"
mkdir -p "$WWW_HOME/.config"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WWW_HOME/.local" "$WWW_HOME/.cache" "$WWW_HOME/.config"
echo -e "${GREEN}✓ www-data home directory structure created${NC}"

# Set HOME environment variable for www-data user
if ! grep -q "^$SERVICE_USER:" /etc/passwd; then
    echo -e "${YELLOW}Setting HOME directory for $SERVICE_USER...${NC}"
    usermod -d "$WWW_HOME" "$SERVICE_USER" || true
    echo -e "${GREEN}✓ HOME directory set${NC}"
fi

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
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WWW_HOME/.local" "$WWW_HOME/.cache" "$WWW_HOME/.config"
echo -e "${GREEN}✓ Ownership set to $SERVICE_USER:$SERVICE_GROUP${NC}"

# Set permissions
echo -e "${YELLOW}Setting file permissions...${NC}"
chmod 755 "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR/.env"
chmod -R 755 "$INSTALL_DIR/uploaded_files"
chmod -R 755 "$INSTALL_DIR/.web"
chmod -R 755 "$INSTALL_DIR/logs"
chmod -R 755 "$INSTALL_DIR/.web"
chmod -R 755 "$INSTALL_DIR/.states"
echo -e "${GREEN}✓ Permissions set${NC}"

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
if [ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]; then
    echo -e "${RED}Error: $SERVICE_FILE not found in $SCRIPT_DIR${NC}"
    exit 1
fi

cp "$SCRIPT_DIR/$SERVICE_FILE" "/etc/systemd/system/"
systemctl daemon-reload
# Re-enable the service in case the unit file changed
systemctl enable "$APP_NAME" 2>/dev/null || true
echo -e "${GREEN}✓ Systemd service installed${NC}"

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
cd "$INSTALL_DIR"
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/alembic" upgrade head || {
    echo -e "${YELLOW}⚠ Database migration failed. You may need to configure the database first.${NC}"
}
echo -e "${GREEN}✓ Database migrations completed${NC}"

# Build Reflex frontend (export static assets)
echo -e "${YELLOW}Building Reflex frontend (this may take a while)...${NC}"
cd "$SCRIPT_DIR"
"$VENV_DIR/bin/reflex" export --frontend-only --no-zip || {
    echo -e "${RED}Error: Reflex frontend build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Reflex frontend built${NC}"

# Copy built frontend assets to install directory
echo -e "${YELLOW}Copying frontend assets...${NC}"
rsync -a --delete "$SCRIPT_DIR/.web/" "$INSTALL_DIR/.web/"
echo -e "${GREEN}✓ Frontend assets copied${NC}"

# Fix ownership and permissions on .web after build+copy (build runs as root)
echo -e "${YELLOW}Setting ownership and permissions on frontend assets...${NC}"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR/.web"
# Directories: rwxr-xr-x (755), files: rw-r--r-- (644)
# .web/backend/ needs to be writable by www-data at runtime (e.g. upload_is_used sentinel)
chmod -R u+rwX,go+rX "$INSTALL_DIR/.web"
echo -e "${GREEN}✓ Frontend asset ownership set to $SERVICE_USER:$SERVICE_GROUP${NC}"

# Start (or restart) the service if it was already enabled
if systemctl is-enabled --quiet "$APP_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Starting $APP_NAME service...${NC}"
    systemctl start "$APP_NAME"
    echo -e "${GREEN}✓ Service started${NC}"
fi

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit configuration: nano $INSTALL_DIR/.env"
echo "2. Enable & start service: systemctl enable --now $APP_NAME"
echo "3. Check status: systemctl status $APP_NAME"
echo "4. View logs: journalctl -u $APP_NAME -f"
echo ""
echo -e "${YELLOW}Service management commands:${NC}"
echo "  Start:   systemctl start $APP_NAME"
echo "  Stop:    systemctl stop $APP_NAME"
echo "  Restart: systemctl restart $APP_NAME"
echo "  Status:  systemctl status $APP_NAME"
echo "  Logs:    journalctl -u $APP_NAME -f"
echo ""
echo -e "${GREEN}Installation directory: $INSTALL_DIR${NC}"
echo -e "${GREEN}Service user home: $WWW_HOME${NC}"
