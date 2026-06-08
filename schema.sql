CREATE DATABASE IF NOT EXISTS project_hub
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE project_hub;

CREATE TABLE IF NOT EXISTS projects (
  id           VARCHAR(255) PRIMARY KEY,
  title        VARCHAR(500)  NOT NULL,
  filename     VARCHAR(500),
  status       VARCHAR(50)   DEFAULT 'Idea',
  tags         JSON,
  summary      TEXT,
  word_count   INT,
  content      LONGTEXT,
  imported_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
