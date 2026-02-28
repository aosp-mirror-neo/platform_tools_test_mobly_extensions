"""Class to write convert Mobly devices to Sponge test components.

This class uses the device information from the Mobly test_summary.yaml
Controller Info record and generates a test_component_pb2.TestComponent for
each device.
"""

from collections.abc import Sequence
import logging
import os
import platform
import re
from typing import Any, Optional

from mobly import records

from protos import test_component_pb2

_MOBLY_RECORD_TYPE_KEY = 'Type'


def _squash_properties(properties: dict[str, Any],
                       key_prefix: Optional[str]) -> dict[str, str]:
  squashed_dict = {}
  for key, value in properties.items():
    next_prefix = f'{key_prefix}.{key}' if key_prefix else key
    if isinstance(value, dict):
      squashed_dict.update(_squash_properties(value, next_prefix))
    else:
      squashed_dict[next_prefix] = str(value)
  return squashed_dict


def _files_for_component(name: str, sponge_root_directory: str) -> list[str]:
  component_files = []
  for dir_name, _, files in os.walk(sponge_root_directory):
    for file in files:
      dir_match = name in dir_name
      file_match = name.replace(':', '-') in file
      if not dir_match and not file_match:
        continue
      relative_path = dir_name[len(sponge_root_directory) + 1 :]
      component_files.append(os.path.join(relative_path, file))
  return component_files


def _get_first_available_value(
    controller_info: dict[str, Any],
    candidate_keys: Sequence[str],
    default: str) -> str:
  """Returns the controller_info value corresponding to the first available key.

  Args:
    controller_info: Mobly controller info.
    candidate_keys: Sequence of keys to look for value candidates.
    default: Value to return if none of the keys are present in controller_info.
  """
  for key in candidate_keys:
    if key in controller_info:
      return controller_info[key]
  return default


def _create_controller_test_components(
    controller_info_record: dict[str, Any],
    sponge_root_directory: str,
    seen_properties=dict[str, set[tuple[str, str]]],
) -> list[test_component_pb2.TestComponent]:
  """Parses Mobly controller infos into test components.

  Args:
    controller_info_record: Controller info record read from the test summary.
    sponge_root_directory: The root directory for undeclared outputs.
    seen_properties: Controller properties that have already been recorded.

  Returns:
    A list of test components for each device in the controller info record.
  """
  if not isinstance(controller_info_record['Controller Info'], list):
    return []
  controller_name = controller_info_record['Controller Name']
  test_components = []
  controller_infos = controller_info_record['Controller Info']
  for controller_index, controller_info in enumerate(controller_infos):
    test_component_display_name = f'{controller_name}_{controller_index + 1}'
    test_component_type = controller_name
    test_component_properties = None

    if isinstance(controller_info, dict):
      test_component_display_name = _get_first_available_value(
          controller_info,
          candidate_keys=['serial', 'name'],
          default=test_component_display_name)
      test_component_type = _get_first_available_value(
          controller_info,
          candidate_keys=['device_type'],
          default=test_component_type)
      test_component_properties = []
      for key, value in _squash_properties(controller_info, None).items():
        if (
            test_component_display_name in seen_properties
            and (key, value) in seen_properties[test_component_display_name]
        ):
          continue
        if test_component_display_name not in seen_properties:
          seen_properties[test_component_display_name] = set()
        seen_properties[test_component_display_name].add((key, value))
        test_component_properties.append(
            test_component_pb2.TestComponentProperty(key=key, value=value)
        )

    logging.debug(
        'Creating test component for device: %s', test_component_display_name)

    test_components.append(
        test_component_pb2.TestComponent(
            # Replace invalid characters in the test component name with '_'.
            name=re.sub('[:./]', '_', test_component_display_name),
            display_name=test_component_display_name,
            type=test_component_type,
            properties=test_component_properties,
            relative_file_paths=_files_for_component(
                test_component_display_name,
                sponge_root_directory,
            ),
        )
    )

  return test_components


def _get_host_component(
    sponge_root_directory: str,
    mobly_base_directory: Optional[str],
) -> test_component_pb2.TestComponent:
  """Creates a test component for the host machine."""
  properties = [
      test_component_pb2.TestComponentProperty(
          key='system', value=platform.system()
      ),
      test_component_pb2.TestComponentProperty(
          key='release', value=platform.release()
      ),
      test_component_pb2.TestComponentProperty(
          key='version', value=platform.version()
      ),
  ]

  if mobly_base_directory is not None:
    file_paths = [
        os.path.join(mobly_base_directory, file)[
            len(sponge_root_directory) + 1 :
        ]
        for file in os.listdir(mobly_base_directory)
        if os.path.isfile(os.path.join(mobly_base_directory, file))
    ]
  else:
    file_paths = []

  host_component = test_component_pb2.TestComponent(
      name=re.sub('[:.]', '_', platform.node()),
      display_name=platform.node(),
      type='MoblyHost',
      properties=properties,
      relative_file_paths=file_paths,
  )
  return host_component


def convert(
    summary_entries: Sequence[Any],
    sponge_root_directory: str,
    mobly_base_directory: Optional[str],
) -> list[test_component_pb2.TestComponent]:
  """Converts a Mobly Controller Info records to test components.

  Args:
    summary_entries: Mobly summary entries read from the test_summary.yaml.
    sponge_root_directory: The root directory for undeclared outputs.
    mobly_base_directory: The base directory for Mobly artifacts.

  Returns:
    A list of test components for each device used in the Mobly test.
  """
  controller_infos = [
      entry for entry in summary_entries if entry[_MOBLY_RECORD_TYPE_KEY] ==
      records.TestSummaryEntryType.CONTROLLER_INFO.value
  ]

  test_components = []
  seen_properties = {}
  for controller_info_record in controller_infos:
    test_components.extend(
        _create_controller_test_components(
            controller_info_record, sponge_root_directory, seen_properties
        )
    )
  test_components.append(
      _get_host_component(sponge_root_directory, mobly_base_directory)
  )
  return test_components
