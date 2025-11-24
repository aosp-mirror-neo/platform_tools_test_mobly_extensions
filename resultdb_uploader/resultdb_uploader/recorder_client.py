"""Client for interacting with the ResultDB gRPC service."""

import json
import grpc

from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import invocation_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import recorder_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import recorder_pb2_grpc
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import resultdb_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import root_invocation_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import test_result_pb2
from tools.test.mobly_extensions.resultdb_uploader.proto.resultdb import work_unit_pb2

# Default host and port for ResultDB
_PROD_HOST = 'results.api.luci.app'
_STAGING_HOST = 'staging.results.api.luci.app'
_DEFAULT_PORT = 443
_GRPC_TIMEOUT_SECONDS = 120  # 2 minutes
_MAX_MESSAGE_LENGTH = 10 * 1024 * 1024  # 100MB
_UPDATE_TOKEN_METADATA_KEY = 'update-token'
_INCLUSION_TOKEN_METADATA_KEY = 'inclusion-token'


class RecorderClient:
  """A client for interacting with the ResultDB service.

  Usage example:
    channel_creds = grpc.composite_channel_credentials(
        grpc.ssl_channel_credentials(),
        grpc.access_token_call_credentials(access_token),
    )
    with RecorderClient(channel_creds=channel_creds) as client:
        invocation, update_token = client.create_invocation(...)
        ...
    Note that `channel_creds` needs to be appropriately configured for
    authentication.

    Important: This client does not automatically refresh access tokens. If the
    access token provided via `channel_creds` expires, the caller is responsible
    for obtaining a new token and creating a new `RecorderClient` instance with
    the new credentials.
  """
  def __init__(
      self,
      channel_creds: grpc.ChannelCredentials,
      is_prod: bool = False,
  ):
    """Initializes the RecorderClient.

    Args:
      channel_creds: gRPC channel credentials for authentication.
      is_prod: Whether to use the production host. Defaults to False.
    """
    host = _PROD_HOST if is_prod else _STAGING_HOST
    self._target = f'{host}:{_DEFAULT_PORT}'
    self._channel_creds = channel_creds
    self._channel = None
    self._recorder_stub = None

  def __enter__(self):
    service_config = {
        'methodConfig': [{
            'name': [{}],  # Apply retry to all methods
            'retryPolicy': {
                'maxAttempts': 5,
                'initialBackoff': '1s',
                'maxBackoff': '32s',
                'backoffMultiplier': 2,
                'retryableStatusCodes': [
                    'INTERNAL',
                    'UNKNOWN',
                    'UNAVAILABLE',
                ],
            },
        }]
    }
    options = [
        ('grpc.enable_retries', 1),
        ('grpc.service_config', json.dumps(service_config)),
        ('grpc.max_send_message_length', _MAX_MESSAGE_LENGTH),
        ('grpc.max_receive_message_length', _MAX_MESSAGE_LENGTH),
    ]
    self._channel = grpc.secure_channel(
        self._target, self._channel_creds, options=options
    )
    self._recorder_stub = recorder_pb2_grpc.RecorderStub(self._channel)
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    if self._channel:
      self._channel.close()

  def _get_recorder_stub(self) -> recorder_pb2_grpc.RecorderStub:
    if not self._recorder_stub:
      raise ConnectionError(
          'Client not connected. Use "with RecorderClient(...) as client:"'
          ' syntax.'
      )
    return self._recorder_stub

  def create_root_invocation(
      self,
      request: recorder_pb2.CreateRootInvocationRequest,
  ) -> tuple[recorder_pb2.CreateRootInvocationResponse, str]:
    """Creates a new root invocation and its root work unit.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20CreateRootInvocation%22

    Args:
      request: The CreateRootInvocationRequest proto.

    Returns:
      A tuple containing the CreateRootInvocationResponse and the update token.
    """
    call_future = self._get_recorder_stub().CreateRootInvocation.future(
        request, timeout=_GRPC_TIMEOUT_SECONDS
    )
    response = call_future.result()
    metadata = call_future.initial_metadata()
    update_token = ''
    for key, value in metadata:
      if key == _UPDATE_TOKEN_METADATA_KEY:
        update_token = value
        break
    return response, update_token

  def update_root_invocation(
      self,
      request: recorder_pb2.UpdateRootInvocationRequest,
      update_token: str,
  ) -> root_invocation_pb2.RootInvocation:
    """Updates an existing non-final RootInvocation.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20UpdateRootInvocation%22

    Args:
      request: The UpdateRootInvocationRequest proto.
      update_token: The update token for the root invocation.

    Returns:
      The updated RootInvocation.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().UpdateRootInvocation(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def get_root_invocation(
      self,
      request: resultdb_pb2.GetRootInvocationRequest,
      update_token: str,
  ) -> root_invocation_pb2.RootInvocation:
    """Gets an existing RootInvocation.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20GetRootInvocation%22

    Args:
      request: The GetRootInvocationRequest proto.
      update_token: The update token for the root invocation.

    Returns:
      The RootInvocation.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().GetRootInvocation(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def create_work_unit(
      self,
      request: recorder_pb2.CreateWorkUnitRequest,
      update_token: str,
  ) -> tuple[work_unit_pb2.WorkUnit, str]:
    """Creates a new work unit inside a parent work unit.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20CreateWorkUnit%22

    Args:
      request: The CreateWorkUnitRequest proto.
      update_token: The update token for the parent work unit.

    Returns:
      A tuple containing the created WorkUnit and the update token.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    call_future = self._get_recorder_stub().CreateWorkUnit.future(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )
    work_unit = call_future.result()
    metadata = call_future.initial_metadata()
    update_token = ''
    for key, value in metadata:
      if key == _UPDATE_TOKEN_METADATA_KEY:
        update_token = value
        break
    return work_unit, update_token

  def batch_create_work_units(
      self, request: recorder_pb2.BatchCreateWorkUnitsRequest, update_token: str
  ) -> recorder_pb2.BatchCreateWorkUnitsResponse:
    """Batch creates new work units in a batch. This is a blocking call.

    This work units created can belong to different parent work units, but the
    parent work units must share the same update token.

    Please see
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22message%20BatchCreateWorkUnitsRequest%22
    for details.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchCreateWorkUnits%22

    Args:
      request: The BatchCreateWorkUnitsRequest proto.
      update_token: The update token for the parent work unit(s).

    Returns:
      The BatchCreateWorkUnitsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchCreateWorkUnits(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def update_work_unit(
      self, request: recorder_pb2.UpdateWorkUnitRequest, update_token: str
  ) -> work_unit_pb2.WorkUnit:
    """Updates an existing non-final work unit.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20UpdateWorkUnit%22

    Args:
      request: The UpdateWorkUnitRequest proto.
      update_token: The update token for the work unit.

    Returns:
      The updated WorkUnit.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().UpdateWorkUnit(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def get_work_unit(
      self, request: resultdb_pb2.GetWorkUnitRequest, update_token: str
  ) -> work_unit_pb2.WorkUnit:
    """Gets an existing work unit.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20GetWorkUnit%22

    Args:
      request: The GetWorkUnitRequest proto.
      update_token: The update token for the work unit.

    Returns:
      The WorkUnit.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().GetWorkUnit(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def batch_get_work_units(
      self, request: resultdb_pb2.BatchGetWorkUnitsRequest, update_token: str
  ) -> resultdb_pb2.BatchGetWorkUnitsResponse:
    """Batch gets existing work units in a batch.

    The work units need to share the same update token.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchGetWorkUnits%22

    Args:
      request: The BatchGetWorkUnitsRequest proto.
      update_token: The update token for the work units.

    Returns:
      The BatchGetWorkUnitsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchGetWorkUnits(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def batch_update_work_units(
      self, request: recorder_pb2.BatchUpdateWorkUnitsRequest, update_token: str
  ) -> recorder_pb2.BatchUpdateWorkUnitsResponse:
    """Batch updates existing non-final work units in a batch.

    The work units need to share the same update token.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchUpdateWorkUnits%22

    Args:
      request: The BatchUpdateWorkUnitsRequest proto.
      update_token: The update token for the work units.

    Returns:
      The BatchUpdateWorkUnitsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchUpdateWorkUnits(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def finalize_work_unit(
      self, request: recorder_pb2.FinalizeWorkUnitRequest, update_token: str
  ) -> work_unit_pb2.WorkUnit:
    """Marks the given work unit as final and begins the process of transitioning it to the state FINALIZED.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20FinalizeWorkUnit%22

    Args:
      request: The FinalizeWorkUnitRequest proto.
      update_token: The update token for the work unit.

    Returns:
      The finalized WorkUnit.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().FinalizeWorkUnit(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def batch_finalize_work_units(
      self,
      request: recorder_pb2.BatchFinalizeWorkUnitsRequest,
      update_token: str,
  ) -> recorder_pb2.BatchFinalizeWorkUnitsResponse:
    """Batch marks a set of WorkUnits as final and begins the process of transitioning them to the state FINALIZED.

    The work units need to share the same update token.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchFinalizeWorkUnits%22

    Args:
      request: The BatchFinalizeWorkUnitsRequest proto.
      update_token: The update token for the work units.

    Returns:
      The BatchFinalizeWorkUnitsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchFinalizeWorkUnits(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def delegate_work_unit_inclusion(
      self,
      request: recorder_pb2.DelegateWorkUnitInclusionRequest,
      update_token: str,
  ) -> str:
    """Mints an 'inclusion token' that proves the current caller has permission to include work units from a given realm.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20DelegateWorkUnitInclusion%22

    Args:
      request: The DelegateWorkUnitInclusionRequest proto.
      update_token: The update token for the work unit.

    Returns:
      The inclusion token.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    call_future = self._get_recorder_stub().DelegateWorkUnitInclusion.future(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )
    call_future.result()
    metadata = call_future.initial_metadata()
    inclusion_token = ''
    for key, value in metadata:
      if key == _INCLUSION_TOKEN_METADATA_KEY:
        inclusion_token = value
        break
    return inclusion_token

  def create_invocation(
      self,
      request: recorder_pb2.CreateInvocationRequest,
  ) -> tuple[invocation_pb2.Invocation, str]:
    """Creates a new invocation. This is a blocking call.

    LEGACY ONLY: Please do not use for new code. Instead, use
    create_root_invocation() or create_work_unit() depending on the purpose.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20CreateInvocation%22

    Args:
      request: The CreateInvocationRequest proto.

    Returns:
      A tuple containing the created Invocation and the update token.
    """
    call_future = self._get_recorder_stub().CreateInvocation.future(
        request, timeout=_GRPC_TIMEOUT_SECONDS
    )
    invocation = call_future.result()
    metadata = call_future.initial_metadata()
    update_token = ''
    for key, value in metadata:
      if key == _UPDATE_TOKEN_METADATA_KEY:
        update_token = value
        break
    return invocation, update_token

  def batch_create_invocations(
      self, request: recorder_pb2.BatchCreateInvocationsRequest
  ) -> recorder_pb2.BatchCreateInvocationsResponse:
    """Creates multiple invocations in a single RPC. This is a blocking call.

    LEGACY ONLY: Please do not use for new code. Instead, use
    batch_create_work_units().

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchCreateInvocations%22

    Args:
      request: The BatchCreateInvocationsRequest proto.

    Returns:
      The BatchCreateInvocationsResponse proto.
    """
    return self._get_recorder_stub().BatchCreateInvocations(
        request, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def update_invocation(
      self, request: recorder_pb2.UpdateInvocationRequest, update_token: str
  ) -> invocation_pb2.Invocation:
    """Updates an existing non-finalized invocation. This is a blocking call.

    LEGACY ONLY: Please do not use for new code. Instead, use
    update_root_invocation() or update_work_unit().

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20UpdateInvocation%22

    Args:
      request: The UpdateInvocationRequest proto.
      update_token: The update token for the invocation.

    Returns:
      The updated Invocation.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().UpdateInvocation(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def finalize_invocation(
      self, request: recorder_pb2.FinalizeInvocationRequest, update_token: str
  ) -> invocation_pb2.Invocation:
    """Transitions the given invocation to the state FINALIZED.

    This is a blocking call.

    LEGACY ONLY: Please do not use for new code. Instead, use
    finalize_root_invocation() or finalize_work_unit().

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20FinalizeInvocation%22

    Args:
      request: The FinalizeInvocationRequest proto.
      update_token: The update token for the invocation.

    Returns:
      The finalized Invocation.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().FinalizeInvocation(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def update_included_invocations(
      self,
      request: recorder_pb2.UpdateIncludedInvocationsRequest,
      update_token: str,
  ) -> None:
    """Updates inclusions for a non-finalized invocation.

    This is a blocking call.

    LEGACY ONLY: Please do not use for new code. Instead, use
    create_work_unit() which handles inclusion during creation.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20UpdateIncludedInvocations%22

    Args:
      request: The UpdateIncludedInvocationsRequest proto.
      update_token: The update token for the parent invocation.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    self._get_recorder_stub().UpdateIncludedInvocations(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def create_test_result(
      self, request: recorder_pb2.CreateTestResultRequest, update_token: str
  ) -> test_result_pb2.TestResult:
    """Appends a test result to an active invocation.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20CreateTestResult%22

    Args:
      request: The CreateTestResultRequest proto.
      update_token: The update token for the invocation.

    Returns:
      The created TestResult.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().CreateTestResult(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def batch_create_test_results(
      self,
      request: recorder_pb2.BatchCreateTestResultsRequest,
      update_token: str,
  ) -> recorder_pb2.BatchCreateTestResultsResponse:
    """Atomically appends a batch of test results to an active invocation.

    This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchCreateTestResults%22

    Args:
      request: The BatchCreateTestResultsRequest proto.
      update_token: The update token for the invocation.

    Returns:
      The BatchCreateTestResultsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchCreateTestResults(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )

  def batch_create_artifacts(
      self, request: recorder_pb2.BatchCreateArtifactsRequest, update_token: str
  ) -> recorder_pb2.BatchCreateArtifactsResponse:
    """Creates multiple artifacts. This is a blocking call.

    Source:
    https://source.corp.google.com/piper///depot/google3/third_party/golang/luci_go/resultdb/proto/v1/resultpb/recorder.proto?q=%22rpc%20BatchCreateArtifacts%22

    Args:
      request: The BatchCreateArtifactsRequest proto.
      update_token: The update token for the invocation.

    Returns:
      The BatchCreateArtifactsResponse proto.
    """
    metadata = [(_UPDATE_TOKEN_METADATA_KEY, update_token)]
    return self._get_recorder_stub().BatchCreateArtifacts(
        request, metadata=metadata, timeout=_GRPC_TIMEOUT_SECONDS
    )