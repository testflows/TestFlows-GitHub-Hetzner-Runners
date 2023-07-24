.. image:: https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/master/images/logo.png
   :width: 20%
   :target: https://testflows.com
   :alt: test bug

======================================================
Autoscaling GitHub Actions Runners Using Hetzner Cloud
======================================================

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/master/images/test-machine.png
   :width: 30%
   :alt: test machine

The **github-runners** service program starts and monitors queued up jobs for GitHub Actions workflows.
When a new job is queued up, it creates a new Hetzner Cloud server instance
that provides an ephemeral GitHub Actions runner. Each server instance is automatically
powered off when job completes and then powered off servers are
automatically deleted. Both **x64** and **arm64** runners are supported.

:❗Warning:
   This program is provided on "AS IS" basis without warranties or conditions of any kind. See LICENSE.
   Use it at your own risk. Manual monitoring is required to make sure server instances are cleaned up properly.

Costs depend on the server type, number of jobs and execution time. For each job a new server instance is created
to avoid any cleanup. Server instances are not shared between any jobs.

:✋ Note:
   Currently Hetzner Cloud server instances are billed on hourly basis. So a job that takes 1 min will be billed
   the same way as for a job that takes 59 minutes. Therefore, the minimal cost
   for any job is the cost of the server for 1 hour plus the cost for one public IPv4 address.

.. contents:: Read more about:
   :backlinks: top
   :depth: 4

--------
Features
--------

* cost efficient on-demand runners using Hetzner Cloud
* supports both x64 and ARM64 runners
* supports specifying custom runner types using job labels
* simple configuration

------------
Installation
------------

.. code-block:: bash

   pip3 install testflows.github.runners

------------
Quick Start
------------

Set environment variables corresponding to your GitHub repository and Hetzner Cloud project

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=vzakaznikov/github-runners
   export HETZNER_TOKEN=GJzdc...
   export HETZNER_SSH_KEY_NAME=user@user-node

and then start **github-runners** program

.. code-block:: bash

   github-runners

::

   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Logging in to Hetzner Cloud
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Logging in to GitHub
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Getting repository vzakaznikov/github-runners
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Creating scale up service
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Creating scale down service
   07/22/2023 08:20:38 PM   INFO   worker_2   create_server 🍀 Create server
   ...

or you can pass the required options inline as follows:

.. code-block:: bash

   github-runners --github-token <GITHUB_TOKEN> --github-repository <GITHUB_REPOSITORY> --hetzner-token <HETZNER_TOKEN> --hetzner-ssh-key <HEZNER_SSH_KEY>

-------------------------
Installation From Sources
-------------------------

For development, you can install from sources as follows:

.. code-block:: bash

   git clone https://github.com/testflows/Github-Runners.git
   ./package && ./install

-------------------
Basic Configuration
-------------------

By default, the program uses the following environment variables:

* **GITHUB_TOKEN**
* **GITHUB_REPOSITORY**
* **HETZNER_TOKEN**
* **HETZNER_SSH_KEY**

or you can specify these values using the following options:

* **--github-token**
* **--github-repository**
* **--hetzner-token**
* **--hetzner-ssh-key**

-----------------------
Running as a Service
-----------------------

You can run **github-runners** as a service. For this you will need to install it using the **root** user
or the **sudo** command.

.. code-block:: bash

   sudo pip3 install testflows.github.runners

After installation, you can use **service install** and **service uninstall** commands to install and
uninstall the service.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/github-runners
   export HETZNER_TOKEN=GJzdc...
   export HETZNER_SSH_KEY_NAME=user@user-node

   sudo github-runners service install

.. code-block:: bash

   sudo github-runners service uninstall

After installation, you can check the status of the server using the **service status** command.

.. code-block:: bash

   sudo github-runners service status

You can start and stop the service using the **service start** and **service stop** commands as follows:

.. code-block:: bash

   sudo github-runners service start
   sudo github-runners service stop

or using **service** system utility

.. code-block:: bash

   sudo service github-runners start
   sudo service github-runners stop

You can get the logs for the service using the **service logs** command.

.. code-block:: bash

   sudo github-runners service logs

which is equivalent to the following **journalctl** command:

.. code-block:: bash

   journalctl -u github-runners.service -f

------------------
Scaling Up Runners
------------------

The program scale up runners by looking for any jobs that have **queued** status.
For each such job, a corresponding Hetzner Cloud server instance is created with the following name:

::

   gh-actions-runner-{job.run_id}

The server is configured using default **setup** and **startup** scripts. The runner name is set
to be the same as the server name so that servers can deleted for any idle runner that for some reason
does not pick up a job for which it was created within the **max-idle-runner-time** period.

:Note:
   Given that the server name is fixed and specific for each *job.run_id*, if multiple `github-runners` are running in parallel then
   only 1 server will be created for a given `job` and any other attempts to create a server with the same name will be rejected
   by the Hetzner Cloud.

Also,

:Note:
   There is no guarantee that a given runner will pick the the job with the exact **run_id** that caused it to be created.
   This is expected and because for each **queued** job a unique runner will be created the number of runners will be
   equal the number of jobs and therefore under normal conditions all jobs will executed as expected.

Maximum Number of Runners
=========================

By default, the maximum number of runners and therefore server instances is not set and therefore is unlimited.
You can set the maximum number of runners using the **--max-runners** option.

.. code-blocks::bash

   github-runners --max-runners 10


New Server
==========

The new server is accessed using SSH. It boots up with the specified OS image and is configured using
the **setup** and **startup** scripts.

:Server Type:

   The default server type is **cx11**. However, a job **server-{hetzner-server-type}** label can be used to specify
   custom server type. Where the **{hetzner-server-type}** must be a valid Hetzner Cloud server type name such as *cx11*, *cpx21* etc.

   For example,

   .. code-block:: yaml

       runs-on: [self-hosted, server-cpx21]

:SSH Access:

   The server is configured to be accessed using *ssh* utility and the SSH key specified by name either using the **--hetzner-ssh-key**
   option or the **HETZNER_SSH_KEY** environment variable.

:OS Image:

   The server is configured to have the OS image specified by the **--hetzner-image** option or the **HETZNER_IMAGE**
   environment variable.

:Image Configuration:
   Each new server instance is configured using `setup <#the-setup-script>`_ and `startup <#the-start-up-script>`_ scripts.

The Setup Script
================

The **setup** script created and configures **runner** user that has **sudo** privileges.

:Setup:

   .. code-block:: bash

        set -x

        echo "Create and configure runner user"

        adduser runner --disabled-password --gecos ""
        echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
        addgroup wheel
        usermod -aG wheel runner
        usermod -aG sudo runner

The Start-up Script
===================

The **startup** script installs GitHub Actions runner. After installation it configures the runner to start in an *--ephemeral* mode.
The *--ephemeral* mode causes the runner to exit as soon as it completes a job. After the runner exits the server is powered off.

The x64 **startup** script installs and configures x64 version of the runner.

:x64:

   .. code-block:: bash

     set -x
     echo "Install runner"
     cd /home/runner
     curl -o actions-runner-linux-x64-2.306.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.306.0/actions-runner-linux-x64-2.306.0.tar.gz
     echo "b0a090336f0d0a439dac7505475a1fb822f61bbb36420c7b3b3fe6b1bdc4dbaa  actions-runner-linux-x64-2.306.0.tar.gz" | shasum -a 256 -c
     tar xzf ./actions-runner-linux-x64-2.306.0.tar.gz

     echo "Configure runner"
     ./config.sh --unattended --replace --url https://github.com/${GITHUB_REPOSITORY} --token ${GITHUB_RUNNER_TOKEN} --name "$(hostname)" --runnergroup "${GITHUB_RUNNER_GROUP}" --labels "${GITHUB_RUNNER_LABELS}" --work _work --ephemeral

     echo "Start runner"
     bash -c "screen -d -m bash -c './run.sh; sudo poweroff'"


The ARM64 **startup** script is similar to the x64 script but install an ARM64 version of the runner.

:ARM64:

   .. code-block:: bash

     set -x
     echo "Install runner"
     cd /home/runner

     curl -o actions-runner-linux-arm64-2.306.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.306.0/actions-runner-linux-arm64-2.306.0.tar.gz# Optional: Validate the hash
     echo "842a9046af8439aa9bcabfe096aacd998fc3af82b9afe2434ddd77b96f872a83  actions-runner-linux-arm64-2.306.0.tar.gz" | shasum -a 256 -c# Extract the installer
     tar xzf ./actions-runner-linux-arm64-2.306.0.tar.gz

     echo "Configure runner"
     ./config.sh --unattended --replace --url https://github.com/${GITHUB_REPOSITORY} --token ${GITHUB_RUNNER_TOKEN} --name "$(hostname)" --runnergroup "${GITHUB_RUNNER_GROUP}" --labels "${GITHUB_RUNNER_LABELS}" --work _work --ephemeral

     echo "Start runner"
     bash -c "screen -d -m bash -c './run.sh; sudo poweroff'"

--------------------
Scaling Down Runners
--------------------

Powered Off Servers
===================

The program scales down runners by first cleaning up powered off servers. The scale down service relies on the fact
that the `startup <#the-start-up-script>`_ script starts an ephemeral runner which will pick up only 1 job and then will power itself off after the job is complete.

The powered off servers are deleted after the **max-powered-off-time** interval which
can be specified using the **--max-powered-off-time** option which by default is set to *20* sec.

Idle Runners
============

The scale down service also monitors all the runners that have **idle** status and tries to delete any servers associated with such
runners if the runner is **idle** for more than the **max-idle-runner-time** period. This is needed in case a runner never gets a job
assigned to it and the server will stay in the power on state. This cycle relies on the fact that the runner's name
is the same as server's name. The **max-idle-runner-time** can be specified using the **--max-idle-runner-time** option which by default
is set to *120* sec.

Zombie Servers
==============

The scale down service will delete any zombie servers. A zombie server is defined as as any server that fails to register its runner within
the **max-runner-registration-time**. The **max-runner-registration-time** can be specified using the **--max-runner-registration-time** option
which by default is set to *60* sec.

---------------------------
Handling Failing Conditions
---------------------------

The program is designed to handle the following failing conditions:

:Server Never Registers a Runner:
   The server will remain in **running** state and should be reclaimed by the scale down service when it checks the actual runners registered for current servers.
   If it finds a server that is **running** but no runner is active for it it will be deleted after the **max-runner-registration-time** period.

:The *./config.sh* Command Fails:
   The behavior will be the same as for the **Server Never Registers a Runner** case above.

:The *./run.sh* Command Fails:
   The server will be powered off by the **startup** script and will be deleted by the scale down service.

:Creating Server For Queued Job Fails:
   If creation of the server fails for some reason then the scale up service will retry the operation in the next interval as the job's status will remain **queued**.

:Runner Never Gets a Job Assigned:
   If the runner never gets a job assigned, then the scale down service will remove the runner and delete its server after the **max-idle-runner-time** period.

:Runner Created With a Mismatched Labels:
   The behavior will be the same as for the **Runner Never Gets a Job Assigned** case above.

---------------
Program Options
---------------

The following options are supported:

* **-h, --help**
  show this help message and exit

* **-v, --version**
  show program's version number and exit

* **--license**
  show program's license and exit

* **--github-token GITHUB_TOKEN**
  GitHub token, default: *$GITHUB_TOKEN* environment variable

* **--github-repository GITHUB_REPOSITORY**
  GitHub repository, default: *$GITHUB_REPOSITORY* environment variable

* **--hetzner-token HETZNER_TOKEN**
  Hetzner Cloud token, default: *$HETZNER_TOKEN* environment variable

* **--ssh-key HETZNER_SSH_KEY**
  Hetzner Cloud SSH key name, default: *$HETZNER_SSH_KEY* environment variable

* **--image HETZNER_IMAGE**
  Hetzner Cloud server image name, default: ubuntu-20.04

* **-m count, --max-runners count**
  maximum number of active runners, default: unlimited

* **-w count, --workers count**
  number of concurrent workers, default: 10

* **--logger-config path**
  custom logger configuration file

* **--setup-script path**
  path to custom server setup script

* **--startup-x64-script path**
  path to custom server startup script

* **--startup-arm64-script path**
  path to custom ARM64 server startup script

* **--max-powered-off-time sec**
  maximum time after which a powered off server is deleted, default: *20* sec

* **--max-idle-runner-time sec**
  maximum time after which an idle runner is removed and its server deleted, default: *120* sec

* **--max-runner-registration-time**
  maximum time after which the server will be deleted if its runner is not registered with GitHub, default: *60* sec

* **--scale-up-interval sec**
  scale up service interval, default: *10* sec

* **--scale-down-interval sec**
  scale down service interval, default: *10* sec

* **--debug**
  enable debugging mode, default: *False*

* **commands:**
  
  * *command*

    * **service**
      service commands

      * **install**
        install service

      * **uninstall**
        uninstall service

      * **status**
        get service status

      * **logs**
        get service logs

      * **start**
        start service

      * **stop**
        stop service
