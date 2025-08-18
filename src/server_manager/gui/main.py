import signal
import sys

import docker
import docker.errors

from server_manager.gui.manager_app import MyWindow


def signal_handler(_signal, _frame):
    client = docker.from_env()  # Initialize Docker
    for container in client.containers.list():
        try:  # noqa: SIM105
            container.stop()
        except docker.errors.APIError:
            pass
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    app = MyWindow()
    app.run()
