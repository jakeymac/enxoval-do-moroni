#!/bin/sh
# Runs Django (:8000) and Vite (:5173) together. Open http://localhost:5173
set -e
case "$0" in */*) cd "${0%/*}" ;; esac
trap 'kill 0' EXIT INT TERM
./.venv/bin/python backend/manage.py runserver 8000 &
(cd frontend && npm run dev) &
wait
