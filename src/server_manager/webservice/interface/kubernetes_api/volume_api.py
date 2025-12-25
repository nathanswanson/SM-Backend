import io
import os
import stat
import tarfile
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from typing import Any, cast, override

from fabric import Connection
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from paramiko import SFTPClient

from server_manager.webservice.interface.interface import ControllerVolumeInterface, DirList
from server_manager.webservice.logger import sm_logger

# Default namespace for game servers
DEFAULT_NAMESPACE = "game-servers"

# Custom Resource Definition details for GameServer
CRD_GROUP = "server-manager.io"
CRD_VERSION = "v1alpha1"
CRD_PLURAL = "gameservers"

# SFTP configuration
SFTP_PORT = 22
SFTP_USER = os.environ.get("SM_SFTP_USER", "gameserver")
SFTP_KEY_PATH = os.environ.get("SM_SFTP_KEY_PATH", "/app/secrets/sftp_key")

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

    async def _get_service_ip(self, container_name: str, namespace: str) -> str | None:
        """Get the service IP for a game server from its CRD status.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace

        Returns:
            The service IP if available, None otherwise
        """
        try:
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
            return status.get("serviceIP")
        except ApiException as e:
            sm_logger.error(f"Failed to get service IP for {container_name}: {e}")
            return None

    async def _get_pod_ip(self, container_name: str, namespace: str) -> str | None:
        """Fallback: Get pod IP directly if service IP is not available.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace

        Returns:
            The pod IP if available, None otherwise
        """
        try:
            core_api = self._get_core_api()
            pods = core_api.list_namespaced_pod(
                namespace=namespace or DEFAULT_NAMESPACE,
                label_selector=f"app={container_name}",
            )
            if pods.items:
                return pods.items[0].status.pod_ip
            return None
        except ApiException as e:
            sm_logger.error(f"Failed to get pod IP for {container_name}: {e}")
            return None

    @contextmanager
    def _get_sftp_connection(self, host: str) -> Generator[SFTPClient, None, None]:
        """Create an SFTP connection to the specified host.

        Args:
            host: The host IP or hostname to connect to

        Yields:
            An SFTPClient instance

        Raises:
            ConnectionError: If unable to establish SFTP connection
        """
        connect_kwargs: dict[str, Any] = {}

        # Use key-based authentication if key file exists
        if os.path.exists(SFTP_KEY_PATH):
            connect_kwargs["key_filename"] = SFTP_KEY_PATH
        else:
            # Fall back to password from environment (for development)
            password = os.environ.get("SM_SFTP_PASSWORD")
            if password:
                connect_kwargs["password"] = password

        try:
            conn = Connection(
                host=host,
                user=SFTP_USER,
                port=SFTP_PORT,
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

    async def _get_host(self, container_name: str, namespace: str) -> str | None:
        """Get the host IP for SFTP connection.

        Tries service IP first, falls back to pod IP.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace

        Returns:
            The host IP if available, None otherwise
        """
        host = await self._get_service_ip(container_name, namespace)
        if not host:
            host = await self._get_pod_ip(container_name, namespace)
        return host

    @override
    async def list_directory(self, container_name: str, namespace: str, path: str) -> DirList | None:
        """List files and directories at the specified path.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to list

        Returns:
            Tuple of (directories, files) or None if failed
        """
        host = await self._get_host(container_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {container_name}")
            return None

        try:
            with self._get_sftp_connection(host) as sftp:
                entries = sftp.listdir_attr(path)

                directories: list[str] = []
                files: list[str] = []

                for entry in entries:
                    entry_mode = entry.st_mode or 0
                    if stat.S_ISDIR(entry_mode):
                        directories.append(entry.filename)
                    else:
                        files.append(entry.filename)

                return (directories, files)
        except FileNotFoundError:
            sm_logger.warning(f"Directory not found: {path} on {container_name}")
            return None
        except Exception as e:
            sm_logger.error(f"Failed to list directory {path} on {container_name}: {e}")
            return None

    @override
    async def read_file(self, container_name: str, namespace: str, path: str) -> AsyncGenerator:
        """Read a file from the game server and stream its contents.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to the file to read

        Yields:
            File contents in chunks
        """

        async def _generator() -> AsyncGenerator:
            host = await self._get_host(container_name, namespace)
            if not host:
                sm_logger.error(f"No host available for {container_name}")
                return

            try:
                with self._get_sftp_connection(host) as sftp, sftp.open(path, "rb") as remote_file:
                    while True:
                        chunk = remote_file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            except FileNotFoundError:
                sm_logger.warning(f"File not found: {path} on {container_name}")
            except Exception as e:
                sm_logger.error(f"Failed to read file {path} on {container_name}: {e}")

        return _generator()

    @override
    async def read_archive(self, container_name: str, namespace: str, path: str) -> AsyncGenerator:
        """Read a directory as a tar archive and stream its contents.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to the directory to archive

        Yields:
            Tar archive contents in chunks
        """

        async def _generator() -> AsyncGenerator:
            host = await self._get_host(container_name, namespace)
            if not host:
                sm_logger.error(f"No host available for {container_name}")
                return

            try:
                with self._get_sftp_connection(host) as sftp:
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
                sm_logger.warning(f"Path not found: {path} on {container_name}")
            except Exception as e:
                sm_logger.error(f"Failed to create archive of {path} on {container_name}: {e}")

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
    async def write_file(self, container_name: str, namespace: str, path: str, data: bytes) -> bool:
        """Write data to a file on the game server.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to write the file to
            data: File contents as bytes

        Returns:
            True if successful, False otherwise
        """
        host = await self._get_host(container_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {container_name}")
            return False

        try:
            with self._get_sftp_connection(host) as sftp:
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

                sm_logger.info(f"Wrote {len(data)} bytes to {path} on {container_name}")
                return True
        except Exception as e:
            sm_logger.error(f"Failed to write file {path} on {container_name}: {e}")
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
    async def delete_file(self, container_name: str, namespace: str, path: str) -> bool:
        """Delete a file or directory on the game server.

        Args:
            container_name: Name of the game server
            namespace: Kubernetes namespace
            path: Path to delete

        Returns:
            True if successful, False otherwise
        """
        host = await self._get_host(container_name, namespace)
        if not host:
            sm_logger.error(f"No host available for {container_name}")
            return False

        try:
            with self._get_sftp_connection(host) as sftp:
                file_stat = sftp.stat(path)
                mode = file_stat.st_mode or 0

                if stat.S_ISDIR(mode):
                    # Recursively delete directory contents
                    await self._rmdir_recursive(sftp, path)
                else:
                    sftp.remove(path)

                sm_logger.info(f"Deleted {path} on {container_name}")
                return True
        except FileNotFoundError:
            sm_logger.warning(f"Path not found for deletion: {path} on {container_name}")
            return True  # Already deleted
        except Exception as e:
            sm_logger.error(f"Failed to delete {path} on {container_name}: {e}")
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
