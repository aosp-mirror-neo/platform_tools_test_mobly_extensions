<!-- This is a g3doc page. -->
# Introduction
This Python library provides some methods for uploading test results to ResultDB.

# User
## Virtualenv Setup
```
croot
python -m venv ~/venvs/resultdb_uploader_venv
source ~/venvs/resultdb_uploader_venv/bin/activate
pip install -r tools/test/mobly_extensions/resultdb_uploader/requirements.txt
```

## Example Usage
```
python3 main.py \
      --invocation-id i123456789 \
      --output-url \
      --test-results '{
        "ants_work_unit_id": "1234567890",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "PASS",
        "start_time": 1761721000000000000,
        "duration": 5000000000,
        "artifact_paths": [
          "tests/testdata/test_log.DEBUG",
          "tests/testdata/test_log.INFO",
          "tests/testdata/test_summary.yaml"
        ]
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567891",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "FAIL",
        "start_time": 1761721001000000000,
        "duration": 6000000000,
        "summary_html": "<p><b>Error Message:</b> Incorrect Value. Expected 1 but got 0.</p>"
      }'
```
Note: You need to use an unique invocation id each time.

Alternatively, you can use the executable in **prebuilt/resultdb_uploader**.
```
prebuilt/resultdb_uploader \
      --invocation-id i123456789 \
      --output-url \
      --test-results '{
        "ants_work_unit_id": "1234567890",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "PASS",
        "start_time": 1761721000000000000,
        "duration": 5000000000,
        "artifact_paths": [
          "tests/testdata/test_log.DEBUG",
          "tests/testdata/test_log.INFO",
          "tests/testdata/test_summary.yaml"
        ]
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567891",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "FAIL",
        "start_time": 1761721001000000000,
        "duration": 6000000000,
        "summary_html": "<p><b>Error Message:</b> Incorrect Value. Expected 1 but got 0.</p>"
      }'
```

# Developer
## Copybara Workflow
This step is for updating ResultDB gRPC protos definition.
```
croot
cd tools/test/mobly_extensions/resultdb_uploader
copybara copy.bara.sky resultdb --folder-dir .
```

## Building Protos
This step is for building necessary protos into Python classes.
```
croot
source ~/venvs/resultdb_uploader_venv/bin/activate
python3 -m grpc_tools.protoc --proto_path=. --proto_path=external/googleapis --proto_path=external/protobuf/src --python_out=./tools/test/mobly_extensions/resultdb_uploader --grpc_python_out=./tools/test/mobly_extensions/resultdb_uploader tools/test/mobly_extensions/resultdb_uploader/proto/resultdb/*.proto google/api/field_behavior.proto google/protobuf/timestamp.proto google/protobuf/duration.proto
```

## Building Executable
This step is for updating the executable after making source code changes.
```
croot
cd tools/test/mobly_extensions/resultdb_uploader
source ~/venvs/resultdb_uploader_venv/bin/activate
pyinstaller -F --name resultdb_uploader --distpath prebuilt main.py
rm -rf build
rm resultdb_uploader.spec
```

## Example Library Usage
See ```main.py```
