#!/bin/sh
# Construit l'image du controller (à lancer depuis la racine du dépôt)
cd "$(dirname "$0")" && docker build -t sdwan-controller .
