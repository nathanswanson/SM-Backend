from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any, ClassVar

import docker.errors
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, RichLog, Sparkline

from server_manager.common.api.docker_container_api import docker
from server_manager.common.api.docker_image_api import docker_image_spawn_container
from server_manager.common.template import TemplateManager
from server_manager.gui.widgets.confirmation_prompt import ConfirmationPrompt
from server_manager.gui.widgets.server_form import ServerForm

if TYPE_CHECKING:
    from docker.models.containers import Container


class RichLogWriter:
    def __init__(self, rich_log):
        self.rich_log = rich_log

    def write(self, message):
        if message.strip():
            self.rich_log.write(message.rstrip())

    def flush(self):
        pass  # Needed for compatibility


class MyWindow(App):
    TITLE = "Server Manager"
    container_logs: dict[str, RichLog]
    container_log_tasks: dict[str, asyncio.Task]

    active_servers_table: DataTable
    selected_server: str = ""
    server_was_selected_event: asyncio.Event
    containers: list

    image_name_to_id: dict[str, str]
    image_id_to_name: dict[str, str]

    BINDINGS: ClassVar = [("q", "quit", "Quit the application")]
    CSS_PATH: ClassVar = [
        "resources/main.tcss",
        "resources/server_form.tcss",
        "resources/confirmation_prompt.tcss",
    ]

    # plot data
    plots: dict[str, Sparkline]
    plot_data_window_size = 100
    plot_data: dict[str, list[float]]

    def __init__(self, docker_client):
        self.server_was_selected_event = asyncio.Event()
        self.image_id_to_name = {}
        self.image_name_to_id = {}
        self.container_log_tasks = {}
        self.plot_data = {
            "server_memory_usage": [0] * self.plot_data_window_size,
            "server_network_usage": [0] * self.plot_data_window_size,
            "server_cpu_usage": [0] * self.plot_data_window_size,
            "server_storage_usage": [0] * self.plot_data_window_size,
        }
        self.plots = {
            "server_memory_usage": Sparkline(id="server_memory_usage"),
            "server_network_usage": Sparkline(id="server_network_usage"),
            "server_cpu_usage": Sparkline(id="server_cpu_usage"),
            "server_storage_usage": Sparkline(id="server_storage_usage"),
        }
        self.client = docker_client
        self.fields: dict[str, str] = {}
        self.active_servers_table = DataTable(show_header=True, cursor_type="row")
        self.update_container_data()
        self.update_image_data()
        sys.stdout = RichLogWriter(self.container_logs[self.selected_server])
        sys.stderr = RichLogWriter(self.container_logs[self.selected_server])
        super().__init__()

    def on_mount(self) -> None:
        self.run_worker(self.manager_task())
        self.run_worker(self.collect_stats())
        self.run_worker(self.update_graphs())

    def update_container_data(self):
        self.container_logs = {
            container.name: RichLog(
                id=container.name, max_lines=100, classes="logs_panel"
            )
            for container in self.client.containers.list()
        }
        self.container_logs.update(
            {"": RichLog(id="default_log", classes="logs_panel", max_lines=100)}
        )
        self.containers = list(self.client.containers.list())

    def update_image_data(self):
        self.image_id_to_name = self.get_server_names()
        self.image_name_to_id = {v: k for k, v in self.image_id_to_name.items()}

    def compose(self) -> ComposeResult:
        if len(self.active_servers_table.columns) == 0:
            self.active_servers_table.add_column("Server Name", width=20)
            self.active_servers_table.add_column("Status", width=10)
            self.active_servers_table.add_column("Uptime", width=10)
            self.active_servers_table.add_column("CPU", width=10)
            self.active_servers_table.add_column("Memory", width=10)
            self.active_servers_table.add_column("Network", width=10)
            self.active_servers_table.add_column("Storage", width=10)
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
                    yield Button(
                        "Debug Log", id="debug_log", classes="control_panel_button"
                    )
                yield self.active_servers_table
            with Vertical(classes="metrics_panel"):
                for plot in self.plots.values():
                    if plot.id is not None:
                        yield Label(
                            plot.id.replace("_", " ").title(), classes="plot_label"
                        )
                    yield plot
            yield self.container_logs[self.selected_server]
        yield Footer()

    def id_to_name(self, server_id: str) -> str:
        ret = server_id
        ret = ret.split("/")[-1]
        return ret.split(":")[0]

    def get_server_names(self) -> dict[str, str]:
        for image in self.client.images.list():
            self.image_id_to_name[image.tags[0]] = self.id_to_name(image.tags[0])
        return self.image_id_to_name

    def confirmation_callback(self, container_name: Any):
        if container_name is not None:
            container = self.client.containers.get(container_name)
            if container:
                try:
                    container.stop()
                    container.remove()
                    self.log(f"Container {container_name} stopped and removed.")
                except docker.errors.APIError as e:
                    self.log(f"Error stopping/removing container {container_name}: {e}")
            self.refresh_container_table()

    @on(Button.Pressed, ".control_panel_button")
    def button_callback(self, event: Button.Pressed):
        if event.button.id == "create_server":
            self.push_screen(
                ServerForm(TemplateManager().get_templates()),
                callback=self.server_form_callback,
            )
        elif event.button.id == "delete_server":
            if self.selected_server != "":
                self.push_screen(
                    ConfirmationPrompt(self.selected_server),
                    callback=self.confirmation_callback,
                )
        elif event.button.id == "debug_log":
            self.server_was_selected_event.clear()
            self.selected_server = ""
            self.refresh(recompose=True)

    async def capture_container_log(self, container: Container):
        def stream_logs():
            for char in container.logs(stream=True, follow=True, tail=150):
                if container is not None and container.name is not None:
                    self.container_logs[container.name].write(
                        char.decode("utf-8").strip()
                    )

        await asyncio.to_thread(stream_logs)

    async def update_graphs(self):
        # window size of 0
        while True:
            for plot_id, plot in self.plots.items():
                plot.data = self.plot_data[plot_id]
                await asyncio.sleep(1)  # Update every second
            await asyncio.sleep(1)

    def cpu_per(
        self, cpu_stats: dict[str, Any], prev_cpu_stats: dict[str, Any]
    ) -> float:
        if not prev_cpu_stats:
            return 0.0
        cpu_delta = (
            cpu_stats["cpu_usage"]["total_usage"]
            - prev_cpu_stats["cpu_usage"]["total_usage"]
        )
        return (
            cpu_delta
            / (
                cpu_stats["cpu_usage"]["system_cpu_usage"]
                - prev_cpu_stats["cpu_usage"]["system_cpu_usage"]
            )
            * 100.0
        )

    async def collect_stats(self):
        # this for loop is infinite, it will run until the container is stopped
        await self.server_was_selected_event.wait()
        for stat in self.client.containers.get(self.selected_server).stats(
            stream=True, decode=True
        ):
            self.plot_data["server_cpu_usage"].append(
                self.cpu_per(stat["cpu_stats"], stat["precpu_stats"])
            )
            self.plot_data["server_memory_usage"].append(
                stat["memory_stats"]["usage"] / stat["memory_stats"]["limit"] * 100
            )
            self.plot_data["server_storage_usage"].append(0)
            self.plot_data["server_network_usage"].append(
                stat["networks"]["eth0"]["tx_bytes"]
            )
            if len(self.plot_data["server_cpu_usage"]) > self.plot_data_window_size:
                self.plot_data["server_cpu_usage"].pop(0)
                self.plot_data["server_memory_usage"].pop(0)
                self.plot_data["server_storage_usage"].pop(0)
                self.plot_data["server_network_usage"].pop(0)
            await asyncio.sleep(1)

    async def manager_task(self):
        self.refresh_container_table()

        while True:
            # await asyncio.sleep(5)  # Adjust the sleep time as needed
            async with asyncio.TaskGroup() as tg:
                for container in self.containers:
                    if (
                        container.status == "running"
                        and container.name not in self.container_log_tasks
                    ):
                        self.container_log_tasks[container.name] = tg.create_task(
                            self.capture_container_log(container), name=container.name
                        )
            await asyncio.sleep(1)

    def refresh_container_table(self):
        row = self.active_servers_table.cursor_row
        self.active_servers_table.clear()
        self.containers = list(self.client.containers.list())
        for container in self.containers:
            uptime = container.attrs["State"]["StartedAt"]
            self.active_servers_table.add_row(
                container.name,
                container.status,
                uptime,
                self.plot_data["server_cpu_usage"][-1],
                self.plot_data["server_memory_usage"][-1],
                self.plot_data["server_network_usage"][-1],
                self.plot_data["server_storage_usage"][-1],
            )
        self.active_servers_table.move_cursor(row=row)

    def server_form_callback(self, result: Any):
        # {"image_name": "image_name", "server_name": "string", "env": env}
        image_name = result.get("image_name")
        server_name = result.get("server_name")
        env = result.get("env", {})
        if not image_name:
            logging.warning("Image name or server name is missing.")
            return
        docker_image_spawn_container(image_name, server_name, env)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.selected_server = self.active_servers_table.get_row(event.row_key)[0]
        self.sub_title = self.selected_server
        self.server_was_selected_event.set()
        self.refresh_container_table()
        self.refresh(recompose=True)
