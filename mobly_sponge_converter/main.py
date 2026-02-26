import argparse
import logging
import pathlib
import sys
from sponge_artifact_creator import target_level_artifact_creator


def main():
  """
  Entry point to convert Mobly test results to Sponge artifacts.
  src dir should look like:
  ├── MakeToastTest
  ├── test_log.DEBUG
  ├── test_log.INFO
  └── test_summary.yaml

  dst dir will look like:
  ├── test.log
  ├── test.xml
  ├── test_components.pb
  after running this script.
  """
  args = argparse.ArgumentParser()
  args.add_argument(
      "--src-dir", required=True, help="Mobly test results directory."
  )
  args.add_argument(
      "--dst-dir", required=True, help="Sponge artifacts output directory."
  )
  args = args.parse_args()

  try:
    creator = target_level_artifact_creator.TargetLevelArtifactCreator(
        src_dir=pathlib.Path(args.src_dir),
        dst_dir=pathlib.Path(args.dst_dir),
    )
    creator.create_artifacts()
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to create Sponge artifacts: %s", e)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main())
