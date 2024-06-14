#!/bin/bash

flake8 db etl routers utils main.py && mypy -p db -p etl -p routers -p utils