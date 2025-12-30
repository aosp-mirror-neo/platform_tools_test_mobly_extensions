import importlib.resources
import json
import logging
import os
import stat
import subprocess
from typing import Any

RESULTDB_MODULE_NAME = "resultdb_uploader"
RESULTDB_EXECUTABLE_NAME = "resultdb_uploader"


def set_execute_permissions(executable_path: str) -> None:
  """Set execute permissions on the extracted file."""
  current_mode = os.stat(executable_path).st_mode
  new_mode = current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
  if current_mode != new_mode:
    os.chmod(executable_path, new_mode)


def get_upload_command(
  executable_path: str,
  ants_invocation_id: str,
  test_results: list[dict[str, Any]],
  is_prod: bool,
) -> list[str]:
  """Get the command to upload test results to ResultDB."""
  command = [
      executable_path, "--invocation-id", ants_invocation_id
  ]
  if is_prod:
    command.append("--is-prod")
  for test_result in test_results:
    command.append("--test-result")
    command.append(json.dumps(test_result))
  return command


def enabled() -> bool:
  """Checks if the ResultDB uploader executable is available."""
  resource_ref = (
    importlib.resources.files(RESULTDB_MODULE_NAME)
    / RESULTDB_EXECUTABLE_NAME
  )
  return resource_ref.is_file()


def upload(
  ants_invocation_id: str,
  test_results: list[dict[str, Any]],
  base_log_path: str | None = None,
  is_prod: bool = False,
) -> bool:
  """This function is a wrapper for the 'resultdb_uploader' executable."""
  try:
    # Get a reference to the resource within the 'resultdb_uploader' package.
    resource_ref = (
      importlib.resources.files(RESULTDB_MODULE_NAME)
      / RESULTDB_EXECUTABLE_NAME
    )

    # importlib.resources.as_file() provides a context manager.
    # It ensures the resource is available as a file on the filesystem,
    # extracting it to a temporary location if necessary.
    with importlib.resources.as_file(resource_ref) as executable_path:
      # Set execute permissions on the extracted file
      try:
        set_execute_permissions(executable_path)
      except OSError as e:
        logging.error(
          "Could not set execute permissions on %s: %s",
          executable_path,
          e,
        )
        return False

      run_kwargs = {}
      if base_log_path:
        run_kwargs["cwd"] = base_log_path

      # Run the executable with the upload command.
      result = subprocess.run(
          get_upload_command(
              str(executable_path),
              ants_invocation_id,
              test_results,
              is_prod,
          ),
          check=True,
          capture_output=True,
          text=True,
          **run_kwargs,
      )
      if result.stdout:
        print(result.stdout)
      if result.stderr:
        logging.error("ResultDB uploader stderr: %s", result.stderr)
  except subprocess.CalledProcessError as e:
    if e.stdout:
      print(e.stdout)
    if e.stderr:
      logging.error("ResultDB uploader stderr: %s", e.stderr)
    return False
  except Exception as e:
    logging.error("An unexpected error occurred: %s", e)
    return False
  return True
