#!/usr/bin/env bash

apt-get update
apt-get install -y tesseract-ocr libgl1

pip install -r requirements.txt