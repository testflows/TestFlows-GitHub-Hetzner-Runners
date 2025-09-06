#!/usr/bin/env python3
# Copyright 2023-2025 Katteli Inc.
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
    name="testflows.runners",
    version="__VERSION__",
    description="Autoscaling GitHub Actions Runners",
    author="Vitaliy Zakaznikov",
    author_email="vzakaznikov@testflows.com",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/testflows/runners",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    license="Apache-2.0",
    packages=[
        "testflows.runners",
        "testflows.runners.bin",
        "testflows.runners.config",
        "testflows.runners.scripts",
        "testflows.runners.scripts.deploy",
        "testflows.runners.dashboard",
        "testflows.runners.dashboard.panels",
        "testflows.runners.dashboard.metrics",
        "testflows.runners.providers",
        "testflows.runners.providers.hetzner",
        "testflows.runners.providers.aws",
        "testflows.runners.providers.azure",
        "testflows.runners.providers.gcp",
        "testflows.runners.providers.scaleway",
    ],
    package_data={
        "testflows.runners.config": ["*.json"],
        "testflows.runners.scripts": ["*.sh"],
        "testflows.runners.scripts.deploy": ["*.sh"],
        "testflows.runners.bin": ["tfs-runners"],
    },
    scripts=["testflows/runners/bin/tfs-runners"],
    zip_safe=False,
    install_requires=[
        "PyGithub==1.59.0",
        "hcloud==2.3.0",
        "requests-cache==1.1.0",
        "PyYAML==6.0.2",
        "prometheus_client==0.19.0",
        "streamlit==1.49.1",
        "psutil>=5.9.8",
    ],
    extras_require={"dev": []},
)
