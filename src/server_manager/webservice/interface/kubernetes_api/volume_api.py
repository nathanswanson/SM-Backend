import base64
import io
import os
import stat
import tarfile
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from typing import Any, override

from fabric import Connection
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from paramiko import SFTPClient

from server_manager.webservice.interface.interface import ControllerVolumeInterface, DirList
from server_manager.webservice.logger import sm_logger

# Default namespace for game servers crds
DEFAULT_NAMESPACE = "game-servers"

# Custom Resource Definition details for GameServer
CRD_GROUP = "server-manager.io"
CRD_VERSION = "v1alpha1"
CRD_PLURAL = "gameservers"


# Chunk size for streaming file operations
CHUNK_SIZE = 64 * 1024  # 64KB


class KubernetesVolumeAPI(ControllerVolumeInterface):
    """Kubernetes volume management using SFTP to access pod filesystems.

    This implementation connects to game server pods via SFTP to perform
    file operations. It requires:
    1. An SFTP sidecar container in the game server pods
    2. SSH keys configured for authentication
    3. The pod's service IP exposed via the GameServer CRD status
    """

    def __init__(self):
        """Initialize the Kubernetes client configuration."""
        try:
            # Try in-cluster config first (when running inside a pod)
            config.load_incluster_config()
            sm_logger.info("Loaded in-cluster Kubernetes configuration for VolumeAPI")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig (local development)
                config.load_kube_config()
                sm_logger.info("Loaded kubeconfig Kubernetes configuration for VolumeAPI")
            except config.ConfigException as e:
                sm_logger.error(f"Failed to load Kubernetes configuration: {e}")
                raise

    def _get_custom_objects_api(self) -> client.CustomObjectsApi:
        """Get the CustomObjectsApi client for CRD operations."""
        return client.CustomObjectsApi()

    def _get_core_api(self) -> client.CoreV1Api:
        """Get the CoreV1Api client for pod operations."""
        return client.CoreV1Api()

    @contextmanager
    def _get_sftp_connection(self, host: str, user: str, password: str, port: int) -> Generator[SFTPClient, None, None]:
        """Create an SFTP connection to the specified host.

        Args:
            host: The host IP or hostname to connect to

        Yields:
            An SFTPClient instance

        Raises:
            ConnectionError: If unable to establish SFTP connection
        """
        connect_kwargs: dict[str, Any] = {}
        connect_kwargs["password"] = password
        try:
            conn = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs=connect_kwargs,
            )
            sftp = conn.sftp()
            try:
                yield sftp
            finally:
                sftp.close()
                conn.close()
        except Exception as e:
            sm_logger.error(f"Failed to establish SFTP connection to {host}: {e}")
            msg = f"SFTP connection failed: {e}"
            raise ConnectionError(msg) from e

    async def _get_host(self, deployment_name: str, namespace: str) -> str | None:
        """Get the host IP for SFTP connection.

        Tries service IP first, falls back to pod IP.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace

        Returns:
            The host IP if available, None otherwise
        """
        core_api = self._get_core_api()
        service_name = f"{deployment_name}-svc"
        try:
            service = core_api.read_namespaced_service(name=service_name, namespace=namespace)
            cluster_ip = service.spec.cluster_ip
            if cluster_ip and cluster_ip != "None":
                return cluster_ip
        except ApiException as e:
            sm_logger.error(f"Failed to get service {service_name} in namespace {namespace}: {e}")
        return None

    async def _get_port(self, deployment_name: str, namespace: str) -> int | None:
        """Get the port for SFTP connection from the service.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
        Returns:
            The port if available, None otherwise
        """
        core_api = self._get_core_api()
        service_name = f"{deployment_name}-svc"
        try:
            service = core_api.read_namespaced_service(name=service_name, namespace=namespace)
            ports = service.spec.ports or []
            for port in ports:
                if port.name == "sftp":
                    return port.port
        except ApiException as e:
            sm_logger.error(f"Failed to get service {service_name} in namespace {namespace}: {e}")
        return None

    def _get_password_from_secret(self, server_name: str, namespace: str) -> str:
        """Retrieve the SFTP password from Kubernetes secret.

        Args:
            namespace: Kubernetes namespace

        """
        core_api = self._get_core_api()
        secret_name = f"{server_name}-sftp-secret"
        try:
            secret = core_api.read_namespaced_secret(name=secret_name, namespace=namespace)
            password_b64 = secret.data.get("password")
            if not password_b64:
                msg = "Password not found in secret"
                raise ValueError(msg)
            return base64.b64decode(password_b64).decode("utf-8")
        except ApiException as e:
            sm_logger.error(f"Failed to retrieve secret {secret_name} in namespace {namespace}: {e}")
            raise

    @override
    async def list_directory(self, deployment_name: str, namespace: str, path: str, username: str) -> DirList | None:
        """List files and directories at the specified path.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to list

        Returns:
            Tuple of (directories, files) or None if failed
        """
        host = await self._get_host(deployment_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {deployment_name}")
            return None

        try:
            password = self._get_password_from_secret(deployment_name, namespace)
            port = await self._get_port(deployment_name, namespace)
            with self._get_sftp_connection(host, user=username, password=password, port=port) as sftp:
                entries = sftp.listdir_attr(path)

                directories: list[str] = []
                files: list[str] = []

                for entry in entries:
                    entry_mode = entry.st_mode or 0
                    if stat.S_ISDIR(entry_mode):
                        directories.append(entry.filename + "/")
                    else:
                        files.append(entry.filename)

                return (directories, files)
        except FileNotFoundError:
            sm_logger.warning(f"Directory not found: {path} on {deployment_name}")
            return None
        except Exception as e:
            sm_logger.error(f"Failed to list directory {path} on {deployment_name}: {e}")
            return None

    @override
    async def read_file(self, deployment_name: str, namespace: str, path: str, username: str) -> AsyncGenerator:
        """Read a file from the game server and stream its contents.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to the file to read

        Yields:
            File contents in chunks
        """

        async def _generator() -> AsyncGenerator:
            host = await self._get_host(deployment_name, namespace)
            if not host:
                sm_logger.error(f"No host available for {deployment_name}")
                return

            try:
                password = self._get_password_from_secret(deployment_name, namespace)
                port = await self._get_port(deployment_name, namespace)
                with (
                    self._get_sftp_connection(host, user=username, password=password, port=port) as sftp,
                    sftp.open(path, "rb") as remote_file,
                ):
                    yield remote_file.stat().st_size.to_bytes(8, "big")  # Send file size first
                    while True:
                        chunk = remote_file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            except FileNotFoundError:
                sm_logger.warning(f"File not found: {path} on {deployment_name}")
            except Exception as e:
                sm_logger.error(f"Failed to read file {path} on {deployment_name}: {e}")

        return _generator()

    @override
    async def read_archive(self, deployment_name: str, namespace: str, path: str, username: str) -> AsyncGenerator:
        """Read a directory as a tar archive and stream its contents.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to the directory to archive

        Yields:
            Tar archive contents in chunks
        """

        async def _generator() -> AsyncGenerator:
            host = await self._get_host(deployment_name, namespace)
            if not host:
                sm_logger.error(f"No host available for {deployment_name}")
                return

            try:
                password = self._get_password_from_secret(deployment_name, namespace)
                port = await self._get_port(deployment_name, namespace)
                with self._get_sftp_connection(host, user=username, password=password, port=port) as sftp:
                    # Create an in-memory tar archive
                    buffer = io.BytesIO()

                    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
                        await self._add_to_tar_recursive(sftp, tar, path, os.path.basename(path))

                    # Seek to beginning and stream the contents
                    buffer.seek(0)
                    while True:
                        chunk = buffer.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            except FileNotFoundError:
                sm_logger.warning(f"Path not found: {path} on {deployment_name}")
            except Exception as e:
                sm_logger.error(f"Failed to create archive of {path} on {deployment_name}: {e}")

        return _generator()

    async def _add_to_tar_recursive(
        self, sftp: SFTPClient, tar: tarfile.TarFile, remote_path: str, arcname: str
    ) -> None:
        """Recursively add files and directories to a tar archive.

        Args:
            sftp: SFTP client connection
            tar: TarFile to add entries to
            remote_path: Path on remote server
            arcname: Name in the archive
        """
        try:
            file_stat = sftp.stat(remote_path)
            mode = file_stat.st_mode or 0

            if stat.S_ISDIR(mode):
                # Add directory entry
                tarinfo = tarfile.TarInfo(name=arcname)
                tarinfo.type = tarfile.DIRTYPE
                tarinfo.mode = mode
                tarinfo.mtime = file_stat.st_mtime or 0
                tar.addfile(tarinfo)

                # Recursively add contents
                for entry in sftp.listdir(remote_path):
                    entry_path = f"{remote_path}/{entry}"
                    entry_arcname = f"{arcname}/{entry}"
                    await self._add_to_tar_recursive(sftp, tar, entry_path, entry_arcname)
            else:
                # Add file entry
                tarinfo = tarfile.TarInfo(name=arcname)
                tarinfo.size = file_stat.st_size or 0
                tarinfo.mode = mode
                tarinfo.mtime = file_stat.st_mtime or 0

                with sftp.open(remote_path, "rb") as f:
                    tar.addfile(tarinfo, f)
        except Exception as e:
            sm_logger.warning(f"Failed to add {remote_path} to archive: {e}")

    @override
    async def write_file(self, deployment_name: str, namespace: str, path: str, data: bytes, username: str) -> bool:
        """Write data to a file on the game server.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to write the file to
            data: File contents as bytes

        Returns:
            True if successful, False otherwise
        """
        host = await self._get_host(deployment_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {deployment_name}")
            return False

        try:
            password = self._get_password_from_secret(deployment_name, namespace)
            port = await self._get_port(deployment_name, namespace)
            with self._get_sftp_connection(host, user=username, password=password, port=port) as sftp:
                # Ensure parent directory exists
                parent_dir = os.path.dirname(path)
                if parent_dir:
                    try:
                        sftp.stat(parent_dir)
                    except FileNotFoundError:
                        # Create parent directories recursively
                        self._mkdir_p(sftp, parent_dir)

                # Write the file
                with sftp.open(path, "wb") as remote_file:
                    remote_file.write(data)

                sm_logger.info(f"Wrote {len(data)} bytes to {path} on {deployment_name}")
                return True
        except Exception as e:
            sm_logger.error(f"Failed to write file {path} on {deployment_name}: {e}")
            return False

    def _mkdir_p(self, sftp: SFTPClient, remote_path: str) -> None:
        """Create directory and all parent directories (like mkdir -p).

        Args:
            sftp: SFTP client connection
            remote_path: Path to create
        """
        if remote_path in ("", "/"):
            return

        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            # Parent doesn't exist, create it first
            parent = os.path.dirname(remote_path)
            if parent:
                self._mkdir_p(sftp, parent)
            sftp.mkdir(remote_path)

    @override
    async def delete_file(self, deployment_name: str, namespace: str, path: str, username: str) -> bool:
        """Delete a file or directory on the game server.

        Args:
            deployment_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to delete

        Returns:
            True if successful, False otherwise
        """
        host = await self._get_host(deployment_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {deployment_name}")
            return False

        try:
            password = self._get_password_from_secret(deployment_name, namespace)
            port = await self._get_port(deployment_name, namespace)
            with self._get_sftp_connection(host, user=username, password=password, port=port) as sftp:
                file_stat = sftp.stat(path)
                mode = file_stat.st_mode or 0

                if stat.S_ISDIR(mode):
                    # Recursively delete directory contents
                    await self._rmdir_recursive(sftp, path)
                else:
                    sftp.remove(path)

                sm_logger.info(f"Deleted {path} on {deployment_name}")
                return True
        except FileNotFoundError:
            sm_logger.warning(f"Path not found for deletion: {path} on {deployment_name}")
            return True  # Already deleted
        except Exception as e:
            sm_logger.error(f"Failed to delete {path} on {deployment_name}: {e}")
            return False

    async def _rmdir_recursive(self, sftp: SFTPClient, path: str) -> None:
        """Recursively delete a directory and its contents.

        Args:
            sftp: SFTP client connection
            path: Path to delete
        """
        for entry in sftp.listdir_attr(path):
            entry_path = f"{path}/{entry.filename}"
            entry_mode = entry.st_mode or 0
            if stat.S_ISDIR(entry_mode):
                await self._rmdir_recursive(sftp, entry_path)
            else:
                sftp.remove(entry_path)
        sftp.rmdir(path)
