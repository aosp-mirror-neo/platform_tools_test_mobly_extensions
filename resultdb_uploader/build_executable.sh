#!/bin/bash
executable_name="resultdb_uploader"
source ~/venvs/resultdb_uploader_venv/bin/activate
pyinstaller -F --name $executable_name --distpath prebuilt main.py
rm -rf build
rm $executable_name.spec
