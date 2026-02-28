import os
import pathlib
import tempfile
import unittest
from unittest import mock
from xml.etree import ElementTree

from absl import logging
from mobly_sponge_converter import mobly_sponge_converter
from mobly_sponge_converter import test_component_reporter
from mobly_sponge_converter import test_components_converter
from protos import test_component_pb2


_TESTDATA_DIRECTORY = 'tests/testdata'

_PASS_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'passed_test_summary.yaml'
)
_FAIL_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'failed_test_summary.yaml'
)
_FAIL_WITHOUT_DETAILS_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'failed_without_details_test_summary.yaml'
)
_ERROR_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'error_test_summary.yaml'
)
_EXTRA_ERRORS_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'extra_errors_test_summary.yaml'
)
_SKIP_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'skipped_test_summary.yaml'
)
_RETRY_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'retry_test_summary.yaml'
)
_REPEAT_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'repeat_test_summary.yaml'
)
_INTERRUPTED_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'interrupted_test_summary.yaml'
)
_USER_PROPERTIES_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'user_properties_test_summary.yaml'
)
_INVALID_YAML_SUMMARY_FILE = os.path.join(
    _TESTDATA_DIRECTORY, 'invalid_yaml_char_test_summary.yaml'
)


class MoblySpongeConverterTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    patcher = mock.patch.object(
        test_components_converter, 'convert', autospec=True
    )
    self.mock_components_convert = patcher.start()
    self.addCleanup(patcher.stop)

  def test_adds_trace_tab_property_to_root(self):
    sponge_xml = mobly_sponge_converter.convert(_PASS_SUMMARY_FILE)
    mobly_root = sponge_xml.getroot()[0]
    properties = mobly_root.find('./properties')
    self._assert_has_property(properties, '_contains_utp_test_traces', 'true')

  def test_convert_passed_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_PASS_SUMMARY_FILE)

    main_root = sponge_xml.getroot()
    with self.subTest('_creates_main_root'):
      self.assertEqual(
          main_root.tag, mobly_sponge_converter.SpongeTreeTags.TESTSUITES.value
      )
      attributes = main_root.attrib
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.NAME.value],
          '__main__',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.TIME.value],
          '0',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value],
          '0',
      )
      self.assertEqual(
          attributes[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '0',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.TESTS.value],
          '3',
      )

    mobly_test_element = main_root[0]
    with self.subTest('_creates_mobly_root_element'):
      self.assertEqual(
          mobly_test_element.tag,
          mobly_sponge_converter.SpongeTreeTags.TESTSUITE.value,
      )
      attributes = mobly_test_element.attrib
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.NAME.value],
          'MoblyTest',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.TIME.value],
          '0',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value],
          '0',
      )
      self.assertEqual(
          attributes[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '0',
      )
      self.assertEqual(
          attributes[mobly_sponge_converter.SpongeTreeAttributes.TESTS.value],
          '3',
      )

    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    with self.subTest('_creates_testsuite_element'):
      test_class_attrs = test_class.attrib
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TIME.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TESTS.value
          ],
          '1',
      )

    with self.subTest('_adds_testsuite_mobly_sponge_properties'):
      test_class_props = test_class.find('./properties')
      self._assert_has_property(
          test_class_props, 'mobly_test_class', 'HelloWorldTest'
      )
      self._assert_has_property(test_class_props, 'test_type', 'mobly_class')

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    with self.subTest('_creates_testcase_element'):
      test_hello_attrs = test_hello.attrib
      self.assertEqual(
          test_hello_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.NAME.value
          ],
          'test_hello',
      )
      self.assertEqual(
          test_hello_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.CLASS_NAME.value
          ],
          'HelloWorldTest',
      )
      self.assertEqual(
          test_hello_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TIME.value
          ],
          '11',
      )
      self.assertEqual(
          test_hello_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TIMESTAMP.value
          ],
          '2017-01-26T02:06:31Z',
      )

    with self.subTest('_adds_testcase_mobly_sponge_properties'):
      test_hello_props = test_hello.find('./properties')
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.BEGIN_TIME.value,
          '1485396391375',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.END_TIME.value,
          '1485396391386',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.TEST_CLASS.value,
          'HelloWorldTest',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.TEST_TYPE.value,
          'mobly_test',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.UID.value,
          'bar',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.TEST_SIGNATURE.value,
          'test_hello-1485396391375',
      )
      self._assert_has_property(
          test_hello_props, 'using_python_sponge_converter', 'true'
      )

  def test_convert_failed_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_FAIL_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    with self.subTest('_creates_testsuite_element'):
      test_class_attrs = test_class.attrib
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '1',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TESTS.value
          ],
          '1',
      )

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    failure_element = test_hello.find('./failure')
    self.assertIsNotNone(failure_element)
    failure_element_attributes = failure_element.attrib
    with self.subTest('_adds_failure_message'):
      self.assertEqual(
          failure_element_attributes[
              mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
          ],
          'Details: Test failure message',
      )
      self.assertEqual(str(failure_element.text), 'Line 1\\nLine 2\\n')

    with self.subTest('_adds_error_type_attribute'):
      self.assertEqual(
          failure_element_attributes[
              mobly_sponge_converter.SpongeTreeAttributes.ERROR_TYPE.value
          ],
          'Failure',
      )

    with self.subTest('_adds_error_properties'):
      test_hello_props = test_hello.find('./properties')
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.ERROR_MESSAGE.value,
          'Details: Test failure message',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.ERROR_TYPE.value,
          'Failure',
      )
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.STACK_TRACE.value,
          'Line 1\\nLine 2\\n',
      )

  def test_convert_failed_mobly_test_without_details(self):
    sponge_xml = mobly_sponge_converter.convert(
        _FAIL_WITHOUT_DETAILS_SUMMARY_FILE
    )

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    failure_element = test_hello.find('./failure')
    self.assertIsNotNone(failure_element)
    failure_element_attributes = failure_element.attrib

    with self.subTest('_does_not_add_error_type_attribute'):
      self.assertNotIn(
          mobly_sponge_converter.SpongeTreeAttributes.ERROR_TYPE.value,
          failure_element_attributes,
      )

    with self.subTest('_does_not_add_error_properties'):
      test_hello_props = test_hello.find('./properties')
      self.assertIsNotNone(test_hello_props)
      mobly_error_type_prop = (
          mobly_sponge_converter.MoblySpongeProperties.ERROR_TYPE.value
      )
      self.assertIsNone(
          test_hello_props.find(f'./property[@name="{mobly_error_type_prop}"]')
      )
      mobly_stack_trace_prop = (
          mobly_sponge_converter.MoblySpongeProperties.STACK_TRACE.value
      )
      self.assertIsNone(
          test_hello_props.find(f'./property[@name="{mobly_stack_trace_prop}"]')
      )

  def test_convert_error_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_ERROR_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    with self.subTest('_creates_testsuite_element'):
      test_class_attrs = test_class.attrib
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value
          ],
          '1',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TESTS.value
          ],
          '1',
      )

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    error_element = test_hello.find('./error')
    self.assertIsNotNone(error_element)
    error_element_attributes = error_element.attrib
    with self.subTest('_adds_error_message'):
      self.assertEqual(
          error_element_attributes[
              mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
          ],
          'Details: Test error message',
      )
      self.assertEqual(str(error_element.text), 'Error stacktrace')

    with self.subTest('_adds_error_type_attribute'):
      self.assertEqual(
          error_element_attributes[
              mobly_sponge_converter.SpongeTreeAttributes.ERROR_TYPE.value
          ],
          'Error',
      )

  def test_convert_extra_errors_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_EXTRA_ERRORS_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    error_elements = test_hello.findall('./error')
    self.assertIsNotNone(error_elements)
    self.assertEqual(len(error_elements), 3)
    error_element_1, error_element_2, error_element_3 = error_elements
    error_element_1_attributes = error_element_1.attrib
    self.assertEqual(
        error_element_1_attributes[
            mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
        ],
        'Details: test_error_detail_1',
    )
    self.assertEqual(str(error_element_1.text), 'test_stack_trace_1')
    error_element_2_attributes = error_element_2.attrib
    self.assertEqual(
        error_element_2_attributes[
            mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
        ],
        'Error occurred at teardown_test.\nDetails: test_error_detail_2',
    )
    self.assertEqual(str(error_element_2.text), 'test_stack_trace_2')
    error_element_3_attributes = error_element_3.attrib
    self.assertEqual(
        error_element_3_attributes[
            mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
        ],
        'Error occurred at expect@1708413110.\nDetails: test_error_detail_3',
    )
    self.assertEqual(str(error_element_3.text), 'test_stack_trace_3')

  def test_convert_skipped_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_SKIP_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    with self.subTest('_creates_testsuite_element'):
      test_class_attrs = test_class.attrib
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.ERRORS.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.FAILURES.value
          ],
          '0',
      )
      self.assertEqual(
          test_class_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TESTS.value
          ],
          '1',
      )

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    with self.subTest('_adds_testcase_attributes'):
      test_case_attrs = test_hello.attrib
      self.assertEqual(
          test_case_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.RESULT.value
          ],
          'skipped',
      )
      self.assertEqual(
          test_case_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.STATUS.value
          ],
          'notrun',
      )

    with self.subTest('_adds_testcase_properties'):
      test_hello_props = test_hello.find('./properties')
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.SKIP_REASON.value,
          'Details: Test skip message',
      )

  def test_convert_invalid_yaml_char(self):
    sponge_xml = mobly_sponge_converter.convert(_INVALID_YAML_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    invalid_char_prop = test_hello_props.find(
        './property[@name="invalid_char"]'
    )
    self.assertIsNotNone(invalid_char_prop)
    invalid_char_value = invalid_char_prop.attrib['value']
    self.assertEqual(invalid_char_value, 'char removed')

  def test_convert_interrupted_mobly_test(self):
    sponge_xml = mobly_sponge_converter.convert(_INTERRUPTED_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)

    test_hello = test_class.find('./testcase')
    self.assertIsNotNone(test_hello)
    with self.subTest('_adds_testcase_attributes'):
      test_case_attrs = test_hello.attrib
      self.assertEqual(
          test_case_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.RESULT.value
          ],
          'completed',
      )
      self.assertEqual(
          test_case_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.STATUS.value
          ],
          'run',
      )
      self.assertEqual(
          test_case_attrs[
              mobly_sponge_converter.SpongeTreeAttributes.TIMESTAMP.value
          ],
          '2017-01-26T02:06:31Z',
      )

    with self.subTest('_adds_testcase_properties'):
      test_hello_props = test_hello.find('./properties')
      self._assert_has_property(
          test_hello_props,
          mobly_sponge_converter.MoblySpongeProperties.BEGIN_TIME.value,
          '1485396391375',
      )

    error_element = test_hello.find('./error')
    self.assertIsNotNone(error_element)
    error_element_attributes = error_element.attrib
    with self.subTest('_adds_error_message'):
      self.assertEqual(
          error_element_attributes[
              mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
          ],
          'Details: Test was interrupted manually.',
      )
      self.assertEqual(
          str(error_element.text), 'Details: Test was interrupted manually.'
      )

  def test_convert_mobly_test_with_user_properties(self):
    sponge_xml = mobly_sponge_converter.convert(_USER_PROPERTIES_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    with self.subTest('_adds_user_defined_root_level_properties'):
      mobly_test_props = mobly_test_element.find('./properties')
      self._assert_has_property(mobly_test_props, 'Cake', 'is a lie')
      self._assert_has_property(mobly_test_props, 'Flight Time', '32.4')

    with self.subTest('_accepts_generic_properties_keyword'):
      mobly_test_props = mobly_test_element.find('./properties')
      self._assert_has_property(mobly_test_props, 'Color', 'blue')
      self._assert_has_property(mobly_test_props, 'Temperature', '36')

    hello_world_test_class = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]'
    )
    self.assertIsNotNone(hello_world_test_class)
    another_hello_world_test_class = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]'
    )
    self.assertIsNotNone(another_hello_world_test_class)
    with self.subTest('_adds_user_defined_testsuite_properties'):
      hello_world_props = hello_world_test_class.find('./properties')
      self._assert_has_property(
          hello_world_props, 'class_property_1', 'hello_world'
      )

    test_hello_1 = hello_world_test_class.find('./testcase[@name="test_hello"]')
    self.assertIsNotNone(test_hello_1)
    test_hi = another_hello_world_test_class.find('./testcase[@name="test_hi"]')
    self.assertIsNotNone(test_hi)
    test_hello_2 = another_hello_world_test_class.find(
        './testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_2)
    test_hello_1_props = test_hello_1.find('./properties')
    self.assertIsNotNone(test_hello_1_props)
    test_hello_2_props = test_hello_2.find('./properties')
    self.assertIsNotNone(test_hello_2_props)
    test_hi_props = test_hi.find('./properties')
    with self.subTest('_adds_user_defined_testcase_properties'):
      self._assert_has_property(test_hello_1_props, 'test_property_1', '123')
      self.assertIsNone(
          test_hello_2_props.find('./property[@name="test_property_1"]')
      )
      self._assert_has_property(
          test_hello_1_props, 'test_hello_prop', 'test_hello_val'
      )
      self._assert_has_property(
          test_hello_2_props, 'test_hello_prop', 'test_hello_val'
      )

      self._assert_has_property(test_hi_props, 'test_property_1', 'p1')
      self._assert_has_property(test_hi_props, 'test_property_2', 'p2_2')

    with self.subTest('_removes_invalid_characters_from_properties'):
      self._assert_has_property(
          test_hello_1_props, 'test_invalid_char', 'invalid_char_removed'
      )

    with self.subTest('_does_not_override_mobly_properties'):
      self.assertIsNone(
          test_hello_1_props.find(
              './property[@name="mobly_test_class"][@value="WrongTestClass"]'
          )
      )
      self._assert_has_property(
          test_hello_1_props, 'mobly_test_class', 'HelloWorldTest'
      )

  def _create_mobly_files_and_convert(
      self, file_paths: list[str]
  ) -> ElementTree.ElementTree:
    """Creates a temporary Mobly directory with specified files and runs conversion."""
    with tempfile.TemporaryDirectory() as sponge_root_dir:
      mobly_base_dir = pathlib.Path(sponge_root_dir) / 'mobly'
      mobly_base_dir.mkdir()
      for file_path in file_paths:
        full_path = mobly_base_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

      return mobly_sponge_converter.convert(
          _PASS_SUMMARY_FILE,
          str(mobly_base_dir),
          sponge_root_dir,
      )

  def test_convert_with_test_case_files_adds_test_output_property(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'HelloWorldTest/test_hello-1485396391375/file1.txt',
        'HelloWorldTest/test_hello-1485396391375/subdir/file2.txt',
        'AnotherHelloWorldTest/test_hi-1485396391387/file3.txt',
    ])

    mobly_test_element = sponge_xml.getroot()[0]
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    test_hello_files = self._collect_files(test_hello_props)
    self.assertCountEqual(
        test_hello_files,
        [
            'mobly/HelloWorldTest/test_hello-1485396391375/file1.txt',
            'mobly/HelloWorldTest/test_hello-1485396391375/subdir/file2.txt',
        ],
    )
    test_hi_files = self._collect_files(test_hi_props)
    self.assertCountEqual(
        test_hi_files,
        ['mobly/AnotherHelloWorldTest/test_hi-1485396391387/file3.txt'],
    )

  def test_convert_with_mobly_dir_files_adds_test_output(self):
    sponge_xml = self._create_mobly_files_and_convert(
        ['file1.txt', 'file2.txt', 'subdir/file3.txt']
    )

    mobly_test_element = sponge_xml.getroot()[0]
    mobly_test_props = mobly_test_element.find('./properties')
    mobly_test_files = self._collect_files(mobly_test_props)
    self.assertCountEqual(
        mobly_test_files, ['mobly/file1.txt', 'mobly/file2.txt']
    )

  def test_convert_with_single_device_video_and_logcat(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'test_log.DEBUG',
        'HelloWorldTest/test_hello-1485396391375/video1',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat1',
        'ThirdHelloWorldTest/test_hola-1485396391395/logcat2',
        'ThirdHelloWorldTest/test_hola-1485396391395/video2',
    ])

    mobly_test_element = sponge_xml.getroot()[0]

    # One video
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    test_hello_inspector_prop = test_hello_props.find(
        './property[@name="inspector_link"]'
    )
    self.assertIsNotNone(test_hello_inspector_prop)
    test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
    with self.subTest('_adds_single_device_inspector_link_prop'):
      self.assertIn('utm_medium=single', test_hello_inspector_link)
    with self.subTest('_inspector_link_property_contains_sponge_params'):
      self.assertIn('invocationId={{invocationId}}', test_hello_inspector_link)
      self.assertIn('targetId={{targetId}}', test_hello_inspector_link)
      self.assertIn(
          'configurationId={{configurationId}}',
          test_hello_inspector_link,
      )
      self.assertIn('actionId={{actionId}}', test_hello_inspector_link)

    # One logcat
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    with self.subTest('_adds_single_device_inspector_link_prop'):
      test_hi_inspector_prop = test_hi_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hi_inspector_prop)
      test_hi_inspector_link = test_hi_inspector_prop.attrib['value']
      self.assertIn('utm_medium=single', test_hi_inspector_link)

    # One video and one logcat
    test_hola_element = mobly_test_element.find(
        './testsuite[@name="ThirdHelloWorldTest"]/testcase[@name="test_hola"]'
    )
    self.assertIsNotNone(test_hola_element)
    test_hola_props = test_hola_element.find('./properties')
    self.assertIsNotNone(test_hola_props)
    with self.subTest('_adds_single_device_inspector_link_prop'):
      test_hola_inspector_prop = test_hola_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hola_inspector_prop)
      test_hola_inspector_link = test_hola_inspector_prop.attrib['value']
      self.assertIn('utm_medium=single', test_hola_inspector_link)

  def test_convert_with_multiple_devices_video_and_logcat(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'test_log.DEBUG',
        'HelloWorldTest/test_hello-1485396391375/video1',
        'HelloWorldTest/test_hello-1485396391375/video2',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat1',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat2',
        'ThirdHelloWorldTest/test_hola-1485396391395/logcat1',
        'ThirdHelloWorldTest/test_hola-1485396391395/logcat2',
        'ThirdHelloWorldTest/test_hola-1485396391395/video1',
        'ThirdHelloWorldTest/test_hola-1485396391395/video2',
    ])

    mobly_test_element = sponge_xml.getroot()[0]

    # Two videos
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    test_hello_inspector_prop = test_hello_props.find(
        './property[@name="inspector_link"]'
    )
    self.assertIsNotNone(test_hello_inspector_prop)
    test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      self.assertIn('utm_medium=multiple', test_hello_inspector_link)
    with self.subTest('_inspector_link_property_contains_sponge_params'):
      self.assertIn('invocationId={{invocationId}}', test_hello_inspector_link)
      self.assertIn('targetId={{targetId}}', test_hello_inspector_link)
      self.assertIn(
          'configurationId={{configurationId}}', test_hello_inspector_link
      )
      self.assertIn('actionId={{actionId}}', test_hello_inspector_link)

    # Two logcats
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hi_inspector_prop = test_hi_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hi_inspector_prop)
      test_hi_inspector_link = test_hi_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hi_inspector_link)

    # Two videos and two logcats
    test_hola_element = mobly_test_element.find(
        './testsuite[@name="ThirdHelloWorldTest"]/testcase[@name="test_hola"]'
    )
    self.assertIsNotNone(test_hola_element)
    test_hola_props = test_hola_element.find('./properties')
    self.assertIsNotNone(test_hola_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hola_inspector_prop = test_hola_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hola_inspector_prop)
      test_hola_inspector_link = test_hola_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hola_inspector_link)

  def test_convert_with_cros_devices_video_and_log(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'test_log.DEBUG',
        'HelloWorldTest/test_hello-1485396391375/cros_log,chrome,',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat1',
        'AnotherHelloWorldTest/test_hi-1485396391387/cros_log,chrome,',
        'ThirdHelloWorldTest/test_hola-1485396391395/cros_log,chrome,1',
        'ThirdHelloWorldTest/test_hola-1485396391395/cros_log,chrome,2',
        'ThirdHelloWorldTest/test_hola-1485396391395/cros_video,1',
        'ThirdHelloWorldTest/test_hola-1485396391395/cros_video,2',
    ])

    mobly_test_element = sponge_xml.getroot()[0]

    # One CrOS log
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    with self.subTest('_adds_single_device_inspector_link_prop'):
      test_hello_inspector_prop = test_hello_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hello_inspector_prop)
      test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
      self.assertIn('utm_medium=single', test_hello_inspector_link)

    # One logcat and one CrOS log
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hi_inspector_prop = test_hi_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hi_inspector_prop)
      test_hi_inspector_link = test_hi_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hi_inspector_link)

    # Two CrOS videos and two CrOS logs
    test_hola_element = mobly_test_element.find(
        './testsuite[@name="ThirdHelloWorldTest"]/testcase[@name="test_hola"]'
    )
    self.assertIsNotNone(test_hola_element)
    test_hola_props = test_hola_element.find('./properties')
    self.assertIsNotNone(test_hola_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hola_inspector_prop = test_hola_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hola_inspector_prop)
      test_hola_inspector_link = test_hola_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hola_inspector_link)

  def test_convert_with_eiffel_devices_log(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'test_log.DEBUG',
        'HelloWorldTest/test_hello-1485396391375/eiffel_log,',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat1',
        'AnotherHelloWorldTest/test_hi-1485396391387/eiffel_log,',
    ])

    mobly_test_element = sponge_xml.getroot()[0]

    # One Eiffel log
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    with self.subTest('_adds_single_device_inspector_link_prop'):
      test_hello_inspector_prop = test_hello_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hello_inspector_prop)
      test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
      self.assertIn('utm_medium=single', test_hello_inspector_link)

    # One logcat and one Eiffel log
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hi_inspector_prop = test_hi_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hi_inspector_prop)
      test_hi_inspector_link = test_hi_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hi_inspector_link)

  def test_convert_with_windows_devices_log(self):
    sponge_xml = self._create_mobly_files_and_convert([
        'test_log.DEBUG',
        'HelloWorldTest/test_hello-1485396391375/windows_log,',
        'HelloWorldTest/test_hello-1485396391375/window_video,',
        'AnotherHelloWorldTest/test_hi-1485396391387/logcat1',
        'AnotherHelloWorldTest/test_hi-1485396391387/windows_log,',
        'AnotherHelloWorldTest/test_hi-1485396391387/window_video,',
    ])

    mobly_test_element = sponge_xml.getroot()[0]

    # One Windows log
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    with self.subTest('_adds_single_device_inspector_link_prop'):
      test_hello_inspector_prop = test_hello_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hello_inspector_prop)
      test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
      self.assertIn('utm_medium=single', test_hello_inspector_link)

    # One Android and one Windows log
    test_hi_element = mobly_test_element.find(
        './testsuite[@name="AnotherHelloWorldTest"]/testcase[@name="test_hi"]'
    )
    self.assertIsNotNone(test_hi_element)
    test_hi_props = test_hi_element.find('./properties')
    self.assertIsNotNone(test_hi_props)
    with self.subTest('_adds_multi_device_inspector_link_prop'):
      test_hi_inspector_prop = test_hi_props.find(
          './property[@name="inspector_link"]'
      )
      self.assertIsNotNone(test_hi_inspector_prop)
      test_hi_inspector_link = test_hi_inspector_prop.attrib['value']
      self.assertIn('utm_medium=multiple', test_hi_inspector_link)

  def test_convert_without_video_nor_logcat(self):
    sponge_xml = self._create_mobly_files_and_convert(
        ['test_log.DEBUG', 'HelloWorldTest/test_hello-1485396391375/artifact']
    )

    mobly_test_element = sponge_xml.getroot()[0]
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    test_hello_inspector_prop = test_hello_props.find(
        './property[@name="inspector_link"]'
    )
    self.assertIsNotNone(test_hello_inspector_prop)
    test_hello_inspector_link = test_hello_inspector_prop.attrib['value']
    self.assertIn('utm_medium=single', test_hello_inspector_link)

  def test_convert_without_test_log(self):
    sponge_xml = self._create_mobly_files_and_convert(
        ['HelloWorldTest/test_hello-1485396391375/artifact']
    )

    mobly_test_element = sponge_xml.getroot()[0]
    test_hello_element = mobly_test_element.find(
        './testsuite[@name="HelloWorldTest"]/testcase[@name="test_hello"]'
    )
    self.assertIsNotNone(test_hello_element)
    test_hello_props = test_hello_element.find('./properties')
    self.assertIsNotNone(test_hello_props)
    test_hello_inspector_prop = test_hello_props.find(
        './property[@name="inspector_link"]'
    )
    self.assertIsNone(test_hello_inspector_prop)

  def test_convert_mobly_test_with_retries(self):
    sponge_xml = mobly_sponge_converter.convert(_RETRY_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    # Results are error, error, pass.
    first_run = test_class.find('./testcase[@retrynumber="0"]')
    self.assertIsNotNone(first_run)
    error_element_1 = first_run.find('./error')
    self.assertIsNotNone(error_element_1)
    error_message_1 = error_element_1.attrib[
        mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
    ]
    self.assertIn('error message 1', error_message_1)
    second_run = test_class.find('./testcase[@retrynumber="1"]')
    self.assertIsNotNone(second_run)
    error_element_2 = second_run.find('./error')
    self.assertIsNotNone(error_element_2)
    error_message_2 = error_element_2.attrib[
        mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
    ]
    self.assertIn('error message 2', error_message_2)
    third_run = test_class.find('./testcase[@retrynumber="2"]')
    self.assertIsNotNone(third_run)
    self.assertIsNone(third_run.find('./error'))

  def test_convert_mobly_test_with_repeats(self):
    sponge_xml = mobly_sponge_converter.convert(_REPEAT_SUMMARY_FILE)

    mobly_test_element = sponge_xml.getroot()[0]
    test_class = mobly_test_element.find('./testsuite[@name="HelloWorldTest"]')
    self.assertIsNotNone(test_class)
    # Results are error, pass, error.
    first_run = test_class.find('./testcase[@repeatnumber="0"]')
    self.assertIsNotNone(first_run)
    error_element_1 = first_run.find('./error')
    self.assertIsNotNone(error_element_1)
    error_message_1 = error_element_1.attrib[
        mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
    ]
    self.assertIn('error message 1', error_message_1)
    second_run = test_class.find('./testcase[@repeatnumber="1"]')
    self.assertIsNotNone(second_run)
    self.assertIsNone(second_run.find('./error'))
    third_run = test_class.find('./testcase[@repeatnumber="2"]')
    self.assertIsNotNone(third_run)
    error_element_2 = third_run.find('./error')
    self.assertIsNotNone(error_element_2)
    error_message_2 = error_element_2.attrib[
        mobly_sponge_converter.SpongeTreeAttributes.MESSAGE.value
    ]
    self.assertIn('error message 2', error_message_2)

    with self.subTest('_set_repeat_specific_properties'):
      first_run_props = first_run.find('./properties')
      self._assert_has_property(
          first_run_props,
          'test_hello_prop',
          'test_hello_val_0',
      )
      second_run_props = second_run.find('./properties')
      self._assert_has_property(
          second_run_props,
          'test_hello_prop',
          'test_hello_val_1',
      )
      third_run_props = third_run.find('./properties')
      self._assert_has_property(
          third_run_props,
          'test_hello_prop',
          'test_hello_val_2',
      )

  def test_convert_reporter_value_error(self):
    self.mock_components_convert.return_value = [
        test_component_pb2.TestComponent(name='test_component_1'),
        test_component_pb2.TestComponent(name='invalid.test.component'),
    ]
    mock_test_component_reporter = mock.create_autospec(
        test_component_reporter.TestComponentReporter
    )
    mock_test_component_reporter.write.side_effect = [None, ValueError]
    with mock.patch.object(
        test_component_reporter, 'TestComponentReporter', autospec=True
    ) as mock_reporter_constructor:
      mock_reporter_constructor.return_value = mock_test_component_reporter

      with self.assertLogs(level='ERROR') as log_output:
        log_level = logging.get_verbosity()
        logging.set_verbosity(logging.ERROR)
        mobly_sponge_converter.convert(_PASS_SUMMARY_FILE)
        logging.set_verbosity(log_level)

      output = log_output[0][0].message
      self.assertIn(
          'Failed to write test component invalid.test.component.', output
      )

  def test_convert_writes_test_components(self):
    self.mock_components_convert.return_value = [
        test_component_pb2.TestComponent(
            name='test_component_1', description='test_component_1_1'
        ),
        test_component_pb2.TestComponent(
            name='test_component_2', description='test_component_2'
        ),
        test_component_pb2.TestComponent(
            name='test_component_1', description='test_component_1_2'
        ),
    ]
    mock_test_component_reporter = mock.create_autospec(
        test_component_reporter.TestComponentReporter
    )
    with mock.patch.object(
        test_component_reporter, 'TestComponentReporter', autospec=True
    ) as mock_reporter_constructor:
      mock_reporter_constructor.return_value = mock_test_component_reporter

      mobly_sponge_converter.convert(_PASS_SUMMARY_FILE)

      self.mock_components_convert.assert_called_once()
      mock_test_component_reporter.write.assert_has_calls([
          mock.call(
              test_component_pb2.TestComponent(
                  name='test_component_1', description='test_component_1_1'
              )
          ),
          mock.call(
              test_component_pb2.TestComponent(
                  name='test_component_2', description='test_component_2'
              )
          ),
      ])
      mock_test_component_reporter.append.assert_called_once_with(
          test_component_pb2.TestComponent(
              name='test_component_1', description='test_component_1_2'
          )
      )

  def _assert_has_property(
      self, properties_element: ElementTree.Element, name: str, value: str
  ):
    property_element = properties_element.find(f'./property[@name="{name}"]')
    self.assertIsNotNone(property_element)
    self.assertEqual(
        property_element.attrib[
            mobly_sponge_converter.SpongeTreeAttributes.VALUE.value
        ],
        value,
    )

  def _collect_files(
      self, properties_element: ElementTree.Element
  ) -> list[str]:
    counter = 0
    files = []
    while True:
      property_element = properties_element.find(
          f'./property[@name="test_output{counter}"]'
      )
      if property_element is None:
        break
      files.append(
          property_element.attrib[
              mobly_sponge_converter.SpongeTreeAttributes.VALUE.value
          ]
      )
      counter += 1
    return files


if __name__ == '__main__':
  unittest.main()
