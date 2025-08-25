#!/bin/bash

wget https://download.oracle.com/java/21/latest/jdk-21_linux-x64_bin.deb &
apt install ./jdk-21_linux-x64_bin.deb &

mkdir -p /asterix_cc &

curl -O https://downloads.apache.org/asterixdb/asterixdb-0.9.9/asterix-server-0.9.9-binary-assembly.zip &
apt install unzip
unzip asterix-server-0.9.9-binary-assembly.zip &&
  rm asterix-server-0.9.9-binary-assembly.zip

sudo apt install openjdk-21-jdk -y
sudo update-alternatives --config java