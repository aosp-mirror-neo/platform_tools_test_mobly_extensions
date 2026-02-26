import pathlib
import tempfile
import unittest
from unittest import mock

from sponge_artifact_creator import invocation_level_artifact_creator


class InvocationLevelArtifactCreatorTest(unittest.TestCase):
  """Unit tests for InvocationLevelArtifactCreator."""

  def setUp(self):
    super().setUp()
    self.tmp_dir = tempfile.TemporaryDirectory()
    self.src_dir = pathlib.Path(self.tmp_dir.name) / 'src'
    self.dst_dir = pathlib.Path(self.tmp_dir.name) / 'dst'
    self.src_dir.mkdir()
    self.dst_dir.mkdir()
    self.src_log_filename = 'atest.log'
    self.creator = invocation_level_artifact_creator.InvocationLevelArtifactCreator(
        self.src_dir, self.dst_dir, self.src_log_filename
    )

  def tearDown(self):
    self.tmp_dir.cleanup()
    super().tearDown()

  def test_create_build_log_no_src_log(self):
    """Verifies that build.log is not created if src log is not found."""
    with self.assertLogs('root', level='WARNING'):
      self.creator.create_build_log()
    self.assertFalse(
        (self.dst_dir / invocation_level_artifact_creator.BUILD_LOG).exists()
    )

  def test_create_build_log_creates_log(self):
    """Verifies that build.log is created from the source log."""
    log_content = 'some log content'
    (self.src_dir / self.src_log_filename).write_text(log_content)

    self.creator.create_build_log()

    with open(
        self.dst_dir / invocation_level_artifact_creator.BUILD_LOG
    ) as f:
      self.assertEqual(f.read(), log_content)

  @mock.patch.object(
      invocation_level_artifact_creator.InvocationLevelArtifactCreator,
      'create_build_log',
  )
  def test_create_artifacts_calls_creators(self, mock_create_log):
    """Verifies that create_artifacts calls the correct methods."""
    self.creator.create_artifacts()
    mock_create_log.assert_called_once()


if __name__ == '__main__':
  unittest.main()
