import cmd  # noqa: INP001
import os
import signal
import subprocess
import sys

from colorama import Fore


class K8sDashboardCmd(cmd.Cmd):
    intro = "Welcome to the K8s dashboard command line. Type help or ? to list commands.\n"
    prompt = "(k8s-dashboard) "

    tunnel_process: subprocess.Popen | None = None
    dashboard_process: subprocess.Popen | None = None
    browser_process: subprocess.Popen | None = None

    def __init__(self):
        if not os.path.exists("/usr/bin/minikube"):
            msg = "minikube binary not found at /usr/bin/minikube"
            raise FileNotFoundError(msg)
        if not os.path.exists("/usr/bin/kubectl"):
            msg = "kubectl binary not found at /usr/bin/kubectl"
            raise FileNotFoundError(msg)
        self.postcmd = self.stop
        super().__init__()

    def do_create(self, _):
        """create kubernetes cluster"""
        subprocess.run(
            ["/usr/bin/minikube", "start", "--driver=docker", "--cni=cilium", "--memory=4096", "--cpus=2"],
            check=True,
        )
        # addons
        subprocess.run(["/usr/bin/minikube", "addons", "enable", "metallb"], check=True)
        subprocess.run(["/usr/bin/minikube", "addons", "enable", "metrics-server"], check=True)

        # load docker image
        subprocess.run(["/usr/bin/minikube", "image", "load", "frontend-test:latest"], check=True)

    def do_delete(self, _arg):
        """delete kubernetes cluster"""
        subprocess.run(["/usr/bin/minikube", "delete"], check=True)

    def do_init(self, arg):
        """"""

    def do_dashboard(self, arg):
        "Start the Kubernetes dashboard"
        if arg.strip().lower() == "stop":
            # Stop the dashboard
            if self.dashboard_process:
                self.dashboard_process.terminate()
        elif arg.strip().lower() == "start" and not self.dashboard_process:
            self.dashboard_process = subprocess.Popen(["/usr/bin/minikube", "dashboard"])

    def _print_services(self):
        result = subprocess.run(
            ["/usr/bin/kubectl", "get", "services", "--namespace", "default"],
            check=False,
            capture_output=True,
            text=True,
        )
        print(f":{result.stdout}")

    def do_tunnel(self, arg):
        "Start the minikube tunnel"
        if arg.strip().lower() == "stop":
            if self.tunnel_process:
                self.tunnel_process.terminate()
        elif arg.strip().lower() == "start" and not self.tunnel_process:
            self.tunnel_process = subprocess.Popen(["/usr/bin/minikube", "tunnel", "-c"], stdout=subprocess.DEVNULL)
        # display ip/ports of services
        self._print_services()

    def stop(self, stop: bool, line: str) -> bool:  # noqa: ARG002
        "Internal clean up method"
        try:
            if self.tunnel_process:
                self.tunnel_process.terminate()
            if self.dashboard_process:
                self.dashboard_process.terminate()
            if self.browser_process:
                self.browser_process.terminate()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        return stop

    def do_clean(self, _):
        "Clean up all resources except minikube itself"
        path = os.environ.get("KUBE_FILES_PATH")
        if not path:
            print(Fore.RED + "KUBE_FILES_PATH environment variable not set." + Fore.RESET)
            return
        path += "/overlays/dev/"
        subprocess.run(["/usr/bin/kubectl", "delete", "-k", path], env={"KUBE_FILES_PATH": path}, check=False)

    def do_exit(self, _):
        "Exit the command line"
        print("Exiting...")
        return True


if __name__ == "__main__":
    cmd = K8sDashboardCmd()

    def signal_handler(sig, frame):  # noqa: ARG001
        print(Fore.GREEN + "\nSignal received, cleaning up..." + Fore.RESET)
        cmd.stop(True, "")  # type: ignore
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    cmd.cmdloop()
