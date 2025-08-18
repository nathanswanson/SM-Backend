import ast
import asyncio
import re
import subprocess
from collections import deque
from dataclasses import dataclass

from docker.models.containers import Container

from server_manager.common.api.docker_container_api import docker_list_containers

data_table_go_format = '["{{.CPUPerc}}","{{.MemPerc}}","{{.NetIO}}","{{.BlockIO}}"]'
static_table_go_format = '["{{.ID}}","{{.Name}}","{{.MemUsage}}"]'


@dataclass
class DockerStatEntry:
    cpu_perc: str
    mem_perc: str
    net_io_up: str
    net_io_down: str
    block_io_up: str
    block_io_down: str


class ContainerData:
    id: str
    name: str
    max_mem: float
    container: Container
    metrics: deque[DockerStatEntry]

    def __init__(self, container: Container):
        self.container = container
        self._rate_pattern = re.compile(r"(.*) \/ (.*)")
        self._init_metrics()
        self._poll_static_data()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ContainerData):
            return other.id == self.id
        if isinstance(other, str):
            return other == self.name
        return NotImplemented

    def _init_metrics(self):
        self.metrics = deque(maxlen=100)
        assert self.metrics.maxlen is not None, ""
        while len(self.metrics) < self.metrics.maxlen:
            self.metrics.append(DockerStatEntry("--", "--", "--", "--", "--", "--"))

    def _poll_static_data(self):
        if not self.container or not self.container.id:
            return
        result = subprocess.run(
            [
                "/usr/bin/docker",
                "stats",
                "--no-stream",
                "--format",
                static_table_go_format,
                self.container.id,
            ],
            capture_output=True,
            check=True,
        )
        if result.returncode == 0:
            # Parse the output and update the static data
            output = result.stdout.decode("utf-8").strip()
            out_list = ast.literal_eval(output)

            self.id = out_list[0]
            self.name = out_list[1]
            self.max_mem = float(re.sub(r"\D", "", self._get_mem_max(out_list[2])[1]))

    def _get_mem_max(self, string_data: str) -> tuple[str, str]:
        match = re.search(self._rate_pattern, string_data)
        if match:
            return (match.group(1), match.group(2))
        return ("--", "--")

    async def metrics_task(self):
        await self._poll_stats()

    async def _poll_stats(self):
        if not self.container or not self.container.id:
            return None
        result = await asyncio.create_subprocess_exec(
            "docker",
            "stats",
            "--no-stream",
            "--format",
            data_table_go_format,
            self.container.id,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await result.wait()
        if result.returncode == 0 and result.stdout:
            output = await result.stdout.read()
            out_list: list[str] = ast.literal_eval(output.decode("utf-8").strip())
            self.metrics.pop()
            stats = DockerStatEntry(
                cpu_perc=out_list[0],
                mem_perc=out_list[1],
                net_io_up=self._get_mem_max(out_list[2])[0],
                net_io_down=self._get_mem_max(out_list[2])[1],
                block_io_up=self._get_mem_max(out_list[3])[0],
                block_io_down=self._get_mem_max(out_list[3])[1],
            )
            self.metrics.append(stats)

    @staticmethod
    def get_container_by_name(name: str) -> "ContainerData | None":
        for container in ContainerData.get_all_containers():
            if container.name == name:
                return container
        return None

    @staticmethod
    def get_all_containers() -> "list[ContainerData]":
        return [ContainerData(container) for container in docker_list_containers()]
