#!/bin/bash
set -e

# Switch to x86_64 Colima VM for building
colima stop default 2>/dev/null || true
colima start x86_64

# Build for Linux AMD64 architecture (for Yandex Cloud deployment)
docker build --platform linux/amd64 -t cr.yandex/crpd2b5gg7tt3399i6c9/t-app-reports:v0.1 .
docker push cr.yandex/crpd2b5gg7tt3399i6c9/t-app-reports:v0.1
