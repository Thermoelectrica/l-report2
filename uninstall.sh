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

echo -e "${YELLOW}=== Report2 PDF Generator Uninstallation ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Confirm uninstallation
read -p "Are you sure you want to uninstall Report2? This will remove all files from $INSTALL_DIR (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Uninstallation cancelled${NC}"
    exit 0
fi

# Stop and disable service
if systemctl is-active --quiet "$APP_NAME"; then
    echo -e "${YELLOW}Stopping service...${NC}"
    systemctl stop "$APP_NAME"
    echo -e "${GREEN}✓ Service stopped${NC}"
fi

if systemctl is-enabled --quiet "$APP_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Disabling service...${NC}"
    systemctl disable "$APP_NAME"
    echo -e "${GREEN}✓ Service disabled${NC}"
fi

# Remove systemd service file
if [ -f "/etc/systemd/system/$SERVICE_FILE" ]; then
    echo -e "${YELLOW}Removing systemd service file...${NC}"
    rm "/etc/systemd/system/$SERVICE_FILE"
    systemctl daemon-reload
    echo -e "${GREEN}✓ Service file removed${NC}"
fi

# Backup .env file
if [ -f "$INSTALL_DIR/.env" ]; then
    BACKUP_FILE="/tmp/${APP_NAME}_env_backup_$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}Backing up .env file to $BACKUP_FILE${NC}"
    cp "$INSTALL_DIR/.env" "$BACKUP_FILE"
    echo -e "${GREEN}✓ .env file backed up${NC}"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Removing installation directory...${NC}"
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Installation directory removed${NC}"
fi

echo ""
echo -e "${GREEN}=== Uninstallation Complete ===${NC}"
echo ""
if [ -f "$BACKUP_FILE" ]; then
    echo -e "${YELLOW}Your .env file was backed up to: $BACKUP_FILE${NC}"
fi
echo -e "${YELLOW}Note: The service user 'www-data' was not removed as it may be used by other services${NC}"
