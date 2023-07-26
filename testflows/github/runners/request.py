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
import json as json

from http.client import HTTPResponse
from urllib.request import urlopen, Request, HTTPError


def request(
    url,
    headers=None,
    data=None,
    format=None,
    encoding="utf-8",
    timeout=60,
    process_error=True,
):
    """Perform URL request."""
    if headers is None:
        headers = {}

    r = Request(url, headers=headers, data=data)

    try:
        with urlopen(r, timeout=timeout) as response:
            response: HTTPResponse = response

            data = response.read()
            if encoding:
                data = data.decode(encoding)
            if format == "json":
                data = json.loads(data)

            return data, response
    except HTTPError as exc:
        if not process_error:
            raise

        if exc.getcode() in (307, 308):
            # process 307 (Temporary Redirect") and 308 (Permanent Redirect)
            error_data = json.loads(exc.read().decode(encoding))
            return request(
                url=error_data["url"],
                headers=headers,
                data=data,
                format=format,
                encoding=encoding,
                timeout=timeout,
                process_error=False,
            )
