import os
import sys

from colorama import Fore
from fastapi import FastAPI
from fastapi.routing import APIRoute

from server_manager.webservice.logger import sm_logger


def startup_info():
    sm_logger.log_group(
        "Starting server-manager webservice",
        [
            f"Python version: {sys.version.split()[0]}",
            f"OS: {os.name}, Platform: {os.uname().sysname}",
            f"Process ID: {os.getpid()}",
            f"Log Level: {os.environ.get('SM_LOG_LEVEL', 'INFO')} (SM_LOG_LEVEL)",
            f"Log Path: {os.environ.get('SM_LOG_PATH', 'stdout')} (SM_LOG_PATH)",
            f"Environment: {os.environ.get('SM_ENV', 'PROD')} (SM_ENV)",
            f"Port Range: {os.environ.get('SM_PORT_START', '30000')}-{os.environ.get('SM_PORT_END', '30100')} (SM_PORT_START and SM_PORT_END)",
            f"Kubernetes: {'Enabled' if os.environ.get('SM_K8S') == '1' else 'Disabled'} (SM_K8S)",
            f"URL: {Fore.BLUE}{'https' if os.environ.get('SM_ENV') != 'DEV' else 'http'}://{os.environ.get('SM_API_BACKEND', 'localhost')}{Fore.RESET} (SM_API_BACKEND)",
        ],
    )
    if os.environ.get("SM_ENV") == "DEV":
        sm_logger.warning("Running in DEV mode, this is not recommended for production use.")
    check_mount_path()


def check_mount_path():
    mount_path = os.environ.get("SM_MOUNT_PATH", "/mnt/server_manager")
    if not os.path.exists(mount_path):
        os.makedirs(mount_path, exist_ok=True)

    if not os.access(mount_path, os.W_OK):
        sm_logger.error(f"Mount path {mount_path} is not writable. Please check permissions.")
        sys.exit(1)
    sm_logger.info(f"Mount path {mount_path} is valid and writable.")


def generate_operation_id(app: FastAPI):
    """Generate a unique operation ID"""

    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name
