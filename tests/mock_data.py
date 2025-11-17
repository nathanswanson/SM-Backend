from server_manager.webservice.routes.search_api import ServerFileListResponse

TEST_USER = {"username": "testuser", "scopes": [""], "hashed_password": "hashed", "admin": False}
TEST_NODE = {
    "name": "test-node",
    "cpus": 1,
    "memory": 1024,
    "disk": 2,
    "cpu_name": "Test CPU",
    "arch": "x86_64",
    "max_hz": 3000,
}
TEST_TEMPLATE = {
    "name": "test-template",
    "tags": ["latest", "table"],
    "exposed_port": [27015],
    "description": "A test template",
    "image": "test-image",
    "resource_min_cpu": 1,
    "resource_min_mem": 1024,
    "resource_min_disk": 2,
    "modules": [],
}
TEST_SERVER = {
    "name": "test-server",
    "tags": ["latest"],
    "cpu": 1,
    "disk": 2,
    "memory": 3,
    "container_name": "test-container",
    "node_id": 1,
    "template_id": 1,
    "env": {"TEST": "value"},
}
TEST_SERVER_READ = TEST_SERVER | {"id": 1, "port": [30001]}
TEST_USER_READ = TEST_USER | {"id": 1}
TEST_NODE_READ = TEST_NODE | {"id": 1}
TEST_TEMPLATE_READ = TEST_TEMPLATE | {"id": 1}

MOCK_FILE_DATA: ServerFileListResponse = ServerFileListResponse(
    items=["file1.txt", "file2.txt", "folder1/", "folder2/"]
)
