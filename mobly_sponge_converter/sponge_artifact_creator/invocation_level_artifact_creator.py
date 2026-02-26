import logging
import pathlib
from sponge_artifact_creator import base_artifact_creator

BUILD_LOG = "build.log"


class InvocationLevelArtifactCreator(
    base_artifact_creator.BaseArtifactCreator
):
  """Creates Sponge invocation-level artifacts e.g. build.log, etc."""

  def __init__(
      self,
      src_dir: pathlib.Path,
      dst_dir: pathlib.Path,
      src_log_filename: str,
  ):
    super().__init__(src_dir, dst_dir)
    self.src_log_filename = src_log_filename  # e.g. atest.log

  def create_build_log(self) -> None:
    """Creates a build.log file from a test runner log path."""
    if not (self.src_dir / self.src_log_filename).is_file():
      logging.warning(
          "%s not found, skipping %s creation.",
          self.src_log_filename,
          BUILD_LOG,
      )
      return

    with open(self.dst_dir / BUILD_LOG, "w") as dst_file:
      with open(self.src_dir / self.src_log_filename, "r") as src_file:
        dst_file.write(src_file.read())
    logging.info("Created %s.", self.dst_dir / BUILD_LOG)

  def create_artifacts(self) -> None:
    """Creates Sponge invocation-level artifacts."""
    self.create_build_log()
