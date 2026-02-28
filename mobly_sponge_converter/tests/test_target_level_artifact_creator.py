import pathlib
import tempfile
import unittest
from unittest import mock

from sponge_artifact_creator import target_level_artifact_creator


class TargetLevelArtifactCreatorTest(unittest.TestCase):
  """Unit tests for TargetLevelArtifactCreator."""

  def setUp(self):
    super().setUp()
    self.tmp_dir = tempfile.TemporaryDirectory()
    self.src_dir = pathlib.Path(self.tmp_dir.name) / 'src'
    self.dst_dir = pathlib.Path(self.tmp_dir.name) / 'dst'
    self.src_dir.mkdir()
    self.dst_dir.mkdir()
    self.creator = target_level_artifact_creator.TargetLevelArtifactCreator(
        self.src_dir, self.dst_dir
    )

  def tearDown(self):
    self.tmp_dir.cleanup()
    super().tearDown()

  def test_merge_components_pb_no_files(self):
    """Verifies that no file is created when source dir is empty."""
    components_dir = self.src_dir / 'components'
    components_dir.mkdir()
    with self.assertLogs('root', level='WARNING'):
      self.creator.merge_components_pb(components_dir)
    self.assertFalse(
        (self.dst_dir / target_level_artifact_creator.TEST_COMPONENTS_PB)
        .exists()
    )

  def test_merge_components_pb_multiple_files(self):
    """Verifies that component files are merged correctly."""
    components_dir = self.src_dir / 'components'
    components_dir.mkdir()
    (components_dir / 'components_a.pb').write_bytes(b'a')
    (components_dir / 'components_b.pb').write_bytes(b'b')

    self.creator.merge_components_pb(components_dir)

    expected_content = b'ab'
    with open(
        self.dst_dir / target_level_artifact_creator.TEST_COMPONENTS_PB, 'rb'
    ) as f:
      self.assertEqual(f.read(), expected_content)

  def test_create_test_xml_no_summary(self):
    """Verifies that test.xml is not created if no summary yaml is found."""
    with self.assertLogs('root', level='WARNING'):
      self.creator.create_test_xml()
    self.assertFalse(
        (self.dst_dir / target_level_artifact_creator.TEST_XML).exists()
    )

  @mock.patch('mobly_sponge_converter.mobly_sponge_converter.convert')
  def test_create_test_xml_creates_xml(self, mock_convert):
    """Verifies that test.xml is created from test_summary.yaml."""
    mock_et = mock.MagicMock()
    mock_convert.return_value = mock_et
    (self.src_dir / target_level_artifact_creator.TEST_SUMMARY_YAML).touch()

    with self.assertLogs('root', level='WARNING'):
      self.creator.create_test_xml()

    mock_convert.assert_called_once_with(
        mobly_results_path=str(
            self.src_dir / target_level_artifact_creator.TEST_SUMMARY_YAML
        ),
        mobly_base_directory=str(self.src_dir),
        sponge_root_directory=str(self.src_dir),
        test_components_output_directory=mock.ANY,
    )
    mock_et.write.assert_called_once_with(
        self.dst_dir / target_level_artifact_creator.TEST_XML,
        encoding='utf-8',
        xml_declaration=True,
    )

  def test_create_test_log_no_info_log(self):
    """Verifies that test.log is not created if test_log.INFO is not found."""
    with self.assertLogs('root', level='WARNING'):
      self.creator.create_test_log()
    self.assertFalse(
        (self.dst_dir / target_level_artifact_creator.TEST_LOG).exists()
    )

  def test_create_test_log_creates_log(self):
    """Verifies that test.log is created from test_log.INFO."""
    log_content = 'some log content'
    (self.src_dir / target_level_artifact_creator.TEST_INFO_LOG).write_text(
        log_content
    )

    self.creator.create_test_log()

    with open(self.dst_dir / target_level_artifact_creator.TEST_LOG) as f:
      self.assertEqual(f.read(), log_content)

  @mock.patch.object(
      target_level_artifact_creator.TargetLevelArtifactCreator,
      'create_test_xml',
  )
  @mock.patch.object(
      target_level_artifact_creator.TargetLevelArtifactCreator,
      'create_test_log',
  )
  def test_create_artifacts_calls_creators(
      self, mock_create_log, mock_create_xml
  ):
    """Verifies that create_artifacts calls the correct methods."""
    self.creator.create_artifacts()
    mock_create_xml.assert_called_once()
    mock_create_log.assert_called_once()


if __name__ == '__main__':
  unittest.main()
