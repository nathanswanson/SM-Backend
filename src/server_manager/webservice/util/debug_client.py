import cmd
from collections import deque

import socketio
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

server_url = "http://localhost:8000"
sio = socketio.Client()

console = Console()
log_messages = deque(maxlen=30)  # Keep last 30 messages


def add_log(message):
    log_messages.append(message)
    redraw()


def log_panel():
    return Panel(Text("\n".join(log_messages)), title="Log", border_style="blue")


def redraw():
    console.clear()
    console.print(log_panel())


sio.on("*")


def route_messages(event, sid, data):
    print(event, sid, data)
    add_log([event, sid, data])


class ClientShell(cmd.Cmd):
    intro = "Socket.io Debug client. ? to list commands.\n"
    prompt = "(client) "

    def do_connect(self, _args):
        sio.connect(server_url)
        add_log(f"connected: {sio.connected}")
        print(f"connected: {sio.connected}")

    def do_bye(self, _args):
        add_log("disconnecting...")
        sio.disconnect()
        add_log(f"disconnected: {not sio.connected}")
        print(f"disconnected: {not sio.connected}")

    def do_subscribe(self, args):
        room = "01+testter"
        if len(args) > 1:
            room = args[0]
        sio.emit("subscribe", room)
        add_log(f"Subscribed to room: {room}")


if __name__ == "__main__":
    redraw()  # Draw log at startup
    ClientShell().cmdloop()
