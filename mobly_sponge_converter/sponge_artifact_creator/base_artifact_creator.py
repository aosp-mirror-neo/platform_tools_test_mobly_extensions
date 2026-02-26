import abc
import pathlib


class BaseArtifactCreator(abc.ABC):
  """Base class for creating Sponge artifacts."""

  def __init__(self, src_dir: pathlib.Path, dst_dir: pathlib.Path):
    self.src_dir = src_dir
    self.dst_dir = dst_dir

  @abc.abstractmethod
  def create_artifacts(self) -> None:
    """Creates Sponge artifacts."""
    ...
