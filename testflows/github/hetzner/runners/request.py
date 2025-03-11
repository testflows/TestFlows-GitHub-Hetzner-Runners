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
import json
import time
import random

from http.client import HTTPResponse
from urllib.request import urlopen, Request, HTTPError
from . import __version__ as project_version, __name__ as project_name

user_agent = f"{project_name}/{project_version}"


class RetryableError(Exception):
    """Error that can be retried"""

    pass


def should_retry(exc):
    """Determine if an error should be retried"""
    if isinstance(exc, HTTPError):
        # Retry on server errors (500s)
        if 500 <= exc.getcode() < 600:
            return True
        # Retry on rate limits (429)
        if exc.getcode() == 429:
            return True
        # Retry on service unavailable
        if exc.getcode() == 503:
            return True
    return False


def request(
    url,
    headers=None,
    data=None,
    format=None,
    encoding="utf-8",
    timeout=60,
    process_error=True,
    method=None,
    max_retries=5,
    initial_retry_delay=1,
):
    """Perform URL request with retries and exponential backoff."""
    if headers is None:
        headers = {}

    headers["User-Agent"] = user_agent
    retry_count = 0
    retry_delay = initial_retry_delay

    while True:
        try:
            r = Request(url, headers=headers, data=data, method=method)
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
                    max_retries=max_retries,
                    initial_retry_delay=initial_retry_delay,
                )

            if should_retry(exc) and retry_count < max_retries:
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, 0.1) * retry_delay
                sleep_time = retry_delay + jitter

                # If rate limited and Retry-After header is present, use that
                if exc.getcode() == 429 and "Retry-After" in exc.headers:
                    try:
                        sleep_time = float(exc.headers["Retry-After"])
                    except Exception:
                        pass

                time.sleep(sleep_time)
                retry_count += 1
                retry_delay *= 2  # Exponential backoff
                continue

            raise

        except Exception as exc:
            raise
