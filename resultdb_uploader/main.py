import argparse
import json

from resultdb_uploader import atest_mobly_test_result_uploader
import resultdb_uploader.test_status as resultdb_test_status


DEV_TEST_INVESTIGATE_URL = "https://luci-milo-dev.appspot.com/ui/test-investigate/invocations/"
PROD_TEST_INVESTIGATE_URL = " https://ci.chromium.org/ui/test-investigate/invocations/"


def main():
  """
  A program that uploads test results to a specific ResultDB invocation.

  Example usage:
  python3 main.py \
      --invocation-id i123456789 \
      --test-results '{
        "ants_work_unit_id": "1234567890",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "PASS",
        "start_time": 1761721000000000000,
        "duration": 5000000000
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
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567892",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "SKIP",
        "start_time": 1761721002000000000,
        "duration": 7000000000,
        "skipped_reason": "DEMOTED"
      }' \
      --test-results '{
        "ants_work_unit_id": "1234567892",
        "module_name": "hello-world-test",
        "class_name": "HelloWorldTest",
        "method_name": "test_hello_world",
        "status": "ERROR",
        "start_time": 1761721003000000000,
        "duration": 8000000000,
        "failure_reason": "TIMEOUT",
        "summary_html": "<p><b>Error Message:</b>Time Limit Exceeded.</p>"
      }'
  """
  parser = argparse.ArgumentParser(
      description="Upload multiple test results to ResultDB."
  )
  parser.add_argument(
      "--invocation-id",
      required=True,
      help="The ID for the root invocation."
  )
  parser.add_argument(
      "--test-results",
      required=True,
      action="append",
      help="A JSON string for a single test result. Repeat this argument for each result.",
  )
  parser.add_argument(
      "--is-prod",
      required=False,
      help="Whether to use the prod ResultDB instance.",
      default=False,
      action="store_true",
  )
  args = parser.parse_args()

  uploader = atest_mobly_test_result_uploader.AtestMoblyTestResultUploader(
    is_prod=args.is_prod,
  )

  # Create a root invocation to house the test results
  uploader.create_root_invocation(ants_invocation_id=args.invocation_id)

  for test_result_json in args.test_results:
    test_result_data = json.loads(test_result_json)

    module_name = test_result_data["module_name"]
    class_name = test_result_data["class_name"]
    method_name = test_result_data["method_name"]
    start_time = test_result_data["start_time"]
    duration = test_result_data["duration"]
    status = resultdb_test_status.TestStatus[test_result_data["status"]]
    ants_work_unit_id = test_result_data["ants_work_unit_id"]
    if "failure_reason" in test_result_data:
      status_reason = {
          "failure_reason": resultdb_test_status.FailureStatusReason[
              test_result_data["failure_reason"]
          ]
      }
    elif "skipped_reason" in test_result_data:
      status_reason = {
          "skipped_reason": resultdb_test_status.SkippedStatusReason[
              test_result_data["skipped_reason"]
          ]
      }
    else:
      status_reason = resultdb_test_status.get_default_status_reason(
        test_result_data["status"]
      )

    # Create a work unit using the ID from the JSON
    uploader.create_child_work_unit(
      ants_work_unit_id=ants_work_unit_id,
      module_name=module_name,
    )

    test_result_kwargs = {}
    if "summary_html" in test_result_data:
      test_result_kwargs["summary_html"] = test_result_data["summary_html"]

    # Create the test result
    uploader.create_test_result(
      ants_work_unit_id=ants_work_unit_id,
      module_name=module_name,
      class_name=class_name,
      method_name=method_name,
      start_time_nanoseconds=start_time,
      duration_nanoseconds=duration,
      test_status=status,
      **status_reason,
      **test_result_kwargs,
    )

  # Finalize all work units
  uploader.finalize_all_work_units()

  # Finalize the root work unit
  uploader.finalize_root_work_unit()

  test_investigate_url = (
      PROD_TEST_INVESTIGATE_URL if args.is_prod else DEV_TEST_INVESTIGATE_URL
  )
  print(
      f"Test results are uploaded. You can view them at: "
      f"{test_investigate_url}{uploader.root_invocation_id}"
  )


if __name__ == "__main__":
  main()
