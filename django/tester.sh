#!/bin/bash

# Change directory
cd /opt/app
# Execute py-test
pytest
# Create coverage with markdown format
coverage report --format=markdown > htmlcov/report.md
