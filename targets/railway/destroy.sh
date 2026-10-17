#!/usr/bin/env bash
# The lab service stays; every live deployment of it is cancelled or removed.
set -euo pipefail
exec python3 targets/railway/railway_cleanup.py
