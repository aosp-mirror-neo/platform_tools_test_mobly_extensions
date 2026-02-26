"""Utility functions to report test components (go/sponge-test-components)."""

import logging
import os
import re
from typing import Optional
import uuid

from mobly_sponge_converter import delimited_message
from protos import test_component_pb2


def _has_valid_name(component: test_component_pb2.TestComponent) -> bool:
  if component.name is None:
    return False
  return re.fullmatch(r'[a-zA-Z0-9_-]+', component.name) is not None


def _check_has_valid_name(component: test_component_pb2.TestComponent) -> None:
  if not _has_valid_name(component):
    raise ValueError(f'Component name {component.name} must only contain '
                     f'characters [a-zA-Z0-9_-].')


class TestComponentReporter:
  """Utility class to report test components."""

  def __init__(self, output_dir: Optional[str] = None) -> None:
    """Constructor.

    Args:
      output_dir: The directory to which the components should be written. If
        unspecified, it will default to the value of the `TEST_COMPONENTS_DIR`
        environment variable.

    Raises:
      RuntimeError: If no output directory could be resolved.
    """
    if output_dir is None:
      output_dir = os.environ.get('TEST_COMPONENTS_DIR')
      if output_dir is None:
        raise RuntimeError('Either the `outpath_dir` must be set, or the '
                           '`TEST_COMPONENTS_DIR` environment variable should '
                           'be defined.')
    file_name = f'component_{uuid.uuid4()}.pb'
    self._output_path = os.path.join(output_dir, file_name)
    self._name = None

  def write(self, component: test_component_pb2.TestComponent) -> None:
    """Writes the test component data to a length delimited protobuf file.

    Multiple calls to this method on the same instance will overwrite data.

    Args:
      component: The test component message to be written.
    """
    _check_has_valid_name(component)
    self._name = component.name
    logging.debug('Writing component %s to %s', component.name,
                  self._output_path)
    with open(self._output_path, 'wb') as output:
      delimited_message.SerializeDelimitedTo(component, output)

  def append(self, component: test_component_pb2.TestComponent) -> None:
    """Appends test component data to the current file.

    This will append data to allow recording details of subsequent events on
    this component. This must have the same name as the previous component.

    Args:
      component: The test component message to be written.

    Raises:
      RuntimeError: If a test component name does not match.
    """
    if self._name is None:
      self.write(component)
      return
    if self._name != component.name:
      raise RuntimeError(
          f'Name {component.name} does not match previously written name {self._name}'
      )
    logging.debug('Appending component %s to %s', component.name,
                  self._output_path)
    with open(self._output_path, 'ab') as output:
      delimited_message.SerializeDelimitedTo(component, output)
