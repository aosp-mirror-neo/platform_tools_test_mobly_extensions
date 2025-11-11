import logging
import uuid

import google.auth as auth
import google.auth.transport.grpc as auth_transport_grpc
import google.auth.transport.requests as auth_transport_requests
from google.protobuf import duration_pb2
from google.protobuf import timestamp_pb2
import grpc
import resultdb_uploader.recorder_client as recorder_client
import resultdb_uploader.test_status as resultdb_test_status
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
_RESULTDB_SCOPE = ["https://www.googleapis.com/auth/userinfo.email"]
NANOSECONDS_MULTIPLIER = 1_000_000_000


class ResultDBWriter:
  def __init__(self, is_prod: bool = False):
    self._recorder_client = recorder_client.RecorderClient(
        channel_creds=self._get_channel_creds(), is_prod=is_prod
    )

  def _get_channel_creds(self) -> grpc.ChannelCredentials:
    """Gets the channel credentials for the Recorder Client."""
    creds, _ = auth.default(scopes=_RESULTDB_SCOPE)
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
    try:
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
                streaming_export_state=root_invocation_pb2.RootInvocation.StreamingExportState.METADATA_FINAL
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
    except grpc.RpcError as e:
      logging.error("Failed to create root invocation: %s", e)
      raise e

  def create_work_unit(
      self,
      parent_work_unit_name: str,
      parent_update_token: str,
      work_unit_id: str,
      module_name: str,
  ) -> tuple[recorder_pb2.WorkUnit, str]:
    try:
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
    except grpc.RpcError as e:
      logging.error("Failed to create work unit: %s", e)
      raise e

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
  ) -> tuple[recorder_pb2.TestResult, str]:
    try:
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
        return create_tr_resp
    except grpc.RpcError as e:
      logging.error("Failed to create test result: %s", e)
      raise e

  def finalize_work_unit(
      self,
      work_unit_name: str,
      work_unit_update_token: str,
  ) -> tuple[recorder_pb2.WorkUnit, str]:
    try:
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
        return finalized_work_unit_resp
    except grpc.RpcError as e:
      logging.error("Failed to finalize work unit: %s", e)
      raise e
