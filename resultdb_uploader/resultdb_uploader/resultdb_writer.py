import hashlib
import logging
import os
from urllib import parse as urllib_parse
import uuid

import google.auth as auth
import google.auth.transport.grpc as auth_transport_grpc
import google.auth.transport.requests as auth_transport_requests
from google.protobuf import duration_pb2
from google.protobuf import timestamp_pb2
import grpc
import requests
import resultdb_uploader.recorder_client as recorder_client
import resultdb_uploader.test_status as resultdb_test_status
import resultdb_uploader.utils as utils
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import artifact_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import common_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import failure_reason_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import recorder_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import root_invocation_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import skipped_reason_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import test_result_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import work_unit_pb2


MOBLY_SCHEME = "mobly"
WORK_UNIT_KIND = "ATEST_MOBLY_RUNNER"
REALM = "android:local-tests"
DEFAULT_SKIPPED_REASON_MESSAGE = "skipped"
RESULTDB_SCOPE = ["https://www.googleapis.com/auth/userinfo.email"]
SYSTEM = "atest"
NANOSECONDS_MULTIPLIER = 1_000_000_000
MAX_ARTIFACT_GRPC_SIZE_BYTES = 3.5 * 1024 * 1024
MAX_ARTIFACT_STREAMING_SIZE_BYTES = 630 * 1024 * 1024  # 630 MB


class ResultDBWriter:
  def __init__(self, config: utils.Config):
    self.config = config
    self._recorder_client = recorder_client.RecorderClient(
        channel_creds=self._get_channel_creds(), is_prod=config.is_prod
    )
    logging.debug("Uploading to ResultDB %s", config.name)
    utils.init_mime_types()

  def _get_channel_creds(self) -> grpc.ChannelCredentials:
    """Gets the channel credentials for the Recorder Client."""
    creds, _ = auth.default(scopes=RESULTDB_SCOPE)
    auth_plugin = auth_transport_grpc.AuthMetadataPlugin(
        creds, auth_transport_requests.Request()
    )
    return grpc.composite_channel_credentials(
      grpc.ssl_channel_credentials(),
      grpc.metadata_call_credentials(auth_plugin),
    )

  def create_root_invocation(
      self, root_invocation_id: str
  ) -> tuple[recorder_pb2.RootInvocation, str]:
    with self._recorder_client as client:
      create_root_req = recorder_pb2.CreateRootInvocationRequest(
          root_invocation_id=root_invocation_id,
          request_id=str(uuid.uuid4()),
          root_work_unit=work_unit_pb2.WorkUnit(
              kind=WORK_UNIT_KIND,
              state=work_unit_pb2.WorkUnit.State.RUNNING,
          ),
          root_invocation=root_invocation_pb2.RootInvocation(
              realm=REALM,
              streaming_export_state=root_invocation_pb2.RootInvocation.StreamingExportState.METADATA_FINAL,
              sources=common_pb2.Sources(is_dirty=True),
              producer_resource=common_pb2.ProducerResource(
                system=SYSTEM,
                data_realm=self.config.data_realm,
                name=f"run/{uuid.uuid4()}",
              ),
          )
      )
      root_inv_resp, root_update_token = client.create_root_invocation(
          create_root_req
      )
      logging.debug(
          "Successfully created root invocation: %s",
          root_inv_resp.root_invocation.name,
      )
    return root_inv_resp, root_update_token

  def create_work_unit(
      self,
      parent_work_unit_name: str,
      parent_update_token: str,
      work_unit_id: str,
      module_name: str,
  ) -> tuple[recorder_pb2.WorkUnit, str]:
    with self._recorder_client as client:
      create_work_unit_req = recorder_pb2.CreateWorkUnitRequest(
        parent=parent_work_unit_name,
        work_unit_id=work_unit_id,
        work_unit=work_unit_pb2.WorkUnit(
            kind=WORK_UNIT_KIND,
            state=work_unit_pb2.WorkUnit.State.RUNNING,
            realm=REALM,
            module_id=common_pb2.ModuleIdentifier(
                module_name=module_name,
                module_scheme=MOBLY_SCHEME,
                module_variant=common_pb2.Variant(),
            ),
        ),
        request_id=str(uuid.uuid4()),
      )
      work_unit_resp, work_unit_update_token = client.create_work_unit(
          create_work_unit_req, parent_update_token
      )
      logging.debug(
          "Successfully created work unit: %s", work_unit_resp.name
      )
    return work_unit_resp, work_unit_update_token

  def create_test_result(
      self,
      parent_work_unit_name: str,
      parent_update_token: str,
      module_name: str,
      class_name: str,
      method_name: str,
      start_time_nanoseconds: int,
      duration_nanoseconds: int,
      test_result_id: str,
      test_status: resultdb_test_status.TestStatus,
      failure_reason: resultdb_test_status.FailureStatusReason | None = None,
      skipped_reason: resultdb_test_status.SkippedStatusReason | None = None,
      summary_html: str | None = None,
  ) -> None:
    with self._recorder_client as client:
      req_kwargs = {}
      if failure_reason:
        req_kwargs["failure_reason"] = failure_reason_pb2.FailureReason(
          kind=failure_reason.value
        )
      if skipped_reason:
        req_kwargs["skipped_reason"] = skipped_reason_pb2.SkippedReason(
          kind=skipped_reason.value,
          reason_message=DEFAULT_SKIPPED_REASON_MESSAGE,
        )
      create_tr_req = recorder_pb2.CreateTestResultRequest(
          parent=parent_work_unit_name,
          test_result=test_result_pb2.TestResult(
              test_id_structured=common_pb2.TestIdentifier(
                  module_name=module_name,
                  fine_name=class_name,
                  case_name=method_name,
                  module_scheme=MOBLY_SCHEME,
                  module_variant=common_pb2.Variant(),
              ),
              result_id=test_result_id,
              status_v2=test_status.value,
              start_time=timestamp_pb2.Timestamp(
                seconds=start_time_nanoseconds // NANOSECONDS_MULTIPLIER,
                nanos=start_time_nanoseconds % NANOSECONDS_MULTIPLIER,
              ),
              duration=duration_pb2.Duration(
                  seconds=duration_nanoseconds // NANOSECONDS_MULTIPLIER,
                  nanos=duration_nanoseconds % NANOSECONDS_MULTIPLIER,
              ),
              summary_html=summary_html,
              **req_kwargs,
          ),
          request_id=str(uuid.uuid4()),
      )
      create_tr_resp = client.create_test_result(
          create_tr_req,
          parent_update_token,
      )
      logging.debug(
          "Successfully created test result: %s",
          create_tr_resp.name
      )

  def batch_create_test_artifacts(
      self,
      work_unit_name: str,
      update_token: str,
      module_name: str,
      class_name: str,
      method_name: str,
      test_result_id: str,
      artifact_paths: list[str],
  ) -> None:
    if not artifact_paths:
      raise ValueError("No artifact paths provided.")

    for artifact_path in artifact_paths:
      artifact_size = os.path.getsize(artifact_path)
      if artifact_size > MAX_ARTIFACT_STREAMING_SIZE_BYTES:
        logging.warning(
            'Skipping artifact "%s" because its size %d exceeds %d.',
            artifact_path,
            artifact_size,
            MAX_ARTIFACT_STREAMING_SIZE_BYTES,
        )
        continue

      if artifact_size > MAX_ARTIFACT_GRPC_SIZE_BYTES:
        logging.debug(
            'Uploading artifact "%s" by streaming because its size %d exceeds %d.',
            artifact_path,
            artifact_size,
            MAX_ARTIFACT_GRPC_SIZE_BYTES,
        )
        self.stream_artifact(
            work_unit_name,
            update_token,
            module_name,
            class_name,
            method_name,
            test_result_id,
            os.path.basename(artifact_path),
            artifact_path,
        )
        continue

      logging.debug(
          'Uploading artifact "%s" by gRPC because its size %d is small.',
          artifact_path,
          artifact_size,
      )
      try:
        with self._recorder_client as client, open(artifact_path, "rb") as f:
          create_artifact_req = recorder_pb2.CreateArtifactRequest(
              artifact=artifact_pb2.Artifact(
                  artifact_id=os.path.basename(artifact_path),
                  content_type=utils.get_mime_type(artifact_path),
                  test_id_structured=common_pb2.TestIdentifier(
                      module_name=module_name,
                      fine_name=class_name,
                      case_name=method_name,
                      module_scheme=MOBLY_SCHEME,
                      module_variant=common_pb2.Variant(),
                  ),
                  result_id=test_result_id,
                  contents=f.read(),
              ),
          )
          batch_create_artifact_req = recorder_pb2.BatchCreateArtifactsRequest(
              parent=work_unit_name,
              requests=[create_artifact_req],
              request_id=str(uuid.uuid4()),
          )
          create_artifact_resp = client.batch_create_artifacts(
              batch_create_artifact_req, update_token
          )
          logging.debug(
              "Successfully created artifacts: %s",
              create_artifact_resp,
          )
      except grpc.RpcError as e:
        logging.error("Failed to create artifact: %s", e)

  def finalize_work_unit(
      self,
      work_unit_name: str,
      work_unit_update_token: str,
  ) -> None:
    with self._recorder_client as client:
      finalize_work_unit_req = recorder_pb2.FinalizeWorkUnitRequest(
          name=work_unit_name,
          state=work_unit_pb2.WorkUnit.State.SUCCEEDED,
      )
      finalized_work_unit_resp = client.finalize_work_unit(
          finalize_work_unit_req, work_unit_update_token
      )
      logging.debug(
          "Successfully finalized work unit: %s",
          finalized_work_unit_resp.name,
      )

  def stream_artifact(
      self,
      work_unit_name: str,
      update_token: str,
      module_name: str,
      class_name: str,
      method_name: str,
      test_result_id: str,
      artifact_id: str,
      artifact_path: str,
  ):
    """Streams an artifact to ResultDB."""
    hash_sha256 = hashlib.sha256()
    with open(artifact_path, "rb") as f:
      for chunk in iter(lambda: f.read(4096), b""):
        hash_sha256.update(chunk)
    content_hash = "sha256:" + hash_sha256.hexdigest()

    headers = {
        "Content-Length": str(os.path.getsize(artifact_path)),
        "Content-Hash": content_hash,
        "Content-Type": utils.get_mime_type(artifact_path),
        "Update-Token": update_token,
        "Artifact-ID": artifact_id,
        "Result-ID": test_result_id,
        "Test-Module-Name": urllib_parse.quote(module_name),
        "Test-Module-Scheme": urllib_parse.quote(MOBLY_SCHEME),
        "Test-Fine-Name": urllib_parse.quote(class_name),
        "Test-Case-Name": urllib_parse.quote(method_name),
    }

    url = f"https://{self.config.streaming_host}/{work_unit_name}/artifacts"
    try:
      with open(artifact_path, "rb") as f:
        response = requests.post(url, data=f, headers=headers)
        if response.status_code == 201:
          logging.debug("Successfully streamed artifact: %s", artifact_id)
          return True
        else:
          logging.error(
              "Failed to stream artifact: %s, status: %s, response: %s",
              artifact_id,
              response.status_code,
              response.text,
          )
          return False
    except requests.exceptions.RequestException as e:
      logging.error("Error streaming artifact %s: %s", artifact_id, e)
      return False
