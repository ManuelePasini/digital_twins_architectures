#!/bin/bash

systemctl stop docker
apt-get remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
apt install -y ./containerd.io_1.6.22-1_amd64.deb                     ./docker-ce-cli_24.0.7-1~ubuntu.22.04~jammy_amd64.deb                     ./docker-ce_24.0.7-1~ubuntu.22.04~jammy_amd64.deb                     ./docker-buildx-plugin_0.11.2-1~ubuntu.22.04~jammy_amd64.deb                     ./docker-compose-plugin_2.20.2-1~ubuntu.22.04~jammy_amd64.deb
apt-mark hold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin  
systemctl restart docker
docker -v