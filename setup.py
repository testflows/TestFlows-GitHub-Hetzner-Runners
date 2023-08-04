#!/usr/bin/env python3
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
from setuptools import setup

with open("README.rst", "r", encoding="utf-8") as fd:
    long_description = fd.read()


setup(
    name="testflows.github.runners",
    version="__VERSION__",
    description="Autoscaling GitHub Actions Runners Using Hetzner Cloud ",
    author="Vitaliy Zakaznikov",
    author_email="vzakaznikov@testflows.com",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/testflows/github-runners",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    license="Apache-2.0",
    packages=[
        "testflows.github.runners",
        "testflows.github.runners.bin",
        "testflows.github.runners.scripts",
        "testflows.github.runners.scripts.deploy",
    ],
    package_data={
        "testflows.github.runners.scripts": ["*.sh"],
        "testflows.github.runners.scripts.deploy": ["*.sh"],
        "testflows.github.runners.bin": ["github-runners"],
    },
    scripts=["testflows/github/runners/bin/github-runners"],
    zip_safe=False,
    install_requires=[
        "PyGithub==1.59.0",
        "hcloud==1.26.0",
        "requests-cache==1.1.0",
        "PyYAML==6.0",
    ],
    extras_require={"dev": []},
)
