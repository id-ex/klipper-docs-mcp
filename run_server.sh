#!/bin/bash
cd /data/data/com.termux/files/home/klipper_docs_mcp
export PYTHONPATH=/data/data/com.termux/files/home/klipper_docs_mcp
export KLIPPER_DOCS_PATH=/data/data/com.termux/files/home/klipper_docs_mcp/docs
exec /data/data/com.termux/files/usr/bin/python -m klipper_docs_mcp.server
