#!/bin/bash
rsync -avz --exclude '.venv' --exclude '.github' --exclude '.vscode' --exclude '.gitignore' --exclude '.git' /home/wsl/Textual/server-manager/backend/ game-server@raspberrypi.home:/home/game-server/backend
ssh game-server@raspberrypi.home "cd /home/game-server/backend &&  hatch run server_manager -- --host=192.168.0.145 --port=8000"
