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
