from typing import Any, cast, override

from kubernetes import client
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models import V1Deployment
from kubernetes.stream import stream

from server_manager.webservice.db_models import ServersCreate, TemplatesCreate
from server_manager.webservice.interface.interface import ControllerContainerInterface
from server_manager.webservice.logger import sm_logger

# Default namespace for game servers
DEFAULT_NAMESPACE = "game-servers"

# Custom Resource Definition details for GameServer
CRD_GROUP = "server-manager.io"
CRD_VERSION = "v1alpha1"
CRD_PLURAL = "gameservers"

# HTTP status codes
HTTP_NOT_FOUND = 404


class KubernetesContainerAPI(ControllerContainerInterface):
    """Kubernetes-based container management using Custom Resource Definitions (GameServer CRD)."""

    def _get_custom_objects_api(self) -> client.CustomObjectsApi:
        """Get the CustomObjectsApi client for CRD operations."""
        return client.CustomObjectsApi()

    def _get_core_api(self) -> client.CoreV1Api:
        """Get the CoreV1Api client for pod operations."""
        return client.CoreV1Api()

    def _get_apps_api(self) -> client.AppsV1Api:
        """Get the AppsV1Api client for deployment operations."""
        return client.AppsV1Api()

    @override
    async def start(self, container_name: str, namespace: str) -> bool:
        """Start a game server by setting running=true on the GameServer CRD or scaling deployment to 1."""
        try:
            # Try CRD approach first
            custom_api = self._get_custom_objects_api()
            body = {"spec": {"running": True}}
            custom_api.patch_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
                body=body,
            )
            return True
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to deployment-based approach
                try:
                    apps_api = self._get_apps_api()
                    body = {"spec": {"replicas": 1}}
                    apps_api.patch_namespaced_deployment_scale(
                        namespace=namespace or DEFAULT_NAMESPACE,
                        name=container_name,
                        body=body,
                    )
                    return True
                except ApiException as deploy_err:
                    sm_logger.error(f"Failed to start deployment {container_name}: {deploy_err}")
                    return False
            sm_logger.error(f"Failed to start GameServer {container_name}: {e}")
            return False

    @override
    async def stop(self, container_name: str, namespace: str) -> bool:
        """Stop a game server by setting running=false on the GameServer CRD or scaling deployment to 0."""
        try:
            # Try CRD approach first
            custom_api = self._get_custom_objects_api()
            body = {"spec": {"running": False}}
            custom_api.patch_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
                body=body,
            )
            return True
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to deployment-based approach
                try:
                    apps_api = self._get_apps_api()
                    body = {"spec": {"replicas": 0}}
                    apps_api.patch_namespaced_deployment_scale(
                        namespace=namespace or DEFAULT_NAMESPACE,
                        name=container_name,
                        body=body,
                    )
                    return True
                except ApiException as deploy_err:
                    sm_logger.error(f"Failed to stop deployment {container_name}: {deploy_err}")
                    return False
            sm_logger.error(f"Failed to stop GameServer {container_name}: {e}")
            return False

    @override
    async def remove(self, container_name: str, namespace: str) -> bool:
        """Remove a game server by deleting the GameServer CRD or deployment."""
        try:
            # Try CRD approach first
            custom_api = self._get_custom_objects_api()
            custom_api.delete_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
            )
            return True
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to deployment-based approach
                try:
                    apps_api = self._get_apps_api()
                    apps_api.delete_namespaced_deployment(
                        name=container_name,
                        namespace=namespace or DEFAULT_NAMESPACE,
                    )
                    return True
                except ApiException as deploy_err:
                    sm_logger.error(f"Failed to remove deployment {container_name}: {deploy_err}")
                    return False
            sm_logger.error(f"Failed to remove GameServer {container_name}: {e}")
            return False

    @override
    async def exists(self, container_name: str, namespace: str) -> bool:
        """Check if a game server exists (either as GameServer CRD or deployment)."""
        try:
            # Try CRD approach first
            custom_api = self._get_custom_objects_api()
            custom_api.get_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
            )
            return True
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to deployment-based approach
                try:
                    apps_api = self._get_apps_api()
                    apps_api.read_namespaced_deployment(
                        name=container_name,
                        namespace=namespace or DEFAULT_NAMESPACE,
                    )
                    return True
                except ApiException:
                    return False
            return False

    # apiVersion: apiextensions.k8s.io/v1
    # kind: CustomResourceDefinition
    # metadata:
    #   name: gameservers.server-manager.io
    # spec:
    #   group: server-manager.io
    #   versions:
    #     - name: v1alpha1
    #       served: true
    #       storage: true
    #       schema:
    #         openAPIV3Schema:
    #           type: object
    #           required:
    #             - spec
    #           properties:
    #             spec:
    #               type: object
    #               required:
    #                 - templateImage
    #                 - templateName
    #                 - tenantId
    #                 - tenantName
    #               properties:
    #                 running:
    #                   type: boolean
    #                   description: Whether the game server should be running

    #                 containerName:
    #                   type: string
    #                   description: Name of the container within the pod
    #                 templateImage:
    #                   type: string
    #                   description: Docker image for the game server
    #                 templateName:
    #                   type: string
    #                   description: Name of the server template
    #                 nodeName:
    #                   type: string
    #                   description: Node selector for scheduling
    #                 tenantId:
    #                   type: integer
    #                   description: ID of the tenant/user owning this server
    #                 tenantName:
    #                   type: string
    #                   description: Name of the tenant/user
    #                 env:
    #                   type: object
    #                   additionalProperties:
    #                     type: string
    #                   description: Environment variables for the server
    #                 cpu:
    #                   type: integer
    #                   description: CPU cores allocation
    #                   minimum: 1
    #                   maximum: 4
    #                 memory:
    #                   type: integer
    #                   description: Memory allocation in GB
    #                   minimum: 1
    #                   maximum: 4
    #                 disk:
    #                   type: integer
    #                   description: Disk allocation in GB
    #                   minimum: 1
    #                   maximum: 500
    #                   default: 10
    #                 ports:
    #                   type: array
    #                   items:
    #                     type: integer
    #                   description: Ports to expose
    #                 templateVolumes:
    #                   type: array
    #                   items:
    #                     type: string
    #                   description: Volume mount paths from template
    #                 templatePorts:
    #                   type: array
    #                   items:
    #                     type: integer
    #                   description: Ports from template
    #             status:
    #               type: object
    #               properties:
    #                 phase:
    #                   type: string
    #                   enum:
    #                     - Pending
    #                     - Creating
    #                     - Running
    #                     - Failed
    #                     - Terminating
    #                   description: Current phase of the game server
    #                 message:
    #                   type: string
    #                   description: Human-readable status message
    #                 deploymentReady:
    #                   type: boolean
    #                   description: Whether the deployment is ready
    #                 serviceIP:
    #                   type: string
    #                   description: External IP of the LoadBalancer service
    #                 lastReconciled:
    #                   type: string
    #                   format: date-time
    #                   description: Last time the resource was reconciled
    #                 configHash:
    #                   type: string
    #                   description: Hash of the current configuration
    #       subresources:
    #         status: {}
    #       additionalPrinterColumns:
    #         - name: Tenant
    #           type: string
    #           jsonPath: .spec.tenantName
    #         - name: Template
    #           type: string
    #           jsonPath: .spec.templateName
    #         - name: Phase
    #           type: string
    #           jsonPath: .status.phase
    #         - name: IP
    #           type: string
    #           jsonPath: .status.serviceIP
    #         - name: Age
    #           type: date
    #           jsonPath: .metadata.creationTimestamp
    #   scope: Namespaced
    #   names:
    #     plural: gameservers
    #     singular: gameserver
    #     kind: GameServer
    #     shortNames:
    #       - gs

    @override
    async def create(self, server: ServersCreate, template: TemplatesCreate) -> bool:
        """Create a new GameServer custom resource from server and template configuration."""
        try:
            custom_api = self._get_custom_objects_api()

            # Build the GameServer custom resource
            gameserver_manifest: dict[str, Any] = {
                "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
                "kind": "GameServer",
                "metadata": {
                    "name": server.container_name or server.name.lower().replace(" ", "-"),
                    "namespace": DEFAULT_NAMESPACE,
                    "labels": {
                        "app.kubernetes.io/name": server.name,
                        "app.kubernetes.io/managed-by": "server-manager",
                    },
                },
                "spec": {
                    "running": False,  # Start in stopped state
                    "containerName": server.container_name or server.name.lower().replace(" ", "-"),
                    "templateImage": template.image,
                    "templateName": template.name,
                    "nodeName": str(server.node_id) if server.node_id else None,
                    "tenantId": server.node_id,  # Using node_id as tenant association
                    "tenantName": server.name,
                    "env": server.env or {},
                    "cpu": server.cpu or template.resource_min_cpu or 1,
                    "memory": server.memory or template.resource_min_mem or 1,
                    "disk": server.disk or template.resource_min_disk or 10,
                    "ports": template.exposed_port or [],
                    "templateVolumes": template.exposed_volume or [],
                    "templatePorts": template.exposed_port or [],
                },
            }

            # Add tags as annotations if present
            if server.tags:
                gameserver_manifest["metadata"]["annotations"] = {"server-manager.io/tags": ",".join(server.tags)}

            custom_api.create_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                body=gameserver_manifest,
            )
            sm_logger.info(f"Created GameServer {server.container_name or server.name}")
            return True
        except ApiException as e:
            sm_logger.error(f"Failed to create GameServer {server.name}: {e}")
            return False

    @override
    async def is_running(self, container_name: str, namespace: str) -> bool:
        """Check if the game server is currently running."""
        try:
            # Try CRD approach first - check status.phase
            custom_api = self._get_custom_objects_api()
            gameserver = custom_api.get_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
            )
            gameserver_dict = cast(dict[str, Any], gameserver)
            status = gameserver_dict.get("status", {})
            phase = status.get("phase", "")
            return phase == "Running"
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to deployment-based approach
                try:
                    apps_api = self._get_apps_api()
                    deployment = cast(
                        V1Deployment,
                        apps_api.read_namespaced_deployment(
                            name=container_name,
                            namespace=namespace or DEFAULT_NAMESPACE,
                        ),
                    )
                    # Check if deployment has available replicas
                    if deployment.status:
                        return (deployment.status.available_replicas or 0) > 0
                    return False
                except ApiException:
                    return False
            return False

    @override
    async def health_status(self, container_name: str, namespace: str) -> str | None:
        """Get the health status of a game server."""
        try:
            # Try CRD approach first
            custom_api = self._get_custom_objects_api()
            gameserver = custom_api.get_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace or DEFAULT_NAMESPACE,
                plural=CRD_PLURAL,
                name=container_name,
            )
            gameserver_dict = cast(dict[str, Any], gameserver)
            status = gameserver_dict.get("status", {})
            phase = status.get("phase", "Unknown")
            message = status.get("message", "")
            return f"{phase}: {message}" if message else phase
        except ApiException as e:
            if e.status == HTTP_NOT_FOUND:
                # Fall back to checking pod health
                return await self._get_pod_health_status(container_name, namespace)
            return None

    async def _get_pod_health_status(self, container_name: str, namespace: str) -> str | None:
        """Get health status from pod conditions."""
        try:
            core_api = self._get_core_api()
            # Find pods with the matching label
            pods = core_api.list_namespaced_pod(
                namespace=namespace or DEFAULT_NAMESPACE,
                label_selector=f"app={container_name}",
            )
            if not pods.items:
                return "No pods found"

            pod = pods.items[0]
            conditions = pod.status.conditions or []

            # Check container statuses for health
            container_statuses = pod.status.container_statuses or []
            for cs in container_statuses:
                if cs.state.running:
                    if cs.ready:
                        return "Healthy"
                    return "Running but not ready"
                if cs.state.waiting:
                    return f"Waiting: {cs.state.waiting.reason}"
                if cs.state.terminated:
                    return f"Terminated: {cs.state.terminated.reason}"

            # Fall back to pod conditions
            for condition in conditions:
                if condition.type == "Ready":
                    return "Ready" if condition.status == "True" else f"Not Ready: {condition.reason}"

            return "Unknown"
        except ApiException as e:
            sm_logger.error(f"Failed to get pod health status for {container_name}: {e}")
            return None

    @override
    async def command(self, container_name: str, command: str, namespace: str) -> bool:
        """Execute a command inside the game server container."""
        try:
            core_api = self._get_core_api()

            # Find the pod associated with this game server
            pods = core_api.list_namespaced_pod(
                namespace=namespace or DEFAULT_NAMESPACE,
                label_selector=f"app={container_name}",
            )

            if not pods.items:
                sm_logger.error(f"No pods found for game server {container_name}")
                return False

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Execute command in the pod
            exec_command = ["/bin/sh", "-c", command]

            # Use kubernetes stream to execute the command
            resp = stream(
                core_api.connect_get_namespaced_pod_exec,
                pod_name,
                namespace or DEFAULT_NAMESPACE,
                command=exec_command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )

            sm_logger.debug(f"Command output for {container_name}: {resp}")
            return True
        except ApiException as e:
            sm_logger.error(f"Failed to execute command on {container_name}: {e}")
            return False
        except Exception as e:
            sm_logger.error(f"Unexpected error executing command on {container_name}: {e}")
            return False
