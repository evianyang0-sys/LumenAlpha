#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../web/sector_rotation_dashboard"
npm start -- "$@"
