import logging
import pathlib
import tempfile
from xml.etree import ElementTree
from mobly_sponge_converter import mobly_sponge_converter
from sponge_artifact_creator import base_artifact_creator

TEST_COMPONENTS_PB = "test_components.pb"
TEST_INFO_LOG = "test_log.INFO"
TEST_SUMMARY_YAML = "test_summary.yaml"
TEST_XML = "test.xml"
TEST_LOG = "test.log"


class TargetLevelArtifactCreator(
    base_artifact_creator.BaseArtifactCreator
):
  """Creates Sponge target-level artifacts e.g. test.xml, test.log, etc."""

  def merge_components_pb(
      self, src_dir: pathlib.Path
  ) -> None:
    """
    Creates a test_components.pb file from a directory of components.pb files.
    """
    if not any(src_dir.iterdir()):
      logging.warning(
          "%s has no files, skipping %s creation.",
          src_dir,
          TEST_COMPONENTS_PB,
      )
      return

    with open(self.dst_dir / TEST_COMPONENTS_PB, "w+b") as dst_file:
      for component_file in sorted(src_dir.iterdir()):
        with open(component_file, "rb") as src_file:
          dst_file.write(src_file.read())
    logging.info("Created %s.", self.dst_dir / TEST_COMPONENTS_PB)

  def create_test_xml(self) -> None:
    """
    Creates a test.xml and test_components.pb file from Mobly test_summary.yaml.
    """
    if not (self.src_dir / TEST_SUMMARY_YAML).is_file():
      logging.warning(
          "%s not found, skipping %s creation.", TEST_SUMMARY_YAML, TEST_XML
      )
      return

    with tempfile.TemporaryDirectory() as tmp_dir:
      test_xml = mobly_sponge_converter.convert(
          mobly_results_path=str(self.src_dir / TEST_SUMMARY_YAML),
          mobly_base_directory=str(self.src_dir),
          sponge_root_directory=str(self.src_dir),
          test_components_output_directory=tmp_dir,
      )
      self.merge_components_pb(pathlib.Path(tmp_dir))

    ElementTree.indent(test_xml)
    test_xml.write(
        self.dst_dir / TEST_XML,
        encoding="utf-8",
        xml_declaration=True,
    )
    logging.info("Created %s.", self.dst_dir / TEST_XML)

  def create_test_log(self) -> None:
    """Creates a test.log file from Mobly test_log.INFO file."""
    if not (self.src_dir / TEST_INFO_LOG).is_file():
      logging.warning(
          "%s not found, skipping %s creation.", TEST_INFO_LOG, TEST_LOG
      )
      return

    with open(self.dst_dir / TEST_LOG, "w") as dst_file:
      with open(self.src_dir / TEST_INFO_LOG, "r") as src_file:
        dst_file.write(src_file.read())
    logging.info("Created %s.", self.dst_dir / TEST_LOG)

  def create_artifacts(self) -> None:
    """Creates Sponge target-level artifacts."""
    self.create_test_xml()
    self.create_test_log()
