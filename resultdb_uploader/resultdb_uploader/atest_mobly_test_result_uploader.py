import dataclasses
import logging
from resultdb_uploader import utils
import resultdb_uploader.resultdb_writer as resultdb_writer
import resultdb_uploader.test_status as resultdb_test_status


@dataclasses.dataclass
class WorkUnit:
  name: str
  update_token: str


class AtestMoblyTestResultUploader:
  def __init__(self, config: utils.Config) -> None:
    self.client = resultdb_writer.ResultDBWriter(config=config)
    self.root_invocation_id = None
    self.root_work_unit = None
    self.work_units: dict[str, WorkUnit] = {}
    self.test_result_name = None
    self.next_test_result_id = 1
    self.curr_test_result_id = 1

  def ants_id_to_resultdb_id(self, ants_id: str) -> str:
    return f"u-ants-{ants_id}"

  def get_next_test_result_id(self) -> str:
    self.curr_test_result_id = self.next_test_result_id
    self.next_test_result_id += 1
    return str(self.curr_test_result_id)

  def create_root_invocation(self, ants_invocation_id: str) -> None:
    root_invocation_response, update_token = self.client.create_root_invocation(
      self.ants_id_to_resultdb_id(ants_invocation_id),
    )
    assert self.root_work_unit is None, "Root work unit already exists."
    self.root_invocation_id = root_invocation_response.root_invocation.root_invocation_id
    self.root_work_unit = WorkUnit(
        name=root_invocation_response.root_work_unit.name,
        update_token=update_token,
    )

  def create_child_work_unit(
      self,
      ants_work_unit_id: str,
      module_name: str,
  ) -> None:
    assert self.root_work_unit is not None, "Root work unit does not exist."
    if ants_work_unit_id in self.work_units:
      return

    work_unit_response, update_token = self.client.create_work_unit(
        parent_work_unit_name=self.root_work_unit.name,
        parent_update_token=self.root_work_unit.update_token,
        work_unit_id=self.ants_id_to_resultdb_id(ants_work_unit_id),
        module_name=module_name,
    )
    self.work_units[ants_work_unit_id] = WorkUnit(
        name=work_unit_response.name,
        update_token=update_token,
    )

  def create_test_result(
      self,
      ants_work_unit_id: str,
      module_name: str,
      class_name: str,
      method_name: str,
      start_time_nanoseconds: int,
      duration_nanoseconds: int,
      test_status: resultdb_test_status.TestStatus,
      failure_reason: resultdb_test_status.FailureStatusReason | None = None,
      skipped_reason: resultdb_test_status.SkippedStatusReason | None = None,
      summary_html: str | None = None,
  ) -> None:
    assert ants_work_unit_id in self.work_units, "Work unit does not exist."
    work_unit = self.work_units[ants_work_unit_id]
    self.client.create_test_result(
        parent_work_unit_name=work_unit.name,
        parent_update_token=work_unit.update_token,
        module_name=module_name,
        class_name=class_name,
        method_name=method_name,
        start_time_nanoseconds=start_time_nanoseconds,
        duration_nanoseconds=duration_nanoseconds,
        test_result_id=self.get_next_test_result_id(),
        test_status=test_status,
        failure_reason=failure_reason,
        skipped_reason=skipped_reason,
        summary_html=summary_html,
    )

  def create_test_artifacts(
      self,
      ants_work_unit_id: str,
      module_name: str,
      class_name: str,
      method_name: str,
      artifact_paths: list[str],
  ) -> None:
    if not artifact_paths:
      logging.warning("No artifact paths provided. Skipping artifact creation.")
      return

    assert ants_work_unit_id in self.work_units, "Work unit does not exist."
    work_unit = self.work_units[ants_work_unit_id]
    self.client.batch_create_test_artifacts(
        work_unit_name=work_unit.name,
        update_token=work_unit.update_token,
        module_name=module_name,
        class_name=class_name,
        method_name=method_name,
        test_result_id=str(self.curr_test_result_id),
        artifact_paths=artifact_paths,
    )

  def _finalize_work_unit(self, work_unit: WorkUnit) -> None:
    self.client.finalize_work_unit(
        work_unit_name=work_unit.name,
        work_unit_update_token=work_unit.update_token,
    )

  def finalize_root_work_unit(self) -> None:
    assert self.root_work_unit is not None, "Root work unit does not exist."
    self._finalize_work_unit(self.root_work_unit)
    self.root_work_unit = None

  def finalize_all_work_units(self) -> None:
    for work_unit in self.work_units.values():
      self._finalize_work_unit(work_unit)
    self.work_units = {}
