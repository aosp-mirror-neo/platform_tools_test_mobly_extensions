# Copyright 2019 Google Inc. All Rights Reserved.

"""Protobuf Python delimited parsing and writing APIs.

example usage:
    out = io.BytesIO()
    for msg in message_list:
      delimited_message.SerializeDelimitedTo(msg, out)

    input_bytes = io.BytesIO(out.getvalue())
    while delimited_message.ParseDelimitedFrom(msg, input_bytes):
      ...
"""

from google.protobuf import proto


# Deprecated. Please use serialize_length_prefixed in google.protobuf.proto
# instead.
def SerializeDelimitedTo(message, output):
  """Writes the size of the message as a varint and the serialized message.

  Writes the size of the message as a varint and then the serialized message.
  This allows more data to be written to the output after the message. Use
  Parse(Merge)DelimitedFrom to parse(or merge) messages written by this method.

  The output stream must be buffered, e.g. using
  https://docs.python.org/3/library/io.html#buffered-streams.

  Args:
    message: The protocol buffer message that should be serialized.
    output: BytesIO or custom buffered IO that data should be written to.

  Returns:
    None.
  """
  return proto.serialize_length_prefixed(message, output)


# Deprecated. Please use parse_length_prefixed in google.protobuf.proto
# instead.
def ParseDelimitedFrom(message_class, input_bytes):
  """Parse a message from input_bytes.

  Args:
    message_class: The protocol buffer message class that parser should parse.
    input_bytes: A buffered input.

  Returns:
    A parsed message if successful. None if input_bytes is at EOF.
  """
  return proto.parse_length_prefixed(message_class, input_bytes)
