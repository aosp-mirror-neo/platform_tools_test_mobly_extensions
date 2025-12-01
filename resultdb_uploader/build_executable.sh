#!/bin/bash
executable_name="resultdb_uploader"
source ~/venvs/resultdb_uploader_venv/bin/activate
if pyinstaller -F --name $executable_name --distpath prebuilt main.py; then
  echo "Build successful"
  rm -rf build
  rm $executable_name.spec
fi
