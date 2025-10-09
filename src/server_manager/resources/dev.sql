BEGIN TRANSACTION;

DELETE FROM templates;
DELETE FROM nodes;
DELETE FROM users WHERE id != 1; -- Keep admin user with id 1
DELETE FROM servers;
DELETE FROM serveruserlink;

INSERT INTO templates (name, image, tags, default_env, user_env, resource_min_cpu, resource_min_disk, resource_min_mem) VALUES
('minecraft_java', 'itzg/minecraft-server:latest', '["survival","vanilla"]', '{"EULA":"TRUE"}', '{"MOTD":"Welcome to dev server"}', 1, 2, 1024),
('factorio', 'factoriotools/factorio:latest', '["factory","co-op"]', '{}', '{}', 1, 1, 512);

INSERT INTO nodes (id, name, cpus, disk, memory, cpu_name, max_hz, arch) VALUES
(1, 'node-1', 4, 100, 8192, 'Intel(R) Xeon(R) CPU', 3400000, 'x86_64'),
(2, 'node-2', 8, 500, 32768, 'AMD EPYC', 3600000, 'x86_64');


INSERT INTO users (id, username, disabled, admin, hashed_password) VALUES
(2, 'alice', 0, 0, '$2b$12$examplehashaliceaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
(3, 'bob', 0, 1, '$2b$12$examplehashbobbbbbbbbbbbbbbbbbbbbbbbbbbb');

-- Assuming 'minecraft_java' has id 1, 'factorio' has id 2
INSERT INTO servers (id, name, container_name, template_id, env, cpu, disk, memory, port, node_id) VALUES
(1, 'mc-server-1', 'mc-server-1', 1, '{"LEVEL_NAME":"world","MAX_PLAYERS":"10"}', 2, 10, 2048, '{"25565": 25565}', 1),
(2, 'factorio-1', 'itzg/factorio', 2, NULL, 1, 5, 1024, '{"34197": 34197}', 2);

INSERT INTO serveruserlink (server_id, user_id) VALUES
(1, 1),
(1, 2),
(2, 3);

COMMIT;