from __future__ import annotations

import asyncio
import threading
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, RichLog, Sparkline

from server_manager.common.api.docker_image_api import docker_image_spawn_container
from server_manager.common.container_data import ContainerData
from server_manager.common.template import TemplateManager
from server_manager.gui.widgets.server_form import ServerForm


class MyWindow(App):
    TITLE = "Server Manager"
    BINDINGS: ClassVar = [("q", "quit", "Quit the application")]
    CSS_PATH: ClassVar = [
        "resources/main.tcss",
        "resources/server_form.tcss",
        "resources/confirmation_prompt.tcss",
    ]

    server_table: DataTable
    servers: dict[str, ContainerData]
    _selected_server_key: str | None
    plots: list[Sparkline]
    log_widget: RichLog
    log_thread_obj: threading.Thread

    def __init__(self):
        self.log_thread_obj = threading.Thread(target=self.log_thread, daemon=True)
        self.log_widget = RichLog()
        self.log_widget.styles.width = "0.5fr"
        self.servers = {container.name: container for container in ContainerData.get_all_containers()}
        self.server_table = DataTable(cursor_type="row")
        self.plots = [Sparkline(), Sparkline(), Sparkline()]
        self._selected_server_key = None
        super().__init__()

    async def poll_active_server(self) -> None:
        while True:
            for server in self.servers.values():
                await server.metrics_task()
            await asyncio.sleep(5)

    def on_mount(self) -> None:
        pass

    @property
    def selected_server(self) -> ContainerData | None:
        if self._selected_server_key is None:
            return None
        return self.servers.get(self._selected_server_key)

    def compose(self) -> ComposeResult:
        if len(self.server_table.columns) == 0:
            self.server_table.add_column("Server Name", key="server_name", width=20)
            self.server_table.add_column("Status", key="status", width=10)
            self.server_table.add_column("Uptime", key="uptime", width=10)
            self.server_table.add_column("CPU", key="cpu", width=10)
            self.server_table.add_column("Memory", key="memory", width=10)
            self.server_table.add_column("Network ▲", key="network_up", width=10)
            self.server_table.add_column("Network ▼", key="network_down", width=10)
            self.server_table.add_column("Storage ▲", key="storage_up", width=10)
            self.server_table.add_column("Storage ▼", key="storage_down", width=10)
        yield Header()
        with Horizontal():
            with Vertical(classes="control_panel"):
                with Horizontal(classes="control_panel_button_pane"):
                    yield Button(
                        "Create New Server",
                        id="create_server",
                        classes="control_panel_button",
                    )
                    yield Button(
                        "Delete Selected Server",
                        id="delete_server",
                        classes="control_panel_button",
                    )
                    yield Button("Debug Log", id="debug_log", classes="control_panel_button")
                    yield Button("Stop Selected Server", id="stop_server", classes="control_panel_button")
                    yield Button("Start Selected Server", id="start_server", classes="control_panel_button")
                yield self.server_table
            yield self.log_widget
        yield Footer()
        self.run_worker(self.poll_active_server)
        self.run_worker(self.monitor_servers)
        for server_name in self.servers:
            self.create_row(server_name)

    @on(Button.Pressed, "#create_server")
    async def create_server(self) -> None:
        self.push_screen(ServerForm(TemplateManager().get_templates()), callback=self.on_server_created)

    @on(Button.Pressed, "#stop_server")
    async def stop_server(self) -> None:
        if self.selected_server:
            self.selected_server.container.stop()

    @on(Button.Pressed, "#start_server")
    async def start_server(self) -> None:
        if self.selected_server:
            self.selected_server.container.start()

    async def monitor_servers(self) -> None:
        while True:
            await asyncio.sleep(2)
            # monitor all rows in table and associated stats
            for row in self.server_table.rows:
                # get Container_data for row
                row_data = self.server_table.get_row(row)
                container_data = self.servers.get(row_data[0])
                if container_data and len(container_data.metrics) > 0:
                    latest_data = container_data.metrics[-1]
                    if latest_data:
                        self.server_table.update_cell(row, "status", container_data.container.status)
                        self.server_table.update_cell(
                            row, "uptime", container_data.container.attrs["State"]["StartedAt"]
                        )
                        self.server_table.update_cell(row, "cpu", latest_data.cpu_perc)
                        self.server_table.update_cell(row, "memory", latest_data.mem_perc)
                        self.server_table.update_cell(row, "network_up", latest_data.net_io_up)
                        self.server_table.update_cell(row, "network_down", latest_data.net_io_down)
                        self.server_table.update_cell(row, "storage_up", latest_data.block_io_up)
                        self.server_table.update_cell(row, "storage_down", latest_data.block_io_down)

    def _add_server(self, image_name, server_name, env):
        new_container = docker_image_spawn_container(image_name, server_name, env)
        if new_container:
            # add row with empty data so it
            self.create_row(server_name)

    def create_row(self, server_name: str) -> None:
        self.server_table.add_row(
            server_name,
            "--",
            "--",
            "--",
            "--",
            "--",
            "--",
            "--",
            "--",
        )

    def on_server_created(self, data) -> None:
        server_name = data.get("server_name", "")
        image_name = data.get("image_name", "")
        env = data.get("env", {})
        self._add_server(image_name, server_name, env)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_server_key = self.server_table.get_row(event.row_key)[0]
        self.switch_log()

    # log threading

    def switch_log(self):
        if self.log_thread_obj.is_alive():
            self.cancel_log_stream()
        self.log_thread_obj = threading.Thread(target=self.log_thread, daemon=True)
        self.log_thread_obj.start()

    def log_thread(self) -> None:
        if self.selected_server:
            self.log_widget.clear()
            self.log_stream = self.selected_server.container.logs(stream=True, tail=100)
            for line in self.log_stream:
                self.log_widget.write(line.decode("utf-8").rstrip())
        else:
            self.log_widget.clear()
            self.log_widget.write("No server selected.")

    def cancel_log_stream(self) -> None:
        if self.log_stream:
            self.log_stream.close()
