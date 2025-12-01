import dataclasses
import mimetypes

DEFAULT_ARTIFACT_MIME_TYPE = "application/octet-stream"
TEXT_MIME_TYPE = "text/plain"
YAML_MIME_TYPE = "text/x-yaml"


def init_mime_types():
  """Initializes the MIME types for unusual file extensions."""
  mimetypes.add_type(TEXT_MIME_TYPE, ".info")
  mimetypes.add_type(TEXT_MIME_TYPE, ".debug")
  mimetypes.add_type(TEXT_MIME_TYPE, ".log")
  mimetypes.add_type(TEXT_MIME_TYPE, ".textproto")
  mimetypes.add_type(YAML_MIME_TYPE, ".yaml")
  mimetypes.add_type(YAML_MIME_TYPE, ".yml")


def get_mime_type(file_path: str) -> str:
  """Gets the MIME type of the file."""
  mime_type, _ = mimetypes.guess_type(file_path)
  return mime_type or DEFAULT_ARTIFACT_MIME_TYPE


@dataclasses.dataclass
class Config:
  """Configuration for the ResultDB uploader."""
  name: str
  is_prod: bool
  data_realm: str
  streaming_host: str
  test_result_url_prefix: str


PROD_CONFIG = Config(
    name="prod",
    is_prod=True,
    data_realm="prod",
    streaming_host="results.api.luci.app",
    test_result_url_prefix="https://ci.chromium.org/ui/test-investigate/invocations/",
)

DEV_CONFIG = Config(
    name="dev",
    is_prod=False,
    data_realm="test",
    streaming_host="staging.results.api.luci.app",
    test_result_url_prefix="https://luci-milo-dev.appspot.com/ui/test-investigate/invocations/",
)
