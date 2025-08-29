import io
import os
import tarfile

import docker
import docker.errors


def upload_file_to_container(container_name: str, file_path: str, target_path: str) -> bool:
    client = docker.from_env()
    # take file(s) from <file_path> put them into
    files = os.listdir(file_path) if os.path.isdir(file_path) else [file_path]

    tarstream = io.BytesIO()
    with tarfile.open(fileobj=tarstream, mode="w|") as tar:
        for file in files:
            tar.add(file)
    tarstream.seek(0)
    try:
        return client.containers.get(container_name).put_archive(target_path, tarstream)
    except docker.errors.APIError:
        return False
