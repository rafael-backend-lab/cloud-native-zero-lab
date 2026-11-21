#!/bin/sh
set -eu
psql --username postgres --dbname lab --set ON_ERROR_STOP=1 --set pw="$APP_PASSWORD" <<'SQL'
CREATE ROLE lab_api LOGIN PASSWORD :'pw';
CREATE TABLE teste_iphone (id serial PRIMARY KEY, mensagem text NOT NULL);
GRANT SELECT, INSERT ON teste_iphone TO lab_api;
GRANT USAGE ON SEQUENCE teste_iphone_id_seq TO lab_api;
SQL
