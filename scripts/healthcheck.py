#!/usr/bin/env python3
"""CLI health probe for Docker and orchestrators. Exit 0 when all deps are up."""

from __future__ import annotations

import sys

from starscream.health import run_healthcheck_cli

if __name__ == "__main__":
    sys.exit(run_healthcheck_cli())
