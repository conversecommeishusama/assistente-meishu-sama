#!/usr/bin/env python3
"""Wrapper fino do shard B -- delega para sync_fase_g_periodicos_auditor_queue.py."""
import runpy
import sys

sys.argv = ["sync_fase_g_periodicos_auditor_queue.py", "B"]
runpy.run_path("scripts/sync_fase_g_periodicos_auditor_queue.py", run_name="__main__")
