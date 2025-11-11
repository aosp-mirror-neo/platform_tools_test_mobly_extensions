import enum
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import failure_reason_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import skipped_reason_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import test_result_pb2


class TestStatus(enum.Enum):
  PASS = test_result_pb2.TestResult.Status.PASSED
  FAIL = test_result_pb2.TestResult.Status.FAILED
  SKIP = test_result_pb2.TestResult.Status.SKIPPED
  ERROR = test_result_pb2.TestResult.Status.FAILED


class FailureStatusReason(enum.Enum):
  ORDINARY = failure_reason_pb2.FailureReason.Kind.ORDINARY
  CRASH = failure_reason_pb2.FailureReason.Kind.CRASH
  TIMEOUT = failure_reason_pb2.FailureReason.Kind.TIMEOUT


class SkippedStatusReason(enum.Enum):
  DEMOTED = skipped_reason_pb2.SkippedReason.Kind.DEMOTED


def get_default_status_reason(
    status_str: str,
) -> dict[str, FailureStatusReason | SkippedStatusReason]:
  if status_str == "FAIL":
    return {"failure_reason": FailureStatusReason.ORDINARY}
  elif status_str == "SKIP":
    return {"skipped_reason": SkippedStatusReason.DEMOTED}
  elif status_str == "ERROR":
    return {"failure_reason": FailureStatusReason.CRASH}
  return {}
