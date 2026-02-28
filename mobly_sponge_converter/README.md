# Introduction

This module is an independently maintained fork of the Mobly Sponge converter (google3/testing/mobly/sponge/). Its primary function is to process Mobly test outputs and generate Sponge-compatible artifacts for uploads in the Android source tree.

## Usage

There are two ways to use this converter:

### As a Library

Integrate the conversion logic directly into your Python code. This is useful if you are programmatically generating Mobly results and need to produce Sponge artifacts as part of a larger script or tool.

**Soong Target Name:** `mobly_sponge_converter_lib`

**Example Import:**

```
from mobly_sponge_converter import mobly_sponge_converter
```

### As a Standalone Binary

Execute the converter as a command-line tool. This is suitable for post-processing Mobly output files (e.g., test_summary.yaml) to generate the necessary Sponge XML and artifact annotations.

**Soong Target Name:** `mobly_sponge_converter`

**Example Usage:**

```
mobly_sponge_converter
  --src-dir /tmp/test_mobly_sponge/mobly_logs/
  --dst-dir /tmp/test_mobly_sponge/sponge_artifacts/
```