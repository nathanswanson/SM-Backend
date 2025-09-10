#!/bin/bash
ssh game-server@raspberrypi.home "kill \$(ps x | grep 'python' | grep 'server_manager' | awk '{print \$1}')"