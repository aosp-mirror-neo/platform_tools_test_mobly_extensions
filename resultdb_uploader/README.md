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
      --test-results '{
        "ants_work_unit_id": "1234567890",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "PASS",
        "start_time": 1761721000,
        "duration": 5
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567891",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "FAIL",
        "start_time": 1761721001,
        "duration": 6
      }'
```
Note: You need to use an unique invocation id each time.

Alternatively, you can use the executable in **dist/main**.
```
dist/main \
      --invocation-id i123456789 \
      --test-results '{
        "ants_work_unit_id": "1234567890",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "PASS",
        "start_time": 1761721000,
        "duration": 5
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567891",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "FAIL",
        "start_time": 1761721001,
        "duration": 6
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
This example highlights how to create your own upload workflow using this library.
```
import dataclasses
from typing import Any, Dict, List
import uuid

import resultdb_test_status
import test_result_uploader


@dataclasses.dataclass
class TestResultInfo:
  """A class to hold information about a set of test results."""

  module_name: str
  class_name: str
  method_name: str
  test_statuses: List[resultdb_test_status.TestStatus]
  test_status_reasons: List[Dict[str, Any]]
  start_times_seconds: List[int]
  duration_seconds: List[int]


def upload_test_results(
    test_info: TestResultInfo,
):
  """Uploads a set of test results to ResultDB."""
  for (
      test_status,
      test_status_reason,
      start_time_seconds,
      duration_seconds,
  ) in zip(
      test_info.test_statuses,
      test_info.test_status_reasons,
      test_info.start_times_seconds,
      test_info.duration_seconds,
  ):
    # create_child_work_unit
    uploader.create_child_work_unit(
        str(uuid.uuid4()),
        module_name=test_info.module_name,
    )
    # create_test_result
    uploader.create_test_result(
        module_name=test_info.module_name,
        class_name=test_info.class_name,
        method_name=test_info.method_name,
        start_time_seconds=start_time_seconds,
        duration_seconds=duration_seconds,
        test_status=test_status,
        **test_status_reason,
    )


if __name__ == "__main__":
  UI_MESSAGE = (
      "Test results are uploaded. You can view them at: "
      "https://luci-milo-dev.appspot.com/ui/test-investigate/invocations/"
      "{root_invocation_id}"
  )

  test_set_1 = TestResultInfo(
      module_name="hello-world-test",
      class_name="HelloWorldTest",
      method_name="test_hello_world",
      test_statuses=[
          resultdb_test_status.TestStatus.PASS,
          resultdb_test_status.TestStatus.FAIL,
          resultdb_test_status.TestStatus.SKIP,
          resultdb_test_status.TestStatus.FAIL,
      ],
      test_status_reasons=[
          {},
          {"failure_reason": resultdb_test_status.FailureStatusReason.ORDINARY},
          {"skipped_reason": resultdb_test_status.SkippedStatusReason.DEMOTED},
          {"failure_reason": resultdb_test_status.FailureStatusReason.CRASH},
      ],
      start_times_seconds=[1761714921, 1761714922, 1761714923, 1761714924],
      duration_seconds=[5, 6, 4, 5],
  )

  test_set_2 = TestResultInfo(
      module_name="another-hello-world-test",
      class_name="AnotherHelloWorldTest",
      method_name="test_another_hello_world",
      test_statuses=[
          resultdb_test_status.TestStatus.PASS,
          resultdb_test_status.TestStatus.PASS,
      ],
      test_status_reasons=[{}, {}],
      start_times_seconds=[1761714925, 1761714926],
      duration_seconds=[7, 8],
  )

  uploader = test_result_uploader.TestResultUploader()
  # create_root_invocation
  uploader.create_root_invocation(ants_invocation_id=str(uuid.uuid4()))

  upload_test_results(test_set_1)
  upload_test_results(test_set_2)

  print(UI_MESSAGE.format(root_invocation_id=uploader.root_invocation_id))
```
