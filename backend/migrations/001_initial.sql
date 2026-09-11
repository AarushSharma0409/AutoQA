-- Version 1 PostgreSQL schema reference; app.db applies this model schema transactionally.

CREATE TABLE events (
	id SERIAL NOT NULL, 
	task_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	payload JSON NOT NULL, 
	created FLOAT NOT NULL, 
	PRIMARY KEY (id)
)

;
CREATE INDEX ix_events_task_id ON events (task_id);

CREATE TABLE files (
	id VARCHAR(36) NOT NULL, 
	task_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	mime VARCHAR(120) NOT NULL, 
	size INTEGER NOT NULL, 
	storage_key VARCHAR(200) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	created FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (storage_key)
)

;
CREATE INDEX ix_files_task_id ON files (task_id);

CREATE TABLE tasks (
	id VARCHAR(36) NOT NULL, 
	owner VARCHAR(200) NOT NULL, 
	goal TEXT NOT NULL, 
	mode VARCHAR(12) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created FLOAT NOT NULL, 
	updated FLOAT NOT NULL, 
	lease VARCHAR(36), 
	lease_until FLOAT NOT NULL, 
	checkpoint JSON NOT NULL, 
	error TEXT, 
	PRIMARY KEY (id)
)

;
CREATE INDEX ix_tasks_status ON tasks (status);
CREATE INDEX ix_tasks_owner ON tasks (owner);
