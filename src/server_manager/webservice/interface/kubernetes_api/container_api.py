import os
from http import HTTPStatus
from typing import override

from kubernetes import config
from kubernetes.client import ApiClient, ApiException, AppsV1Api, CoreV1Api, V1Deployment, V1DeploymentStatus, V1Service
from kubernetes.stream import stream

from server_manager.webservice.db_models import ServersCreate, TemplatesCreate
from server_manager.webservice.interface.interface import ControllerContainerInterface
from server_manager.webservice.logger import sm_logger

namespace = "game-servers"


class KubernetesContainerAPI(ControllerContainerInterface):
    core_client: CoreV1Api
    app_client: AppsV1Api

    def __init__(self):
        configuration = (
            config.load_kube_config() if os.environ.get("SM_ENV", None) == "DEV" else config.load_incluster_config()
        )
        self.core_client = CoreV1Api(api_client=ApiClient(configuration=configuration))
        self.app_client = AppsV1Api(api_client=ApiClient(configuration=configuration))

    def replicas_patch(self, replicas: int):
        return {"spec": {"replicas": replicas}}

    @override
    async def start(self, container_name: str) -> bool:
        sm_logger.info(f"Starting container {container_name} in Kubernetes")
        # set k8 deployment to replicas=1
        try:
            self.app_client.patch_namespaced_deployment_scale(
                name=container_name,
                namespace=namespace,
                body=self.replicas_patch(1),
            )
        except ApiException as e:
            sm_logger.error(f"Error starting container {container_name}: {e}")
            return False
        return True

    @override
    async def stop(self, container_name: str) -> bool:
        sm_logger.info(f"Stopping container {container_name} in Kubernetes")
        # set k8 deployment to replicas=0
        try:
            self.app_client.patch_namespaced_deployment_scale(
                name=container_name,
                namespace=namespace,
                body=self.replicas_patch(0),
            )
        except ApiException as e:
            sm_logger.error(f"Error stopping container {container_name}: {e}")
            return False
        return True

    @override
    async def remove(self, container_name: str) -> bool:
        # delete k8 deployment
        try:
            self.app_client.delete_namespaced_deployment(
                name=container_name,
                namespace=namespace,
            )
            self.core_client.delete_namespaced_service(
                name=container_name,
                namespace=namespace,
            )
        except ApiException as e:
            sm_logger.error(f"Error removing container {container_name}: {e}")
            return False
        return True

    @override
    async def exists(self, container_name: str) -> bool:
        try:
            self.app_client.read_namespaced_deployment(
                name=container_name,
                namespace=namespace,
            )
        except ApiException as e:
            if e.status == HTTPStatus.NOT_FOUND:
                return False
            sm_logger.error(f"Error checking if container {container_name} exists: {e}")
            return False
        return True

    @override
    async def create(self, server: ServersCreate, template: TemplatesCreate) -> bool:
        self.app_client.create_namespaced_deployment(
            namespace=namespace,
            body=V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata={"name": server.name, "namespace": namespace},
                spec={
                    "replicas": 0,
                    "selector": {"matchLabels": {"app": server.name}},
                    "template": {
                        "metadata": {"labels": {"app": server.name}},
                        "spec": {
                            "containers": [
                                {
                                    "name": server.name,
                                    "image": template.image,
                                    "resources": {
                                        "limits": {
                                            "cpu": str(server.cpu),
                                            "memory": f"{server.memory}Gi",
                                        },
                                        "requests": {
                                            "cpu": str(server.cpu),
                                            "memory": f"{server.memory}Gi",
                                        },
                                    },
                                    "env": [{"name": k, "value": v} for k, v in server.env.items()],
                                }
                            ]
                        },
                    },
                },
            ),
        )

        self.core_client.create_namespaced_service(
            namespace=namespace,
            body=V1Service(
                api_version="v1",
                kind="Service",
                metadata={"name": server.name, "namespace": namespace},
                spec={
                    "selector": {"app": server.name},
                    "ports": [
                        {
                            "protocol": "TCP" if True else "UDP",
                            "port": template.exposed_port[0],
                            "targetPort": template.exposed_port[0],
                        }
                    ],
                    "type": "LoadBalancer",
                },
            ),
        )

        return True

    @override
    async def is_running(self, container_name: str) -> bool:
        try:
            deployment = self.app_client.read_namespaced_deployment(
                name=container_name,
                namespace=namespace,
            )
            if not isinstance(deployment, V1Deployment):
                return False
            if deployment.status is None:
                return False
            status: V1DeploymentStatus = deployment.status

        except ApiException as e:
            sm_logger.error(f"Error checking if container {container_name} is running: {e}")
            return False
        else:
            return status.replicas == 1

    @override
    async def health_status(self, container_name: str) -> str | None:
        try:
            deployment = self.app_client.read_namespaced_deployment(name=container_name, namespace=namespace)
        except ApiException as e:
            if e.status == HTTPStatus.NOT_FOUND:
                return None
            sm_logger.error(f"Error fetching deployment {container_name} status: {e}")
            return None

        # if deployment exists but scaled to 0
        if not isinstance(deployment, V1Deployment):
            return None
        if deployment.spec and getattr(deployment.spec, "replicas", 0) == 0:
            return "stopped"

        try:
            pods = self.core_client.list_namespaced_pod(
                namespace=namespace, label_selector=f"app={container_name}"
            ).items
        except ApiException as e:
            sm_logger.error(f"Error listing pods for {container_name}: {e}")
            return None

        if not pods:
            return None

        pod_states: list[str] = []
        for pod in pods:
            phase = getattr(pod.status, "phase", None)
            # consider container readiness when running
            if phase == "Running":
                container_statuses = getattr(pod.status, "container_statuses", []) or []
                if container_statuses:
                    all_ready = all(getattr(cs, "ready", False) for cs in container_statuses)
                    pod_states.append("healthy" if all_ready else "starting")
                else:
                    pod_states.append("starting")
            elif phase in ("Pending",):
                pod_states.append("starting")
            elif phase in ("Succeeded", "Completed"):
                pod_states.append("stopped")
            else:
                pod_states.append("unhealthy")

        if all(s == "healthy" for s in pod_states):
            return "healthy"
        if any(s == "unhealthy" for s in pod_states):
            return "unhealthy"
        if any(s == "starting" for s in pod_states):
            return "starting"
        # Fallback to first observed state
        return pod_states[0] if pod_states else None

    @override
    async def command(self, container_name: str, command: str) -> bool:
        try:
            pods = self.core_client.list_namespaced_pod(
                namespace=namespace, label_selector=f"app={container_name}"
            ).items
        except ApiException as e:
            sm_logger.error(f"Error listing pods for {container_name}: {e}")
            return False

        # pick the first running pod
        target_pod = None
        for pod in pods:
            if getattr(pod.status, "phase", "") == "Running":
                target_pod = pod
                break

        if not target_pod:
            sm_logger.error(f"No running pod found for {container_name} to exec into")
            return False

        pod_name = target_pod.metadata.name
        try:
            # non-interactive exec; for attach-like behavior set tty=True and stdin=True if the client supports it
            resp = stream(
                self.core_client.connect_get_namespaced_pod_exec,
                name=pod_name,
                namespace=namespace,
                command=["/bin/sh", "-c", command],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
            sm_logger.info(f"Exec output for {container_name}@{pod_name}: {resp}")
        except ApiException as e:
            sm_logger.error(f"Error executing command on {container_name}@{pod_name}: {e}")
            return False
        except Exception as e:
            sm_logger.error(f"Unexpected error executing command on {container_name}@{pod_name}: {e}")
            return False
        return True
