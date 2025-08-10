import subprocess

from docker.models.containers import Container

table_go_format = '["{{.ID}}","{{.Name}}","{{.CPUPerc}}","{{.MemUsage}}","{{.MemPerc}}","{{.NetIO}}"]'


class ContainerMonitor:
    def __init__(self, container: Container):
        self.container = container

    def poll_stats(self):
        if not self.container or not self.container.id:
            return None
        result = subprocess.run(
            args=["docker", "stats", "--no-stream", "--format", table_go_format, self.container.id],
            check=True,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return result.stdout
        return None
