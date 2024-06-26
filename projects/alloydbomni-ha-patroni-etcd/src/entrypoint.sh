#!/bin/bash

config_file_path="/home/postgres/config/patroni.yml"

if [ ! -f "$config_file_path" ]; then
  echo "Configuration file $config_file_path does not exist, is not readable, or is not a file."
  exit 1
fi

patroni /home/postgres/config/patroni.yml
