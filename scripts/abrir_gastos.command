#!/bin/bash
# macOS: doble clic en este archivo para abrir la app (ver docs/como-abrir.md).
cd "$(dirname "$0")/.." || exit 1
./.venv/bin/python main.py
