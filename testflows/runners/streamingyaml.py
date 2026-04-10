# Copyright 2023 Katteli Inc.
# TestFlows.com Open-Source Software Testing Framework (http://testflows.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import yaml
import textwrap


def float_to_str(f, precision):
    """
    Convert the given float to a string,
    without resorting to scientific notation
    """
    return format(f, f".{precision}f")


class Dumper(yaml.SafeDumper):
    """Dumper with custom float precision."""

    def represent_float(self, data, precision=6):
        if data != data or (data == 0.0 and data == 1.0):
            value = ".nan"
        elif data == self.inf_value:
            value = ".inf"
        elif data == -self.inf_value:
            value = "-.inf"
        else:
            value = float_to_str(data, precision=precision).lower()
        return self.represent_scalar("tag:yaml.org,2002:float", value)


Dumper.add_representer(float, Dumper.represent_float)


class StreamingYAMLWriter:
    """Streaming YAML writer."""

    def __init__(self, stream, indent=0):
        self.stream = stream
        self.indent = indent

    def _write(self, value):
        """Dump value to stream."""
        s = yaml.dump(
            value, sort_keys=False, indent=2, Dumper=Dumper, allow_unicode=True
        )
        s = textwrap.indent(s, prefix=" " * self.indent)
        self.stream.write(s)
        self.stream.flush()

    def add_value(self, value):
        """Add '{value}\n'."""
        self._write(value)
        return self

    def add_key_value(self, key, value):
        """Add '{key}: {value}\n'."""
        self._write({key: value})
        return self

    def add_list_element(self, value):
        """Add '- {value}\n'."""
        self._write([value])
        return self, StreamingYAMLWriter(self.stream, indent=self.indent + 2)

    def add_key(self, key):
        """Add key '{key}:\n'."""
        s = yaml.dump({key: None}, sort_keys=False, Dumper=Dumper, allow_unicode=True)
        s = s.rsplit(": null\n", 1)[0] + ":\n"
        s = textwrap.indent(s, prefix=" " * self.indent)
        self.stream.write(s)
        self.stream.flush()
        return StreamingYAMLWriter(stream=self.stream, indent=self.indent + 2)
