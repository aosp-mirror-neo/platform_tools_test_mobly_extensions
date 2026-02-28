"""A converter for Mobly result schema to Sponge schema.

Each Mobly test class maps to a Sponge testsuite and each Mobly test method maps
to a Sponge testcase. For example:

  Mobly schema:

  Test Class: HelloWorldTest
  Test Name: test_hello
  Type: Record
  Result: PASS

  Sponge schema:

  <testsuite name="HelloWorldTest" tests=1>
    <testcase name="test_hello"/>
  </testsuite>
"""

from collections.abc import Iterator, Mapping, Sequence
import dataclasses
import datetime
import enum
import glob
import logging
import os
import re
from typing import Any, Optional
# Prefer this over lxml library as lxml has issues on Mac (b/233978393).
from xml.etree import ElementTree

from mobly import records
from mobly_sponge_converter import test_component_reporter
from mobly_sponge_converter import test_components_converter
import yaml


_MOBLY_RECORD_TYPE_KEY = 'Type'

_INSPECTOR_LINK = 'inspector_link'
_INSPECTOR_SINGLE_DEVICE_TYPE = 'single'
_INSPECTOR_MULTI_DEVICE_TYPE = 'multiple'
_INSPECTOR_BASIC_URL = (
    'http://inspector.corp.google.com/moblyview;'
    + 'invocationId={{invocationId}};'
    + 'targetId={{targetId}};'
    + 'configurationId={{configurationId}};'
    + 'actionId={{actionId}};'
)

_MOBLY_TEST_SUITE_NAME = 'MoblyTest'

_TEST_INTERRUPTED_MESSAGE = 'Details: Test was interrupted manually.'

_ILLEGAL_XML_CHARS = re.compile(
    r'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]'
)

_ILLEGAL_YAML_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')


class MoblySpongeProperties(enum.Enum):
  """Sponge properties defined specifically for all Mobly tests.

  All these properties apply to the testcase level. TEST_CLASS and
  TEST_TYPE apply to both the testcase and testsuite level.
  """

  BEGIN_TIME = 'mobly_begin_time'
  END_TIME = 'mobly_end_time'
  TEST_CLASS = 'mobly_test_class'
  TEST_TYPE = 'test_type'
  UID = 'mobly_uid'
  TEST_OUTPUT = 'test_output'
  TEST_SIGNATURE = 'mobly_signature'
  SKIP_REASON = 'skip_reason'
  ERROR_MESSAGE = 'mobly_error_message'
  ERROR_TYPE = 'mobly_error_type'
  STACK_TRACE = 'mobly_stack_trace'


_MOBLY_PROPERTY_VALUES = frozenset(e.value for e in MoblySpongeProperties)


class SpongeTreeTags(enum.Enum):
  """Common tags for Sponge tree nodes."""

  TESTSUITES = 'testsuites'
  TESTSUITE = 'testsuite'
  TESTCASE = 'testcase'
  PROPERTIES = 'properties'
  PROPERTY = 'property'
  FAILURE = 'failure'
  ERROR = 'error'


class SpongeTreeAttributes(enum.Enum):
  """Common attributes for Sponge tree nodes."""

  ERRORS = 'errors'
  FAILURES = 'failures'
  TESTS = 'tests'
  CLASS_NAME = 'classname'
  RESULT = 'result'
  STATUS = 'status'
  TIME = 'time'
  TIMESTAMP = 'timestamp'
  NAME = 'name'
  VALUE = 'value'
  MESSAGE = 'message'
  RETRY_NUMBER = 'retrynumber'
  REPEAT_NUMBER = 'repeatnumber'
  ERROR_TYPE = 'type'
  # Since we modify the test name of the Sponge node to the original test name,
  # we need the reran test name to map rerun specific userdefined Sponge
  # properties to the right node.
  RERAN_TEST_NAME = 'rerantestname'


@dataclasses.dataclass
class TestSuiteSummary:
  num_tests: int
  num_errors: int
  num_failures: int


@dataclasses.dataclass
class ReranNode:
  reran_test_name: str
  original_test_name: str
  index: int
  node_type: records.TestParentType


def _create_inspector_link(
    test_type: str, test_class: str, test_case: str
) -> str:
  return (
      _INSPECTOR_BASIC_URL
      + 'testCase='
      + f'{test_class}%23{test_case}?utm_source=mobly&utm_medium={test_type}'
  )


def _find_all_elements(
    mobly_root: ElementTree.Element,
    class_name: Optional[str],
    test_name: Optional[str],
) -> Iterator[ElementTree.Element]:
  """Finds all elements in the Sponge tree with class name and/or test_name.

  If class name is absent, it will find all elements with the test name
  across all test classes. If test name is absent it will find all elements
  with class name. If both are absent, it will just return the Mobly root tree.

  Args:
    mobly_root: Root element of the Mobly test Sponge tree.
    class_name: Mobly test class name to get the elements for.
    test_name: Mobly test names to get the elements for.

  Yields:
    Iterator of elements satisfying the class_name and test_name search
    criteria.
  """
  if class_name is None and test_name is None:
    yield mobly_root
    return

  xpath = f'./{SpongeTreeTags.TESTSUITE.value}'
  if class_name is not None:
    xpath += f'[@{SpongeTreeAttributes.NAME.value}="{class_name}"]'
  if test_name is not None:
    xpath += (
        f'/{SpongeTreeTags.TESTCASE.value}'
        f'[@{SpongeTreeAttributes.RERAN_TEST_NAME.value}="{test_name}"]'
    )

  yield from mobly_root.iterfind(xpath)


def _create_or_return_properties_element(
    element: ElementTree.Element,
) -> ElementTree.Element:
  properties_element = element.find(f'./{SpongeTreeTags.PROPERTIES.value}')
  if properties_element is not None:
    return properties_element
  return ElementTree.SubElement(element, SpongeTreeTags.PROPERTIES.value)


def _add_or_update_property_element(
    properties_element: ElementTree.Element, name: str, value: str
):
  """Adds a property element or update the property value."""
  name = _ILLEGAL_XML_CHARS.sub('', name)
  value = _ILLEGAL_XML_CHARS.sub('', value)
  property_element = properties_element.find(
      f'./{SpongeTreeTags.PROPERTY.value}'
      f'[@{SpongeTreeAttributes.NAME.value}="{name}"]'
  )
  if property_element is None:
    property_element = ElementTree.SubElement(
        properties_element, SpongeTreeTags.PROPERTY.value
    )
    property_element.set(SpongeTreeAttributes.NAME.value, name)
  property_element.set(SpongeTreeAttributes.VALUE.value, value)


def _add_file_annotations(
    entry: Mapping[str, Any],
    properties_element: ElementTree.Element,
    mobly_base_directory: Optional[str],
    sponge_root_directory: Optional[str],
) -> None:
  """Adds file annotations for a Mobly test case files.

  The mobly_base_directory is used to find the files belonging to a test case.
  The files under "mobly_base_directory/test_class/test_method" belong to the
  test_class#test_method Sponge node.

  The sponge_root_directory is used to determine the
  relative path of the files to the Sponge root directory for undeclared
  outputs. The file annotation must be written for the relative path.

  Args:
    entry: Mobly summary entry for the test case.
    properties_element: Test case properties element.
    mobly_base_directory: Base directory of the Mobly test.
    sponge_root_directory: Root directory for Sponge undeclared outputs.
  """
  # If these directories are not provided, the converter will not add the
  # annotations to associate the files with the test cases.
  if (
      mobly_base_directory is None
      or sponge_root_directory is None
      or entry.get(records.TestResultEnums.RECORD_SIGNATURE, None) is None
  ):
    return

  test_class = entry[records.TestResultEnums.RECORD_CLASS]
  test_case_directory = os.path.join(
      mobly_base_directory,
      test_class,
      entry[records.TestResultEnums.RECORD_SIGNATURE],
  )

  test_case_files = glob.glob(
      os.path.join(test_case_directory, '**'), recursive=True
  )
  file_counter = 0
  for file_path in test_case_files:
    if not os.path.isfile(file_path):
      continue
    relative_path = os.path.relpath(file_path, sponge_root_directory)
    _add_or_update_property_element(
        properties_element, f'test_output{file_counter}', relative_path
    )
    file_counter += 1


def _add_inspector_property(
    properties_element: ElementTree.Element,
    entry: Mapping[str, Any],
    mobly_base_directory: Optional[str],
) -> None:
  """Adds inspector_link property to test case Sponge element.

  This function uses the number of video and logcat files to determine whether
  it is a multi-device test or single device test. The test type is set in the
  inspector link.

  Args:
    properties_element: XML element containing the properties of a Sponge test
      case.
    entry: Mobly summary entry for a single test case.
    mobly_base_directory: Base directory for the Mobly test.
  """
  if mobly_base_directory is None:
    return

  mobly_base_directory_files = glob.glob(
      os.path.join(mobly_base_directory, '*')
  )
  mobly_main_log_count = 0
  for file_path in mobly_base_directory_files:
    if not os.path.isfile(file_path):
      continue
    basename = os.path.basename(file_path)
    if basename == 'test_log.DEBUG' or basename == 'test_log.INFO':
      mobly_main_log_count += 1
  if mobly_main_log_count == 0:
    return

  test_class = entry.get(records.TestResultEnums.RECORD_CLASS, None)
  test_signature = entry.get(records.TestResultEnums.RECORD_SIGNATURE, None)
  test_case = entry.get(records.TestResultEnums.RECORD_NAME, None)
  if test_class is None or test_signature is None:
    return

  test_case_directory = os.path.join(
      mobly_base_directory,
      test_class,
      test_signature,
  )

  android_video_file_count = 0
  android_text_file_count = 0
  cros_text_file_count = 0
  cros_video_file_count = 0
  windows_text_file_count = 0
  windows_video_file_count = 0
  eiffel_text_file_count = 0
  test_case_files = glob.glob(
      os.path.join(test_case_directory, '**'), recursive=True
  )
  for file_path in test_case_files:
    if not os.path.isfile(file_path):
      continue
    basename = os.path.basename(file_path)
    if basename.startswith('video'):
      android_video_file_count += 1
    elif basename.startswith('logcat'):
      android_text_file_count += 1
    elif basename.startswith('cros_log,chrome,'):
      cros_text_file_count += 1
    elif basename.startswith('cros_video'):
      cros_video_file_count += 1
    elif basename.startswith('windows_log,'):
      windows_text_file_count += 1
    elif basename.startswith('windows_video'):
      windows_video_file_count += 1
    elif basename.startswith('eiffel_log,'):
      eiffel_text_file_count += 1

  all_text_log_file_count = (
      android_text_file_count
      + cros_text_file_count
      + windows_text_file_count
      + eiffel_text_file_count
  )
  all_video_file_count = (
      android_video_file_count
      + cros_video_file_count
      + windows_video_file_count
  )
  if all_video_file_count <= 1 and all_text_log_file_count <= 1:
    _add_or_update_property_element(
        properties_element,
        _INSPECTOR_LINK,
        _create_inspector_link(
            _INSPECTOR_SINGLE_DEVICE_TYPE, test_class, test_case
        ),
    )
  else:
    _add_or_update_property_element(
        properties_element,
        _INSPECTOR_LINK,
        _create_inspector_link(
            _INSPECTOR_MULTI_DEVICE_TYPE, test_class, test_case
        ),
    )


def _create_mobly_root_element(
    summary_record: Mapping[str, Any]
) -> ElementTree.Element:
  """Creates a Sponge XML testsuite node for a Mobly test summary."""
  full_summary = TestSuiteSummary(
      num_tests=summary_record['Requested'],
      num_errors=summary_record['Error'],
      num_failures=summary_record['Failed'],
  )
  # Create the root Sponge node to wrap the Mobly test.
  main_wrapper = ElementTree.Element(SpongeTreeTags.TESTSUITES.value)
  main_wrapper.set(SpongeTreeAttributes.NAME.value, '__main__')
  main_wrapper.set(SpongeTreeAttributes.TIME.value, '0')
  main_wrapper.set(
      SpongeTreeAttributes.ERRORS.value, str(full_summary.num_errors)
  )
  main_wrapper.set(
      SpongeTreeAttributes.FAILURES.value, str(full_summary.num_failures)
  )
  main_wrapper.set(
      SpongeTreeAttributes.TESTS.value, str(full_summary.num_tests)
  )

  mobly_test_root = ElementTree.SubElement(
      main_wrapper, SpongeTreeTags.TESTSUITE.value
  )
  mobly_test_root.set(SpongeTreeAttributes.NAME.value, _MOBLY_TEST_SUITE_NAME)
  mobly_test_root.set(SpongeTreeAttributes.TIME.value, '0')
  mobly_test_root.set(
      SpongeTreeAttributes.ERRORS.value, str(full_summary.num_errors)
  )
  mobly_test_root.set(
      SpongeTreeAttributes.FAILURES.value, str(full_summary.num_failures)
  )
  mobly_test_root.set(
      SpongeTreeAttributes.TESTS.value, str(full_summary.num_tests)
  )

  return main_wrapper


def _create_class_element(
    class_name: str, class_summary: TestSuiteSummary
) -> ElementTree.Element:
  """Creates a Sponge XML testsuite node for a Mobly test class summary.

  Args:
    class_name: Mobly test class name.
    class_summary: Mobly test class summary.

  Returns:
    A Sponge testsuite node representing one Mobly test class.
  """
  class_element = ElementTree.Element(SpongeTreeTags.TESTSUITE.value)
  class_element.set(SpongeTreeAttributes.NAME.value, class_name)
  class_element.set(SpongeTreeAttributes.TIME.value, '0')
  class_element.set(
      SpongeTreeAttributes.TESTS.value, str(class_summary.num_tests)
  )
  class_element.set(
      SpongeTreeAttributes.ERRORS.value, str(class_summary.num_errors)
  )
  class_element.set(
      SpongeTreeAttributes.FAILURES.value, str(class_summary.num_failures)
  )

  properties_element = _create_or_return_properties_element(class_element)
  _add_or_update_property_element(
      properties_element, MoblySpongeProperties.TEST_CLASS.value, class_name
  )
  _add_or_update_property_element(
      properties_element, MoblySpongeProperties.TEST_TYPE.value, 'mobly_class'
  )

  return class_element


def _set_rerun_node(
    signature: str,
    child_parent_map: Mapping[str, str],
    parent_type_map: Mapping[str, records.TestParentType],
    signature_test_name_map: Mapping[str, str],
    rerun_node_map: dict[str, ReranNode],
) -> None:
  """Sets the rerun node in the rerun node map for the current test signature.

  This function traverses the child parent map recursively until it finds the
  root test run for the rerun chain. Then it uses the original test name from
  there and builds the indices.

  Args:
    signature: Current test signature.
    child_parent_map: Map of test signature to the parent test signature.
    parent_type_map: Map of parent test signature to the parent type.
    signature_test_name_map: Map of test signature to test name.
    rerun_node_map: Map of test signature to rerun information.
  """
  if signature in rerun_node_map:
    return

  # If there is no parent, then this is the root test in the retry chain.
  if signature not in child_parent_map:
    if parent_type_map[signature] == records.TestParentType.REPEAT:
      # If repeat, remove the '_#' suffix to get the original test name.
      original_test_name = signature_test_name_map[signature].rsplit('_', 1)[0]
    else:
      original_test_name = signature_test_name_map[signature]
    rerun_node_map[signature] = ReranNode(
        signature_test_name_map[signature],
        original_test_name,
        0,
        parent_type_map[signature],
    )
    return

  parent_signature = child_parent_map[signature]
  _set_rerun_node(
      parent_signature,
      child_parent_map,
      parent_type_map,
      signature_test_name_map,
      rerun_node_map,
  )

  parent_node = rerun_node_map[parent_signature]
  rerun_node_map[signature] = ReranNode(
      signature_test_name_map[signature],
      parent_node.original_test_name,
      parent_node.index + 1,
      parent_node.node_type,
  )


def _get_reran_nodes(
    entries: list[Mapping[str, Any]]
) -> Mapping[str, ReranNode]:
  """Gets the nodes for any test case reruns.

  Args:
    entries: Summary entries for the Mobly test runs.

  Returns:
    A map of test signature to node information.
  """
  child_parent_map = {}
  parent_type_map = {}
  signature_test_name_map = {}
  for entry in entries:
    if records.TestResultEnums.RECORD_SIGNATURE not in entry:
      continue
    current_signature = entry[records.TestResultEnums.RECORD_SIGNATURE]
    signature_test_name_map[current_signature] = entry[
        records.TestResultEnums.RECORD_NAME
    ]
    # This is a dictionary with parent and type.
    rerun_parent = entry.get(records.TestResultEnums.RECORD_PARENT, None)
    if rerun_parent is not None:
      parent_signature = rerun_parent['parent']
      parent_type = (
          records.TestParentType.RETRY
          if rerun_parent['type'] == 'retry'
          else records.TestParentType.REPEAT
      )
      child_parent_map[current_signature] = parent_signature
      parent_type_map[parent_signature] = parent_type

  rerun_node_map = {}
  for signature in child_parent_map:
    # Populates the rerun node map.
    _set_rerun_node(
        signature,
        child_parent_map,
        parent_type_map,
        signature_test_name_map,
        rerun_node_map,
    )

  return rerun_node_map


def _process_record(
    entry: Mapping[str, Any],
    reran_node: Optional[ReranNode],
    mobly_base_directory: Optional[str],
    sponge_root_directory: Optional[str],
) -> ElementTree.Element:
  """Processes a single Mobly test record entry to a Sponge test case node.

  Args:
    entry: Summary of a single Mobly test case.
    reran_node: Rerun information if this test case is a rerun. Only present if
      this test is part of a rerun chain.
    mobly_base_directory: Base directory for the Mobly test. Artifacts from the
      Mobly test will be saved here.
    sponge_root_directory: Root directory for Sponge undeclared outputs.

  Returns:
    A Sponge XML node representing a single test case.
  """
  begin_time = entry[records.TestResultEnums.RECORD_BEGIN_TIME]
  end_time = entry[records.TestResultEnums.RECORD_END_TIME]
  testcase_element = ElementTree.Element(SpongeTreeTags.TESTCASE.value)
  result = entry[records.TestResultEnums.RECORD_RESULT]

  if reran_node is not None:
    if reran_node.node_type == records.TestParentType.RETRY:
      testcase_element.set(
          SpongeTreeAttributes.RETRY_NUMBER.value, str(reran_node.index)
      )
    elif reran_node.node_type == records.TestParentType.REPEAT:
      testcase_element.set(
          SpongeTreeAttributes.REPEAT_NUMBER.value, str(reran_node.index)
      )
    testcase_element.set(
        SpongeTreeAttributes.NAME.value, reran_node.original_test_name
    )
    testcase_element.set(
        SpongeTreeAttributes.RERAN_TEST_NAME.value, reran_node.reran_test_name
    )
  else:
    testcase_element.set(
        SpongeTreeAttributes.NAME.value,
        entry[records.TestResultEnums.RECORD_NAME],
    )
    testcase_element.set(
        SpongeTreeAttributes.RERAN_TEST_NAME.value,
        entry[records.TestResultEnums.RECORD_NAME],
    )
  testcase_element.set(
      SpongeTreeAttributes.CLASS_NAME.value,
      entry[records.TestResultEnums.RECORD_CLASS],
  )
  if result == records.TestResultEnums.TEST_RESULT_SKIP:
    testcase_element.set(SpongeTreeAttributes.RESULT.value, 'skipped')
    testcase_element.set(SpongeTreeAttributes.STATUS.value, 'notrun')
    testcase_element.set(SpongeTreeAttributes.TIME.value, '0')
  elif result is None:
    testcase_element.set(SpongeTreeAttributes.RESULT.value, 'completed')
    testcase_element.set(SpongeTreeAttributes.STATUS.value, 'run')
    testcase_element.set(SpongeTreeAttributes.TIME.value, '0')
    testcase_element.set(
        SpongeTreeAttributes.TIMESTAMP.value,
        datetime.datetime.fromtimestamp(
            begin_time / 1000, tz=datetime.timezone.utc
        ).strftime('%Y-%m-%dT%H:%M:%SZ'),
    )
  else:
    testcase_element.set(SpongeTreeAttributes.RESULT.value, 'completed')
    testcase_element.set(SpongeTreeAttributes.STATUS.value, 'run')
    testcase_element.set(
        SpongeTreeAttributes.TIME.value, str(end_time - begin_time)
    )
    testcase_element.set(
        SpongeTreeAttributes.TIMESTAMP.value,
        datetime.datetime.fromtimestamp(
            begin_time / 1000, tz=datetime.timezone.utc
        ).strftime('%Y-%m-%dT%H:%M:%SZ'),
    )

  # Add Mobly specific test case properties.
  properties_element = _create_or_return_properties_element(testcase_element)
  if result == records.TestResultEnums.TEST_RESULT_SKIP:
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.SKIP_REASON.value,
        f'Details: {entry[records.TestResultEnums.RECORD_DETAILS]}',
    )
  elif result is None:
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.BEGIN_TIME.value,
        str(begin_time),
    )
  else:
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.BEGIN_TIME.value,
        str(begin_time),
    )
    _add_or_update_property_element(
        properties_element, MoblySpongeProperties.END_TIME.value, str(end_time)
    )
  _add_or_update_property_element(
      properties_element,
      MoblySpongeProperties.TEST_CLASS.value,
      entry[records.TestResultEnums.RECORD_CLASS],
  )
  _add_or_update_property_element(
      properties_element, MoblySpongeProperties.TEST_TYPE.value, 'mobly_test'
  )
  # TODO(b/228270901): Remove after migration to new converter is complete.
  _add_or_update_property_element(
      properties_element, 'using_python_sponge_converter', 'true'
  )
  if entry.get(records.TestResultEnums.RECORD_SIGNATURE, None) is not None:
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.TEST_SIGNATURE.value,
        entry[records.TestResultEnums.RECORD_SIGNATURE],
    )

  _add_file_annotations(
      entry, properties_element, mobly_base_directory, sponge_root_directory
  )

  _add_inspector_property(properties_element, entry, mobly_base_directory)

  if entry[records.TestResultEnums.RECORD_UID] is not None:
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.UID.value,
        entry[records.TestResultEnums.RECORD_UID],
    )

  if result is None:
    error_element = ElementTree.SubElement(
        testcase_element, SpongeTreeTags.ERROR.value
    )
    error_element.set(
        SpongeTreeAttributes.MESSAGE.value, _TEST_INTERRUPTED_MESSAGE
    )
    error_element.text = _TEST_INTERRUPTED_MESSAGE
  elif (
      result == records.TestResultEnums.TEST_RESULT_FAIL
      or result == records.TestResultEnums.TEST_RESULT_ERROR
  ):
    error_message = f'Details: {entry[records.TestResultEnums.RECORD_DETAILS]}'
    tag = (
        SpongeTreeTags.FAILURE.value
        if result == records.TestResultEnums.TEST_RESULT_FAIL
        else SpongeTreeTags.ERROR.value
    )
    failure_or_error_element = ElementTree.SubElement(testcase_element, tag)
    failure_or_error_element.set(
        SpongeTreeAttributes.MESSAGE.value, error_message
    )
    _add_or_update_property_element(
        properties_element,
        MoblySpongeProperties.ERROR_MESSAGE.value,
        error_message,
    )

    # Add termination signal type and stack trace to the failure XML element and
    # the test case properties.
    termination_signal_type = entry[
        records.TestResultEnums.RECORD_TERMINATION_SIGNAL_TYPE
    ]
    if termination_signal_type is None:
      logging.warning(
          'Test %s has %s result without a termination signal type.',
          entry[records.TestResultEnums.RECORD_NAME],
          result,
      )
    else:
      failure_or_error_element.set(
          SpongeTreeAttributes.ERROR_TYPE.value, termination_signal_type
      )
      _add_or_update_property_element(
          properties_element,
          MoblySpongeProperties.ERROR_TYPE.value,
          termination_signal_type,
      )
    stack_trace = entry[records.TestResultEnums.RECORD_STACKTRACE]
    if stack_trace is None:
      logging.warning(
          'Test %s has %s result without a stack trace.',
          entry[records.TestResultEnums.RECORD_NAME],
          result,
      )
    else:
      failure_or_error_element.text = stack_trace
      _add_or_update_property_element(
          properties_element,
          MoblySpongeProperties.STACK_TRACE.value,
          stack_trace,
      )

  extra_errors = entry[records.TestResultEnums.RECORD_EXTRA_ERRORS]
  if extra_errors is not None:
    for _, error_details in extra_errors.items():
      extra_error_element = ElementTree.SubElement(
          testcase_element, SpongeTreeTags.ERROR.value
      )
      error_position = error_details[records.TestResultEnums.RECORD_POSITION]
      extra_error_element.set(
          SpongeTreeAttributes.MESSAGE.value,
          f'Error occurred at {error_position}.\n'
          f'Details: {error_details[records.TestResultEnums.RECORD_DETAILS]}',
      )
      stack_trace = error_details[records.TestResultEnums.RECORD_STACKTRACE]
      if stack_trace is not None:
        extra_error_element.text = stack_trace
  return testcase_element


def _write_test_components(
    summary_entries: Sequence[Any],
    sponge_root_directory: str,
    mobly_base_directory: Optional[str] = None,
    test_components_output_directory: Optional[str] = None,
):
  """Writes out test components for Mobly controller info records."""
  test_components = test_components_converter.convert(
      summary_entries, sponge_root_directory, mobly_base_directory
  )
  reporters = {}
  for component in test_components:
    try:
      if component.name not in reporters:
        reporters[component.name] = (
            test_component_reporter.TestComponentReporter(
                test_components_output_directory
            )
        )
        reporters[component.name].write(component)
      else:
        reporters[component.name].append(component)
    except ValueError:
      logging.exception('Failed to write test component %s.', component.name)


def convert(
    mobly_results_path: str,
    mobly_base_directory: Optional[str] = None,
    sponge_root_directory: Optional[str] = None,
    test_components_output_directory: Optional[str] = None,
) -> ElementTree.ElementTree:
  """Converts a Mobly results summary file to Sponge XML schema.

  The mobly_base_directory and sponge_root_directory will be used to compute the
  file links for each Sponge tree element. If these are absent then the file
  links will be omitted.

  Args:
    mobly_results_path: Path to the Mobly summary YAML file.
    mobly_base_directory: Base directory of the Mobly test.
    sponge_root_directory: Root directory for Sponge undeclared outputs.

  Returns:
    A Sponge XML tree for the Mobly test.
  """
  logging.info('Generating Sponge tree.')

  with open(mobly_results_path, 'r', encoding='utf-8') as f:
    summary_entries = list(
        yaml.safe_load_all(_ILLEGAL_YAML_CHARS.sub('', f.read()))
    )

  _write_test_components(
      summary_entries,
      sponge_root_directory,
      mobly_base_directory,
      test_components_output_directory,
  )

  summary_record = next(
      entry
      for entry in summary_entries
      if entry[_MOBLY_RECORD_TYPE_KEY]
      == records.TestSummaryEntryType.SUMMARY.value
  )

  main_root = _create_mobly_root_element(summary_record)

  mobly_test_root = main_root[0]
  mobly_root_properties = _create_or_return_properties_element(mobly_test_root)
  # See go/utp-test-traces#adding-custom-traces-via-sponge-testdiagnostics
  _add_or_update_property_element(
      mobly_root_properties, '_contains_utp_test_traces', 'true'
  )
  # Add files under the Mobly root directory to the Mobly test suite node.
  if mobly_base_directory is not None and sponge_root_directory is not None:
    file_counter = 0
    for filename in os.listdir(mobly_base_directory):
      file_path = os.path.join(mobly_base_directory, filename)
      if not os.path.isfile(file_path):
        continue
      relative_path = os.path.relpath(file_path, sponge_root_directory)
      _add_or_update_property_element(
          mobly_root_properties, f'test_output{file_counter}', relative_path
      )
      file_counter += 1

  test_case_entries = [
      entry
      for entry in summary_entries
      if entry[_MOBLY_RECORD_TYPE_KEY]
      == records.TestSummaryEntryType.RECORD.value
  ]
  # Populate the class summaries.
  class_summaries = {}
  for entry in test_case_entries:
    class_name = entry[records.TestResultEnums.RECORD_CLASS]

    if class_name not in class_summaries:
      class_summaries[class_name] = TestSuiteSummary(
          num_tests=0, num_errors=0, num_failures=0
      )

    class_summaries[class_name].num_tests += 1
    if (
        entry[records.TestResultEnums.RECORD_RESULT]
        == records.TestResultEnums.TEST_RESULT_ERROR
    ):
      class_summaries[class_name].num_errors += 1
    elif (
        entry[records.TestResultEnums.RECORD_RESULT]
        == records.TestResultEnums.TEST_RESULT_FAIL
    ):
      class_summaries[class_name].num_failures += 1

  # Create class nodes.
  class_elements = {}
  for class_name, summary in class_summaries.items():
    class_elements[class_name] = _create_class_element(class_name, summary)
    mobly_test_root.append(class_elements[class_name])

  # Append test case nodes to test class nodes.
  reran_nodes = _get_reran_nodes(test_case_entries)
  for entry in test_case_entries:
    class_name = entry[records.TestResultEnums.RECORD_CLASS]
    if (
        records.TestResultEnums.RECORD_SIGNATURE in entry
        and entry[records.TestResultEnums.RECORD_SIGNATURE] in reran_nodes
    ):
      reran_node = reran_nodes[entry[records.TestResultEnums.RECORD_SIGNATURE]]
    else:
      reran_node = None
    class_elements[class_name].append(
        _process_record(
            entry, reran_node, mobly_base_directory, sponge_root_directory
        )
    )

  user_data_entries = [
      entry
      for entry in summary_entries
      if entry[_MOBLY_RECORD_TYPE_KEY]
      == records.TestSummaryEntryType.USER_DATA.value
  ]

  for user_data_entry in user_data_entries:
    class_name = user_data_entry.get(records.TestResultEnums.RECORD_CLASS, None)
    test_name = user_data_entry.get(records.TestResultEnums.RECORD_NAME, None)

    # Key-value pairs under "sponge_properties" or "properties" are written to
    # the corresponding Sponge node.
    sponge_properties = user_data_entry.get('sponge_properties', None)
    if not isinstance(sponge_properties, dict):
      sponge_properties = user_data_entry.get('properties', None)
      if not isinstance(sponge_properties, dict):
        continue
    for element in _find_all_elements(mobly_test_root, class_name, test_name):
      properties_element = _create_or_return_properties_element(element)
      for name, value in sponge_properties.items():
        if name in _MOBLY_PROPERTY_VALUES:
          # Do not override Mobly properties.
          continue
        _add_or_update_property_element(
            properties_element, str(name), str(value)
        )

  return ElementTree.ElementTree(main_root)
