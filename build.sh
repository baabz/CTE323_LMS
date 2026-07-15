#!/usr/bin/env bash
# build.sh — Render Build Script
# Runs during every deploy on Render

set -o errexit   # Exit on error

pip install --upgrade pip
pip install -r requirements.txt
