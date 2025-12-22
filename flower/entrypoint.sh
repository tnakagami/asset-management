#!/bin/bash

# Copy javascript file to static directory of flower
to_path=$(find /usr/local -name flower.js)
cp -f /opt/home/custom-flower.js ${to_path}

# Change execution user
su - user

# Execute command with arguments
$@