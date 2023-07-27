.. image:: https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/master/images/logo.png
   :width: 20%
   :target: https://testflows.com
   :alt: test bug

======================================================
Autoscaling GitHub Actions Runners Using Hetzner Cloud
======================================================

The **github-runners** service program starts and monitors queued up jobs for GitHub Actions workflows.
When a new job is queued up, it creates a new Hetzner Cloud server instance
that provides an ephemeral GitHub Actions runner. Each server instance is automatically
powered off when job completes and then powered off servers are
automatically deleted. Both **x64** and **arm64** runners are supported.

:❗Warning:
   This program is provided on "AS IS" basis without warranties or conditions of any kind. See LICENSE.
   Use it at your own risk. Manual monitoring is required to make sure server instances are cleaned up properly
   and costs are kept under control.

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
* self-contained and can deploy and manage itself on a cloud instance

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

   github-runners --github-token <GITHUB_TOKEN> --github-repository <GITHUB_REPOSITORY> --hetzner-token <HETZNER_TOKEN>

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

or you can specify these values using the following options:

* **--github-token**
* **--github-repository**
* **--hetzner-token**

------------------------------------
Specifying Maximum Number of Runners
------------------------------------
The default maximum number of runners is **10**. You can set a different value
based on your Hetzner Cloud limits using the **-m count, --max-runners count** option. For example,

.. code-block:: bash

   github-runners --max-runners 40

----------------------
Specifying Runner Type
----------------------

x64 Runners
============

The default server type is **cx11** which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.

:✋ Note:
   You can use **--default-type** option to set a different default server type.

You can specify different x64 server instance type by using the **type-{name}** runner label.
The **{name}** must be a valid `Hetzner Cloud server type <https://www.hetzner.com/cloud>`_
name such as *cx11*, *cpx21* etc.

For example, to use AMD, 3 vCPU, 4GB RAM shared-cpu x64 instance, you can define the **runs-on**
as follows:

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cpx21]

ARM64 Runners
==============

The default, the server type is **cx11**, which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.
Therefore, in order to use ARM64 runners you must specify ARM64 server instance type by using the **type-{name}** runner label.
The **{name}** must be a valid `ARM64 Hetzner Cloud server type <https://www.hetzner.com/cloud>`_
name such as *cax11*, *cax21* etc. which correspond to the Ampere Altra, 2 vCPU, 4GB RAM and
4 vCPU, 8GB RAM shared-cpu ARM64 instances respectively.

For example, to use Ampere Altra, 4 vCPU, 8GB RAM shared-cpu ARM64 instance, you must define the **runs-on**
as follows:

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cax21]

---------------------------
Specifying Runner Location
---------------------------

By default, the default location of the server where the runner will be running is not specified. You can use the **--default-location**
option to force specific default server location.

You can also use the **in-{name}** runner label to specify server location for a specific job. Where **{name}** must be a valid
`Hetzner Cloud location <https://docs.hetzner.com/cloud/general/locations/>`_ name such as *ash* for US, Ashburn, VA or
*fsn1* for Germany, Falkenstein.

For example,

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cx11, in-ash]


-----------------------
Specifying Runner Image
-----------------------

By default, the default image of the server for the runner is **ubuntu-22.04**. You can use the **--default-image**
option to force specific default server image.

You can also use the **image-{type}-{name}** runner label to specify server image for a specific job. Where the **{name}** must be a valid
Hetzner Cloud image such as *ubuntu-22.04* or *ubuntu-20.04*, and the **{type}** is either *system*, *snapshot*, *backup*, or *app*.

For example,

:ubuntu-20.04:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-system-ubuntu-20.04]


:docker-ce app:
   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-app-docker-ce]

:snapshot:
   For snapshots, specify **description** as the name. Snapshot descriptions
   must be unique.

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-snapshot-snapshot_description]

--------------------------------------------
Specifying Custom Runner Server Setup Script
--------------------------------------------

You can specify custom runner server setup script using the **--setup-script** option.

For example,

:custom_setup.sh:
   .. code-block:: bash

      #!/bin/bash
      set -x
      echo "Create and configure ubuntu user"
      adduser ubuntu --disabled-password --gecos ""
      echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
      addgroup wheel
      addgroup docker
      usermod -aG wheel ubuntu
      usermod -aG sudo ubuntu
      usermod -aG docker ubuntu
      # custom setup
      apt-get -y update
      apt-get -y install ca-certificates curl gnupg lsb-release python3-pip git unzip

:command:
   .. code-block:: bash

      github-runners --setup-script ./custom_setup.sh

-------
SSH Key
-------

All server instances that are created are accessed via SSH using the **ssh** utility and therefore you must provide a valid SSH key
using the **--ssh-key** option. If the **--ssh-key** option is no specified, then the *~/.ssh/id_rsa.pub* default key path will be used.

The SSH key will be automatically added to your project using the MD5 hash of the public key as the SSH key name.

:❗Warning:
   Given that each new SSH key is automatically added to your Hetzner project, you must manually delete them when no longer needed.

Most GitHub users already have an SSH key associated with the account. If you want to know how to add an SSH key, see `Adding a new SSH key to your GitHub account    <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>`_ article.

Generating New SSH Key
=======================

If you need to generate a new SSH key, see `Generating a new SSH key and adding it to the ssh-agent <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`_ article.

Cloud Deployment
================

If you are deploying the **github-runners** program as a cloud service using the **github-runners <options> cloud deploy** command, then
after provisoning a new cloud server instance that will host the **github-runners** service, a new SSH key will be
auto-generated to access the runners. The auto-generated key will be placed in */home/runner/.ssh/id_rsa*, where **runner**
is the user under which the **github-runners** service runs on the cloud instance. The auto-generated SSH key will be automatically
added to your project using the MD5 hash of the public key as the SSH key name.

-----------------------
Running as a Service
-----------------------

You can run **github-runners** as a service.

:✋ Note:
   In order to install the service, the user that installed the module must have **sudo** privileges.

Installing and Uninstalling
===========================

After installation, you can use **service install** and **service uninstall** commands to install and
uninstall the service.

:✋ Note:
   The options that are passed to the **github-runners <options> service install** command
   will be the same options with which the service will be executed.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/github-runners
   export HETZNER_TOKEN=GJzdc...

   github-runners service install

The **/etc/systemd/system/github-runners.service** file is created with the following content.

:✋ Note:
   The service will use the *User* and the *Group* of the user executing the program.


:/etc/systemd/system/github-runners.service:

   ::

      [Unit]
      Description=Autoscaling GitHub Actions Runners
      After=multi-user.target
      [Service]
      User=1000
      Group=1000
      Type=simple
      Restart=always
      Environment=GITHUB_TOKEN=ghp_...
      Environment=GITHUB_REPOSITORY=testflows/github-runners
      Environment=HETZNER_TOKEN=GJ..
      ExecStart=/home/user/.local/lib/python3.10/site-packages/testflows/github/runners/bin/github-runners --workers 10 --max-powered-off-time 20 --max-idle-runner-time 120 --max-runner-registration-time 60 --scale-up-interval 10 --scale-down-interval 10
      [Install]
      WantedBy=multi-user.target

Modifying Program Options
=========================

If you want to modify service program options you can stop the service,
edit the **/etc/systemd/system/github-runners.service** file by hand, then reload service daemon,
and start the service back up.

.. code-block:: bash

   github-runners service stop
   sudo vim /etc/systemd/system/github-runners.service
   sudo systemctl daemon-reload
   github-runners service start


Checking Status
================

After installation, you can check the status of the service using the **service status** command.

.. code-block:: bash

   github-runners service status:

:service status:

   ::

      ● github-runners.service - Autoscaling GitHub Actions Runners
           Loaded: loaded (/etc/systemd/system/github-runners.service; enabled; vendor preset: enabled)
           Active: active (running) since Mon 2023-07-24 14:38:33 EDT; 1h 31min ago
         Main PID: 66188 (python3)
            Tasks: 3 (limit: 37566)
           Memory: 28.8M
              CPU: 8.274s
           CGroup: /system.slice/github-runners.service
                   └─66188 python3 /usr/local/bin/github-runners --workers 10 --max-powered-off-time 20 --max-idle-runner-time 120 --max->

      Jul 24 14:38:33 user-node systemd[1]: Started Autoscaling GitHub Actions Runners.
      Jul 24 14:38:33 user-node github-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Logging in to Hetzner >
      Jul 24 14:38:33 user-node github-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Logging in to GitHub
      Jul 24 14:38:33 user-node github-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Getting repository vza>
      Jul 24 14:38:33 user-node github-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Creating scale up serv>
      Jul 24 14:38:33 user-node github-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Creating scale down se>
      lines 1-16/16 (END)

Manual Start and Stop
=====================

You can start and stop the service using the **service start** and **service stop** commands as follows:

.. code-block:: bash

   github-runners service start
   github-runners service stop

or using **service** system utility

.. code-block:: bash

   sudo service github-runners start
   sudo service github-runners stop

Checking Logs
=============

You can get the logs for the service using the **service logs** command.

Use **-f, --follow** option to follow logs journal.

.. code-block:: bash

   github-runners service logs -f

:followed service log:

   ::

      sudo github-runners service logs
      Jul 24 16:12:14 user-node systemd[1]: Stopping Autoscaling GitHub Actions Runners...
      Jul 24 16:12:14 user-node systemd[1]: github-runners.service: Deactivated successfully.
      Jul 24 16:12:14 user-node systemd[1]: Stopped Autoscaling GitHub Actions Runners.
      Jul 24 16:12:14 user-node systemd[1]: github-runners.service: Consumed 8.454s CPU time.
      Jul 24 16:12:17 user-node systemd[1]: Started Autoscaling GitHub Actions Runners.
      Jul 24 16:12:18 user-node github-runners[74176]: 07/24/2023 04:12:18 PM   INFO MainThread            main 🍀 Logging in to Hetzner Cloud
      Jul 24 16:12:18 user-node github-runners[74176]: 07/24/2023 04:12:18 PM   INFO MainThread            main 🍀 Logging in to GitHub
      Jul 24 16:12:18 user-node github-runners[74176]: 07/24/2023 04:12:18 PM   INFO MainThread            main 🍀 Getting repository vzakaznikov/github-runners
      Jul 24 16:12:18 user-node github-runners[74176]: 07/24/2023 04:12:18 PM   INFO MainThread            main 🍀 Creating scale up service
      Jul 24 16:12:18 user-node github-runners[74176]: 07/24/2023 04:12:18 PM   INFO MainThread            main 🍀 Creating scale down service

which is equivalent to the following **journalctl** command:

.. code-block:: bash

   journalctl -u github-runners.service -f

You can dump the full log by omitting the **-f, --follow** option.

.. code-block:: bash

   github-runners service logs

:full service log:

   ::

      Jul 24 14:24:42 user-node systemd[1]: Started Autoscaling GitHub Actions Runners.
      Jul 24 14:24:42 user-node env[62771]: LANG=en_CA.UTF-8
      Jul 24 14:24:42 user-node env[62771]: LANGUAGE=en_CA:en
      Jul 24 14:24:42 user-node env[62771]: PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
      Jul 24 14:24:42 user-node env[62771]: INVOCATION_ID=dc7b778f95fa4ccf95e4a4592b50d9e1
      Jul 24 14:24:42 user-node env[62771]: JOURNAL_STREAM=8:328542
      Jul 24 14:24:42 user-node env[62771]: SYSTEMD_EXEC_PID=62771
      ...

--------------------------
Running as a Cloud Service
--------------------------

Instead of running **github-runners** program locally as a standalone application or as a service.
You can easily deploy **github-runners** to run on a Hetzner Cloud instance.

See **-h, --help** for all the available commands.

:✋ Note:
   By default, the server name where the **github-runners** service will be running
   is **github-runners**. If you want to use a custom server name, then
   you must use the **cloud --name** option for any **cloud** commands.

.. code-block:: bash

   github-runners cloud -h

Deployment
==========

You can deploy **github-runners** as a service to a new Hetzner Cloud server instance, that will be created for you automatically,
using the **cloud deploy** command.

:✋ Note:
   The options that are passed to the **github-runners <options> cloud deploy** command
   will be the same options with which the service will be executed.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/github-runners
   export HETZNER_TOKEN=GJzdc...

   github-runners deploy

You can specify the version of the package to be installed using the **--version** option. By default, the current local package
version will be installed on the cloud service server. You can also pass *latest* as the value to install the latest available
version.

.. code-block:: bash

   github-runners deploy --version latest

The **deploy** command will use the following default values:

:location:
   *ash*
:type:
   *cpx11*
:image:
   *ubuntu-22.04*

The **cloud deploy** command uses the following setup script.

:setup script:
   .. code-block:: bash

      set -x

      apt-get update

      apt-get -y install python3-pip
      apt-get -y install openssh-client

      echo "Create and configure ubuntu user"

      adduser ubuntu --disabled-password --gecos ""
      echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
      addgroup wheel
      usermod -aG wheel ubuntu
      usermod -aG sudo ubuntu

      echo "Generate SSH Key"
      sudo -u ubuntu ssh-keygen -t rsa -q -f "/home/ubuntu/.ssh/id_rsa" -N ""

You can customize deployment server location, type, and image using the *--location*, *--type*, and *--image* options.

.. code-block:: bash

   github-runners deploy --location nbg1 --type cx11 --image ubuntu-22.04

The cloud instance that runs the **github-runners** service can either be x64 or ARM64 instance. By default, **cpx11**
AMD, 2 vCPU, 2GB RAM, shared-cpu x64 instance type is used.

Using ARM64 Instance
++++++++++++++++++++

If you want to deploy the **github-runners** service to an ARM64 instance, then you must specify the instance
type using the **--type** option.

:✋ Note:
   Currently Hetzner Cloud has ARM64 instances only available in Germany, Falkenstein (**fsn1**) location.

For example, to use Ampere Altra, 4 vCPU, 8GB RAM shared-cpu ARM64 instance, you must specify **cax21**
as the value of the **--type** as follows:

.. code-block:: bash

   github-runners deploy --location fsn1 --type cax21 --image ubuntu-22.04

Using x64 Instance
++++++++++++++++++

By default, the **cpx11** AMD, 2 vCPU, 2GB RAM, shared-cpu x64 instance type is used. If you want to use
a different x64 instance then specify desired type using the **--type** option.

Redeploying Cloud Service
=========================

You can change cloud service configuration or cloud service package version without deleting the existing cloud service server
using the **cloud redeploy** command.

.. code-block:: bash

   github-runners <options> cloud redeploy

:✋ Note:
   The options that are passed to the **github-runners <options> cloud redeploy** command
   will be the same options with which the service will be executed.

You can specify the version of the package to be installed using the **--version** option.

Cloud Service Logs
===================

You can check logs for the **github-runners** service running on a cloud instance using the **github-runners cloud logs** command.
Specify **-f, --follow** if you want to follow the logs journal.

For example,

:dump the full log:

   .. code-block:: bash

      github-runners cloud logs

:follow the logs journal:

   .. code-block:: bash

      github-runners cloud logs -f

Cloud Service Status
=====================

You can check the status of the **github-runners** service running on a cloud instance using the **github-runners cloud status** command.

For example,

.. code-block:: bash

   github-runners cloud status

Stopping Cloud Service
======================

You can manually stop the **github-runners** service running on a cloud instance using the **github-runners cloud stop** command.

.. code-block:: bash

   github-runners cloud stop

Starting Cloud Service
======================

You can manually start the **github-runners** service running on a cloud instance after it was being manually stopped
using the **github-runners cloud start** command.

.. code-block:: bash

   github-runners cloud start

Installing Cloud Service
========================

You can manually force installation of the **github-runners** service running on a cloud instance using
the **github-runners cloud install** command.

:✋ Note:
   Just like with the `github-runners <options> service install` command,
   the options that are passed to the `github-runners <options> cloud install` command
   will be the same options with which the service will be executed.

You can specify **-f, --force** option to force service re-installation if it is already installed.

.. code-block:: bash

   github-runners <options> cloud install -f


Uninstalling Cloud Service
==========================

You can manually force uninstallation of the **github-runners** service running on a cloud instance using
the **github-runners cloud uninstall** command.

.. code-block:: bash

   github-runners cloud uninstall

Upgrading Cloud Service Package
===============================

You can manually upgrade the **github-runners** service package running on a cloud instance using
the **github-runners cloud upgrade** command.

If specific '--version' is specified then the *testflows.github.runners* package is upgraded to
the specified version otherwise the version is upgraded to the latest available.

:✋ Note:
   The service is not re-installed during the package upgrade process.
   Instead, it is stopped before the upgrade and then started back up
   after the package upgrade is complete.

.. code-block:: bash

   github-runners cloud upgrade --version <version>

The service is not re-installed during the package upgrade process.
Instead, it is stopped before the upgrade and then started back up

Changing Cloud Service Options
==============================

If you need to change cloud service options such as the **--setup-script** or the **--max-runners** etc.,
you can keep the existing server and use **cloud redeploy** command.

.. code-block:: bash

   github-runners <options> cloud redeploy --version latest

When needed, you can also SSH into the cloud service manually and perform changes manually.

You can do complete service teardown using the **cloud delete** and then the **cloud deploy** commands.

.. code-block:: bash

   github-runners cloud delete
   github-runners <options> cloud deploy --version latest

:✋ Note:
   Complete teardown will not affect any current jobs as the service is designed to
   be restartable. However, some servers might be left in an unfinished state
   but they will be cleaned up when the service is restarted.


Deleting Cloud Service
======================

You can delete the **github-runners** cloud service and the cloud instance that is running on using
the **github-runners cloud delete** command.

The **cloud delete** command, deletes the cloud service by first stopping the service and then deleting the server instance.

:❗Warning:
   The default server name where the cloud service is deployed is **github-runners**.
   Please make sure to specify the **cloud --name** option if you have deployed the service to a server with a different name.

For example,

:default name:
   .. code-block:: bash

      github-runners cloud delete

:custom name:
   .. code-block:: bash

      github-runners cloud --name <custom_name> delete

SSH in to Cloud Service
==============================

You can open SSH client to the cloud service using the **cloud ssh** command. For example,

.. code-block:: bash

   github-runners cloud ssh

You can also manually SSH in to the cloud service using the **ssh** utility. For convenience, you can
retrieve the SSH client command using the **cloud ssh command** command. For example,

.. code-block:: bash

   github-runners cloud ssh command

The output will contain the full **ssh** command including the IP address of the cloud service server.

::

   ssh -q -o "StrictHostKeyChecking no" root@5.161.87.21

------------------
Scaling Up Runners
------------------

The program scales up runners by looking for any jobs that have **queued** status.
For each such job, a corresponding Hetzner Cloud server instance is created with the following name:

::

   github-runner-{job.run_id}-{job.id}

The server is configured using default **setup** and **startup** scripts. The runner name is set
to be the same as the server name so that servers can be deleted for any idle runner that for some reason
does not pick up a job for which it was created within the **max-idle-runner-time** period.

:Note:
   Given that the server name is fixed and specific for each *job.run_id, job.id* tuple, if multiple `github-runners` are running in parallel then
   only 1 server will be created for a given `job` and any other attempts to create a server with the same name will be rejected
   by the Hetzner Cloud.

Also,

:Note:
   There is no guarantee that a given runner will pick the job with the exact **run_id, job.id** tuple that caused it to be created.
   This is expected and because for each **queued** job a unique runner will be created the number of runners will be
   equal the number of jobs and therefore under normal conditions all jobs will be executed as expected.

Maximum Number of Runners
=========================

By default, the maximum number of runners and therefore the maximum number of server instances is not set and therefore is unlimited.
You can set the maximum number of runners using the **--max-runners** option.

.. code-blocks::bash

   github-runners --max-runners 10


New Server
==========

The new server is accessed using SSH. It boots up with the specified OS image and is configured using
the **setup** and **startup** scripts.

:Server Type:

   The default server type is **cx11** which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.

   You can specify different x64 server instance type by using the **type-{name}** runner label.
   The **{name}** must be a valid `Hetzner Cloud <https://www.hetzner.com/cloud>`_
   server type name such as *cx11*, *cpx21* etc.

   For example, to use AMD, 3 vCPU, 4GB RAM shared-cpu x64 instance, you can define the **runs-on**
   as follows:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cpx21]

:Server Location:

   The server location can bespecified by using the **--default-location** option or the **in-<name>** runner label.
   By default, location is not set as some server types are not available in some locations.

:Image:

   The server is configured to have the image specified by the **--default-image** option or the **image-{type}-{name}** runner label.

:SSH Access:

   The server is configured to be accessed using *ssh* utility and the SSH public key path is specified using the **--ssh-key**
   option.

:Image Configuration:
   Each new server instance is configured using the `setup <#the-setup-script>`_ and the `startup <#the-start-up-script>`_ scripts.

The Setup Script
================

The **setup** script creates and configures **runner** user that has **sudo** privileges.

:Setup:

   .. code-block:: bash

        set -x

        echo "Create and configure ubuntu user"

        adduser ubuntu --disabled-password --gecos ""
        echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
        addgroup wheel
        usermod -aG wheel ubuntu
        usermod -aG sudo ubuntu

The Start-up Script
===================

The **startup** script installs GitHub Actions runner. After installation it configures the runner to start in an *--ephemeral* mode.
The *--ephemeral* mode causes the runner to exit as soon as it completes a job. After the runner exits the server is powered off.

The x64 **startup** script installs and configures x64 version of the runner.

:x64:

   .. code-block:: bash

     set -x
     echo "Install runner"
     cd /home/ubuntu
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
     cd /home/ubuntu

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

* **--ssh-key path**
  public SSH key file, default: *~/.ssh/id_rsa.pub*

* **--default-type name**
  default runner server type name, default: *cx11*

* **--default-location name**
  default runner server location name, default: not specified

* **--default-image type:name_or_description**
  default runner server image type and name or description,
  where type is either: 'system','snapshot','backup','app',
  default: *system:ubuntu-22.04*

* **-m count, --max-runners count**
  maximum number of active runners, default: *10*

* **-w count, --workers count**
  number of concurrent workers, default: *10*

* **--logger-config path**
  custom logger configuration file

* **--setup-script path**
  path to custom server setup script

* **--startup-x64-script path**
  path to custom server startup script

* **--startup-arm64-script path**
  path to custom ARM64 server startup script

* **--max-powered-off-time sec**
  maximum time after which a powered off server is deleted, default: *60* sec

* **--max-idle-runner-time sec**
  maximum time after which an idle runner is removed and its server deleted, default: *120* sec

* **--max-runner-registration-time**
  maximum time after which the server will be deleted if its runner is not registered with GitHub, default: *120* sec

* **--max-server-ready-time sec**
  maximum time to wait for the server to be in the running state, default: *120* sec

* **--scale-up-interval sec**
  scale up service interval, default: *15* sec

* **--scale-down-interval sec**
  scale down service interval, default: *15* sec

* **--debug**
  enable debugging mode, default: *False*

* **commands:**

  * *command*

    * **cloud**
      cloud service commands

      * **-n server, --name server**
        deployment server name, default: *github-runners*

      * **deploy**
        deploy cloud service

        * **-f, --force**
          force deployment if already exist

        * **--version number|latest**
          service package version to deploy, either version number or 'latest',
          default: current package version

        * **-l name, --location name**
          deployment server location, default: *ash*

        * **-t name, --type name**
          deployment server type, default: *cpx11*

        * **-i type:name_or_description, --image type:name_or_description**
          deployment server image type and name or description,
          where the type is either: 'system','snapshot','backup','app',
          default: *system:ubuntu-22.04*

        * **--setup-script path**
          path to custom deployment server setup script

      * **redeploy**
        redeploy on the same cloud service server

        * **--version number|latest**
          service package version to deploy, either version number or 'latest',
          default: current package version

      * **logs**
        get cloud service logs

        * **-f, --follow**
          follow logs journal, default: *False*

      * **status**
        get cloud service status

      * **start**
        start cloud service

      * **stop**
        stop cloud service

      * **install**
        install cloud service

        * **-f, --force**
          force installation if service already exists

      * **uninstall**
        uninstall cloud service

      * **upgrade**
        upgrade cloud service

        * **--version version**
          package version, default: *the latest*

      * **ssh**
        ssh to cloud service

        * **command**
          print ssh command to cloud service

    * **service**
      service commands

      * **install**
        install service

        * **-f, --force**
          force installation if service already exists

      * **uninstall**
        uninstall service

      * **status**
        get service status

      * **logs**
        get service logs

        * **-f, --follow**
          follow logs journal, default: *False*

      * **start**
        start service

      * **stop**
        stop service
