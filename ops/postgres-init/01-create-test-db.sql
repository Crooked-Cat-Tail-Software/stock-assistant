-- Runs once, when the database volume is first created.
-- Integration tests wipe their tables, so they get a database of their own.
CREATE DATABASE app_test OWNER app;
