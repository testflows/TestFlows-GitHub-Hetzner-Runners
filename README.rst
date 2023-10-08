.. image:: https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/master/images/logo.png
   :width: 300px
   :align: center
   :target: https://testflows.com
   :alt: TestFlows Open-source Testing Framework

----

:PyPi:
   `Versions <https://pypi.org/project/testflows.github.hetzner.runners/>`_
:License:
   `Apache-2.0 <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/blob/main/LICENSE>`_

======================================================
Autoscaling GitHub Actions Runners Using Hetzner Cloud
======================================================

A simple alternative to Github's `Recommended autoscaling solutions <https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#recommended-autoscaling-solutions>`_.

:🔍 Tip:
   You can easily navigate this documentation page by clicking on any title to jump to the `Table of Contents`_.
   Try it out, and remember, if you get lost, just click any title!

The **github-hetzner-runners** service program starts and monitors queued-up jobs for GitHub Actions workflows.
When a new job is queued up, it creates a new Hetzner Cloud server instance
that provides an ephemeral GitHub Actions runner. Each server instance is automatically
powered off when the job completes, and then powered off servers are
automatically deleted. Both **x64** (*x86*) and **arm64** (*arm*) runners are supported.
See `Features`_ and `Limitations`_ for more details.

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-GiHhub-Hetzner-Runners/master/docs/images/intro.gif
   :align: center
   :alt: TestFlows GitHub Runners


:❗Warning:
   This program is provided on "AS IS" basis without warranties or conditions of any kind. See LICENSE.
   Use it at your own risk. Manual monitoring is required to make sure server instances are cleaned up properly
   and costs are kept under control.

Costs depend on the server type, number of jobs, and execution time. For each job, a new server instance is created
to avoid any cleanup. Server instances are not shared between jobs.

:✋ Note:
   Currently, Hetzner Cloud server instances are billed on an hourly basis. So a job that takes 1 minute will be billed
   the same way as for a job that takes 59 minutes. Therefore, the minimal cost
   for any job, the cost of the server for 1 hour plus the cost of one public IPv4 address.

=================
Table of Contents
=================

.. contents:: Find out more about,
   :backlinks: top
   :depth: 4

========
Features
========

* cost-efficient on-demand runners using `Hetzner Cloud <https://www.hetzner.com/cloud>`_
* supports server recycling to minimize costs
* simple configuration, no Webhooks, no need for AWS lambdas, and no need to setup any GitHub application
* supports specifying custom runner server types, images, and locations using job labels
* self-contained program that you can use to deploy, redeploy, and manage the service on a cloud instance
* supports x64 (x86) and ARM64 (arm) runners
* supports using any Hetzner Cloud server types
* supports runners with pre-installed Docker
* supports using any standard Hetzner Cloud images and applications
* supports auto-replenishable fixed standby runner pools for jobs to be picked up immediately
* supports limiting the maximum number of runners created for each workflow run
* supports efficient GitHub API usage using HTTP caching and conditional requests
* simpler alternative to what GitHub lists in `Recommended Autoscaling Solutions: <https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#recommended-autoscaling-solutions>`_

===========
Limitations
===========

**Group runners are not supported**
  ✎ However, you can run individual services for each repository using different Hetzner Cloud projects.

**A unique Hetzner Cloud project must be used for each repository**
   ✎ However, unique projects allow you to easily keep track of runner costs per repository.

=============
Prerequisites
=============

* Python >= 3.7
* `Hetzner Cloud <https://www.hetzner.com/cloud>`_ account
* GitHub API token with admin privileges to manage self-hosted runners

============
Installation
============

.. code-block:: bash

   pip3 install testflows.github.hetzner.runners

Check that the **github-hetzner-runners** utility was installed correctly by executing the **github-hetzner-runners -v** command.

.. code-block:: bash

   github-hetzner-runners -v

The **github-hetzner-runners** utility is installed in the *~/.local/bin/* folder. Please make sure that this folder
is part of the **PATH**.

.. code-block:: bash

   which github-hetzner-runners

::

   ~/.local/bin/github-hetzner-runners

If your **PATH** is missing this folder on Ubuntu, modify your *~/.profile* and add the following section:

:~/.profile:
   .. code-block:: bash

      # set PATH so it includes the user's private bin if it exists
      if [ -d "$HOME/.local/bin" ] ; then
          PATH="$HOME/.local/bin:$PATH"
      fi

===========
Quick Start
===========

Set environment variables corresponding to your GitHub repository and Hetzner Cloud project.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/testflows-github-hetzner-runners
   export HETZNER_TOKEN=GJzdc...

Then, start the **github-hetzner-runners** program:

.. code-block:: bash

   github-hetzner-runners

::

   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Logging in to Hetzner Cloud
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Logging in to GitHub
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Getting repository testflows/testflows-github-hetzner-runners
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Creating scale-up services
   07/22/2023 08:20:37 PM   INFO MainThread            main 🍀 Creating scale-down services
   07/22/2023 08:20:38 PM   INFO   worker_2   create_server 🍀 Create server
   ...

Alternatively, you can pass the required options using the command line as follows:

.. code-block:: bash

   github-hetzner-runners --github-token <GITHUB_TOKEN> --github-repository <GITHUB_REPOSITORY> --hetzner-token <HETZNER_TOKEN>

========================
Getting Started Tutorial
========================

:✅ Launch your first self-hosted runner in:
   5 minutes

This tutorial will guide you on how to use the **github-hetzner-runners** program to provide autoscaling GitHub Actions runners
for a GitHub repository and a Hetzner Cloud project that you'll create.

-----------------------------------
Installing TestFlows Github Runners
-----------------------------------

❶ Before we get started, you will need to install **testflows.github.hetzner.runners** Python package. See the `Installation`_ section for more details.

.. code-block:: bash

  pip3 install testflows.github.hetzner.runners

❷ Check that the **github-hetzner-runners** utility was installed correctly by executing the **github-hetzner-runners -v** command.

.. code-block:: bash

   github-hetzner-runners -v

::

   1.3.230731.1173142

:✋ Note:
   The **github-hetzner-runners** utility is installed in to the *~/.local/bin/* folder. Please make sure that this folder
   is part of the **PATH**.

   .. code-block:: bash

      which github-hetzner-runners

   ::

      ~/.local/bin/github-hetzner-runners

   If your **PATH** is missing this folder, on Ubuntu, you can modify your *~/.profile* and add the following section:

   :~/.profile:
      .. code-block:: bash

         # set PATH so it includes the user's private bin if it exists
         if [ -d "$HOME/.local/bin" ] ; then
             PATH="$HOME/.local/bin:$PATH"
         fi

In order to launch the **github-hetzner-runners** program, we'll need to specify the GitHub repository as well as GitHub and
Hetzner Cloud tokens. So, let's create these.

------------------------------------------------------------
Creating a GitHub Repository With Actions Workflow and Token
------------------------------------------------------------

Before using the **github-hetzner-runners**, you need a GitHub repository with a GitHub Actions workflow set up.

❶ First, create a GitHub repository named **demo-testflows-github-hetzner-runners** and note the repository name.

The repository name will have the following format:

::

   <username>/demo-testflows-github-hetzner-runners

For me, my GitHub repository is:

::

   vzakaznikov/demo-testflows-github-hetzner-runners

❷ Now, create an example GitHub Actions workflow as described in the `Quickstart for GitHub Actions <https://docs.github.com/en/actions/quickstart>`_ article.
Note that we need to modify the example YAML configuration and specify that our job will run on a runner with the **self-hosted** and the **type-cpx21**
labels.

.. code-block:: yaml

     Explore-GitHub-Actions:
       runs-on: [self-hosted, type-cpx21]

So, the complete *demo.yml* that uses a self-hosted runner is as follows:

:demo.yml:

   .. code-block:: yaml

      name: GitHub Actions Demo
      run-name: ${{ github.actor }} is testing out GitHub Actions 🚀
      on: [push]
      jobs:
        Explore-GitHub-Actions:
          runs-on: [self-hosted, type-cpx21]
          steps:
            - run: echo "🎉 The job was automatically triggered by a ${{ github.event_name }} event."
            - run: echo "🐧 This job is now running on a ${{ runner.os }} server hosted by GitHub!"
            - run: echo "🔎 The name of your branch is ${{ github.ref }} and your repository is ${{ github.repository }}."
            - name: Check out repository code
              uses: actions/checkout@v3
            - run: echo "💡 The ${{ github.repository }} repository has been cloned to the runner."
            - run: echo "🖥️ The workflow is now ready to test your code on the runner."
            - name: List files in the repository
              run: |
                ls ${{ github.workspace }}
            - run: echo "🍏 This job's status is ${{ job.status }}."


❸ Finally, you will need to create a GitHub API token with the **workflow** privileges. Make sure to save the token!

For me, my *demo* GitHub token is:

::

   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

You should now have your GitHub repository ready.

See these steps in action:

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-GitHub-Hetzner-Runners/master/docs/images/github_create_repo_and_token.gif
   :align: center
   :width: 790px
   :alt: Creating a GitHub Repository and Token

------------------------------------------
Creating a Hetzner Cloud Project and Token
------------------------------------------

Next, you will need to create a Hetzner Cloud project and an API token that we can use to create and manage Hetzner Cloud server instances.

❶ Create a new Hetzner Cloud project **Demo GitHub Runners**.

❷ Now, create an API token and save it.

For me, the Hetzner Cloud token for my *Demo GitHub Runners* project is:

::

   5Up04IHuY8mC7l0JxKwh3Aps4ghGIyL0NJ9rGlhyAmmkddzuRreR1YstTSTFCG0N

You should now have your Hetzner Cloud project ready.

See these steps in action:

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-GitHub-Hetzner-Runners/master/docs/images/hetzner_create_project_and_token.gif
   :align: center
   :width: 790px
   :alt: Creating a GitHub Repository and Token

------------------------
Creating a Cloud Service
------------------------

With the GitHub repository and GitHub and Hetzner Cloud tokens in hand, we can deploy the **github-hetzner-runners** service
to the Hetzner Cloud instance. This way, the service is not running on your local machine.

During the deployment, we'll create a **github-hetzner-runners** instance in your Hetzner Cloud project on which the service will be running.
See the `Running as a Cloud Service`_ section for details.

❶ To deploy the service run the **github-hetzner-runners cloud deploy** command and specify your
GitHub repository, GitHub, and Hetzner Cloud tokens using
**GITHUB_REPOSITORY**, **GITHUB_TOKEN**, and **HETZNER_TOKEN** environment variables.

.. code-block:: bash

   export GITHUB_REPOSITORY=
   export HETZNER_TOKEN=
   export GITHUB_TOKEN=
   github-hetzner-runners cloud deploy

You should now have the cloud service up and running.

See these steps in action:

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-GitHub-Hetzner-Runners/master/docs/images/cloud_deploy.gif
   :align: center
   :width: 625px
   :alt: Deploying Cloud Service

----------------------------------------------
Waiting for the GitHub Actions Job to Complete
----------------------------------------------

❶ The **github-hetzner-runners** cloud service is now running. So, now you can just sit back and wait until **github-hetzner-runners**
spins up a new runner to complete any queued-up GitHub Actions jobs in your GitHub repository.

See this step in action:

.. image:: https://raw.githubusercontent.com/testflows/TestFlows-GitHub-Hetzner-Runners/master/docs/images/github_job_completed.gif
   :align: center
   :width: 790px
   :alt: Waiting For the GitHub Actions Job to Complete

As you can see, our job was executed and completed using our own self-hosted runner!

:✋ Note:

   If you run into any issues, you can check the cloud service log using the
   **github-hetzner-runners cloud log -f** command. For other cloud service commands, see the `Running as a Cloud Service`_ section.

   .. code-block:: bash

      github-hetzner-runners cloud log -f

=========================
Installation from Sources
=========================

For development, you can install from sources as follows:

.. code-block:: bash

   git clone https://github.com/testflows/testflows-github-hetzner-runners.git
   ./package && ./install

===================
Basic Configuration
===================

By default, the program uses the following environment variables:

* **GITHUB_TOKEN**
* **GITHUB_REPOSITORY**
* **HETZNER_TOKEN**

or you can specify these values using the following options:

* **--github-token**
* **--github-repository**
* **--hetzner-token**

========================================
Specifying the Maximum Number of Runners
========================================

The default maximum number of runners is **10**. You can set a different value
based on your Hetzner Cloud limits using the **-m count, --max-runners count** option. For example,

.. code-block:: bash

   github-hetzner-runners --max-runners 40

===============================================================
Specifying the Maximum Number of Runners Used in Workflow a Run
===============================================================

By default, the maximum number of runners that could be created for a single workflow run
is not defined.

:❗Warning:
   In general, GitHub does not allow you to assign a job to a specific runner, so any available runner
   that matches the labels could be used. Therefore, one can't control how runners are allocated
   to queued workflow run jobs, and this is why the **--max-runners-in-workflow-run** option will not behave
   as one would intuitively expect.

If you set the **--max-runners-in-workflow-run** to some value *X*, then **github-hetzner-runners**
will create the *X * number of queued workflow runs* runners. How these runners will be allocated by
GitHub is out of our control. Therefore, the more runs queued-up, the more runners will be created, up to the **--max-runners**
limit, to try to complete the jobs faster. However, this does not mean that you will see exactly *X* number of jobs
being executed in each queued workflow run.

For example,

.. code-block:: bash

   github-hetzner-runners --max-runners 40 --max-runners-in-workflow-run 5

will create upto *5* runners for each queued up workflow run. If there is only one workflow running, then the maximum number of
runners will be *5* unless more queued-up workflow runs appear, which could then speed up the execution of the run in progress.

=============================
Recycling Powered-Off Servers
=============================

By default, recycling of powered-off servers that have completed executing a job is turned on.

Recycling allows for minimizing costs by allowing multiple runners to be brought up on
the same server instance as Hetzner Cloud, which bills servers in 1-hour increments.
Therefore, it is inefficient to delete a server if it only executed a job
that runs for a few minutes. Instead, after completing a job, the server is powered off
and if it can be recycled, it is rebuilt from scratch by reinstalling the image
thus providing a clean environment for the next job.

Powered-off servers are marked as recyclable by changing their name to **github-hetzner-runner-recycle-{uid}**.

Recyclable servers are deleted when they reach their end of life period
which is defined by the **--end-of-life** option, and by default is set to *50* minutes.
The end of life is calculated on an hourly basis and must be greater than *0* and less than *60*.

For example, with the default value of the **--end-of-life** option set to the *50* minutes,
if the server is running for 2 hours and 50 minutes, then it will be
considered to have reached its end of life and is deleted because it has only *10* minutes or less of useful life
left in the current hour period.
However, if the server is running for 2 hours and 30 minutes, then it could potentially
has 30 minutes of life left, and it will be kept around to be available for recycling.

Sometimes a job might need a server that does not match any recyclable servers,
if the maximum number of runners has been reached, then by default, one of the recyclable servers
will be picked to be deleted to make room for a new server. By default, the recyclable server
that is deleted is picked based on the server's price per hour and its remaining useful life.
The server with the lowest *unused budget* is deleted.

The *unused budget* is defined as follows:

:unused budget:

   .. code-block:: python3

      server_life = 60 - server_age.minutes
      price_per_minute = price_per_hour / 60
      unused_budget = server_life * price_per_minute

:✋ Note:
   You can also use the **--delete-random** option to randomly pick a recyclable server to be deleted.
   Deleting servers at random is a legacy feature.

A recyclable server is recycled for a new job if it matches the following:

* The server type matches exactly what the job requires, or the default type
* The server location matches exactly if a job requests a runner in a specific location or the default location is specified
* The server has matching SSH keys

:✋ Note:
   **Matching server type exactly means that even if a bigger, more expensive server type
   could be potentially recycled if it is not used, even though a job that actually requires
   that expensive server might not be queued before the server's end of life.**

   This is intensional, as we can't predict when a job that actually requires the more expensive
   server type could be queued. If the program would allow recycling of higher server types
   than actually requested by a job, then we could run into cases when a job
   that requires a smaller and less expensive server runs on a bigger and more expensive server instead.
   In this case, a job that actually requires a bigger server would force a new, expensive server to be created
   and thus causing more expensive servers to be created than are actually necessary.

If needed, you can turn recycling off using the **--recycle {on,off}** option.

.. code-block:: bash

   github-hetzner-runners --recycle off


=============
Skipping Jobs
=============

By default, a runner will be created for any **queued** job.

If needed, you can skip creating runners if a job does not have a specified label
using the **--with-label** option.

For example,

.. code-block:: bash

   github-hetzner-runners --with-label on-demand

will only create runners for jobs that contain **on-demand** label and skip any job that is missing
that label.

===================================
Jobs That Require the Docker Engine
===================================

For jobs that require Docker to be installed, you can use the standard `Hetzner Docker CE application: <https://docs.hetzner.com/cloud/apps/list/docker-ce/>`_
which can be specified using the **image-** label. See `Specifying the Runner Image`_ for more details about specifying custom runner images.

For example

:x64:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, image-x86-app-docker-ce]

:ARM64:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cax11, image-arm-app-docker-ce]

==========================
Specifying The Runner Type
==========================

-----------
x64 Runners
-----------

The default server type is **cx11**, which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.

:✋ Note:
   You can use the **--default-type** option to set a different default server type.

You can specify different x64 server instance type by using the **type-{name}** runner label.
The **{name}** must be a valid `Hetzner Cloud server type <https://www.hetzner.com/cloud>`_
name such as *cx11*, *cpx21* etc.

For example, to use an AMD, 3 vCPU, 4GB RAM shared-cpu x64 instance, you can define the **runs-on**
as follows:

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cpx21]

-------------
ARM64 Runners
-------------

The default server type is **cx11**, which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.
Therefore, in order to use ARM64 runners, you must specify the ARM64 server instance type by using the **type-{name}** runner label.
The **{name}** must be a valid `ARM64 Hetzner Cloud server type <https://www.hetzner.com/cloud>`_
name such as *cax11*, *cax21* etc. which correspond to the Ampere Altra, 2 vCPU, 4GB RAM and
4 vCPU, 8GB RAM shared-cpu ARM64 instances, respectively.

For example, to use the Ampere Altra, 4 vCPU, 8GB RAM shared-cpu ARM64 instance, you must define the **runs-on**
as follows:

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cax21]

==============================
Specifying The Runner Location
==============================

By default, the default location of the server where the runner will be running is not specified. You can use the **--default-location**
option to force a specific default server location.

You can also use the **in-{name}** runner label to specify the server location for a specific job. Where **{name}** must be a valid
`Hetzner Cloud location <https://docs.hetzner.com/cloud/general/locations/>`_ name such as *ash* for US, Ashburn, VA or
*fsn1* for Germany, Falkenstein.

For example,

.. code-block:: yaml

   job-name:
      runs-on: [self-hosted, type-cx11, in-ash]

===========================
Specifying The Runner Image
===========================

By default, the default image of the server for the runner is **ubuntu-22.04**. You can use the **--default-image**
option to force a specific default server image.

You can also use the **image-{architecture}-{type}-{name}** runner label to specify the server image for a specific job.

Where,

* **{architecture}** is either *x86* or *arm*
* **{type}** is either *system*, *snapshot*, *backup*, or *app*
* **{name}** must be a valid Hetzner Cloud image name, for *system* or *app* type, such as *ubuntu-22.04*,
  or a description, for *backup* or *snapshot* type.

For example,

:ubuntu-20.04:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-x86-system-ubuntu-20.04]


:docker-ce app:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-x86-app-docker-ce]

:snapshot:
   For snapshots, specify **description** as the name. Snapshot descriptions
   must be unique.

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cx11, in-ash, image-x86-snapshot-snapshot_description]

================================================
Specifying The Custom Runner Server Setup Script
================================================

You can specify a custom runner server setup script using the **--setup-script** option.

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

      github-hetzner-runners --setup-script ./custom_setup.sh

==========================
Specifying Standby Runners
==========================

You can define standby runner groups to always be ready to pick up your jobs using a custom configuration file.

:✋ Note:
   Standby runner groups can only be defined using a configuration file.
   See `Using a Configuration File`_ for more details.

Standby runners are always active and allow jobs to be picked up immediately.

More than one standby runner group can be specified in the **standby_runners**. Each group is defined using the **standby_runner** object
that has *labels*, *count*, and *replenish_immediately* attributes.

:schema:
   .. code-block:: json

       "standby_runners": {
           "type": "array",
           "items": {
               "type": "object",
               "properties": {
                   "labels": {
                       "type": "array",
                       "items": {
                           "type": "string"
                       }
                   },
                   "count": {
                       "type": "integer"
                   },
                   "replenish_immediately": {
                       "type": "boolean"
                   }
               }
           }
       }

where,

* **labels** specifies an array of labels with which standby runners in this group should be created
* **count** specifies the count of how many runners should be created for the group
* **replenish_immediately** specifies if the sandby runners should be replenished as soon as they become busy after picking up a job; default: true

For example,

:config.yaml:
   .. code-block:: yaml

      config:
         standby_runners:
            - labels:
               - type-cx21
              count: 2
              replenish_immediately: true

===============================
Specifying Logger Configuration
===============================

You can specify a custom logger configuration using a configuration file.

:✋ Note:
   A custom logger configuration can only be specified using a configuration file.
   See `Using a Configuration File`_ for more details.

The logger configuration is specified in the configuration file using the **logger_config** object.
For more information about the logger configuration, see `Configuration dictionary schema <https://docs.python.org/3/library/logging.config.html#logging-config-dictschema>`_ in the Python documentation.

Any custom logger configuration must at least define **stdout** and **rotating_service_logfile** handlers
as well as configure **testflows.github.hetzner.runners** in the **loggers**.

For example,

:config.yaml:
   .. code-block:: yaml

       config:
          # logging module config
          logger_config:
              version: 1
              disable_existing_loggers: false
              formatters:
                  standard:
                      format: "%(asctime)s %(levelname)s %(funcName)s %(message)s"
                      datefmt: "%m/%d/%Y %I:%M:%S %p"
              handlers:
                  stdout:
                      level: INFO
                      formatter: standard
                      class: testflows.github.hetzner.runners.logger.StdoutHandler
                      stream: "ext://sys.stdout"
                  rotating_service_logfile:
                      level: DEBUG
                      formatter: standard
                      class: testflows.github.hetzner.runners.logger.RotatingFileHandler
                      filename: /tmp/github-hetzner-runners.log
                      maxBytes: 10485760
                      backupCount: 1
              loggers:
                  testflows.github.hetzner.runners:
                      level: INFO
                      handlers:
                          - stdout
                          - rotating_service_logfile

If the logger configuration is using a custom format for the **rotating_service_logfile**, then a custom **logger_format** object
must be defined to specify the format of the service's rotating log file, which is needed for the **service log** and **cloud log** commands.

For the example above, the custom **logger_format** is the following:

.. code-block:: yaml

   config:
       # logger format
       logger_format:
           delimiter: " "
           default:
               - column: date
               - column: time
               - column: time_ampm
               - column: level
               - column: funcName
               - column: message
           columns:
               - column: date
                 index: 0
                 width: 10
               - column: time
                 index: 1
                 width: 8
               - column: time_ampm
                 index: 2
                 width: 2
               - column: level
                 index: 3
                 width: 8
               - column: funcName
                 index: 4
                 width: 15
               - column: message
                 index: 5
                 width: 80

Note that the *date*, *time*, and *time_ampm* columns come from the **datefmt** definition, which
defines the **asctime** as a three-column field consisting of *date*, *time*, and *time_ampm* columns
separated by a space.

.. code-block:: yaml

   datefmt: "%m/%d/%Y %I:%M:%S %p"

===========================
Listing All Current Servers
===========================

You can list all currently created servers using the **list** command.
This command will show all the servers that start with the *github-hetzner-runner* prefix in their name.

For example,

.. code-block:: bash

   github-hetzner-runners list

::

   Using config file: /home/user/.github-hetzner-runners/config.yaml
   11:40:40 🍀 Logging in to Hetzner Cloud
   11:40:40 🍀 Getting a list of servers
   ❌ off        github-hetzner-runner-5811138574-15753659850
   ❌ off        github-hetzner-runner-recycle-1691595565.5396028
   ❌ off        github-hetzner-runner-recycle-1691595478.7024605
   ❌ off        github-hetzner-runner-5811138574-15753660130
   ❌ off        github-hetzner-runner-recycle-1691595481.196499

====================================
Opening The SSH Client To The Server
====================================

For debugging, you can open an SSH client to the current server using the **ssh** command and specify the name of the server you would like to connect to.
For the **ssh** command to work, you need to specify the **--hetzner-token** and have the correct private SSH key.

.. code-block:: bash

   github-hetzner-runners ssh <name>

For example,

.. code-block:: bash

   github-hetzner-runners ssh github-hetzner-runner-5811138574-15753659850

======================================
Deleting All Runners and Their Servers
======================================

You can delete all runners, including standby runners, and their servers using the **delete** command.

:✋ Note:
   The **delete** command will not delete a cloud service server. If you also want to delete it,
   you also need to execute **cloud delete** command. For more information, see `Deleting the Cloud Service`_ section.

.. code-block:: bash

   github-hetzner-runners delete

::

   07/29/2023 07:43:16 PM     INFO       MainThread             all 🍀 Logging in to Hetzner Cloud
   07/29/2023 07:43:16 PM     INFO       MainThread             all 🍀 Logging in to GitHub
   07/29/2023 07:43:16 PM     INFO       MainThread             all 🍀 Getting repository testflows/testflows-github-hetzner-runners
   07/29/2023 07:43:17 PM     INFO       MainThread             all 🍀 Getting list of self-hosted runners
   07/29/2023 07:43:17 PM     INFO       MainThread             all 🍀 Getting list of servers

==========================
Using a Configuration File
==========================

Instead of passing configuration options using command-line arguments, you can use
configuration file. The configuration file uses YAML format, and it is usually named **config.yaml**. You can find the complete schema
in `schema.json <https://github.com/testflows/TestFlows-github-hetzner-runners/blob/main/testflows/github/hetzner/runners/config/schema.json>`_.

:✋ Note:
   When you mix command-line options with a custom configuration file,
   explicit command-line options take precedence over the values that are defined
   for the same parameters in the configuration file.

You can specify the default configuration by placing the configuration in the *~/.github-hetzner-runners/config.yaml* file or
pass the path to the configuration file explicitly using the **-c path, --config path** option.

The YAML configuration file supports special syntax to specify the value of a property as the value of the environment variable using
the **${ENV_VAR_NAME}** syntax.

For example,

.. code-block:: bash

   github-hetzner-runners -c config.yaml

where,

:config.yaml:
   .. code-block:: yaml

      config:
         github_token: ${GITHUB_TOKEN}
         github_repository: ${GITHUB_REPOSITORY}
         hetzner_token: ${HETZNER_TOKEN}
         default_server_type: cx11
         cloud:
            server_name: "my-github-hetzner-runners-service"
         standby_runners:
            - labels:
               - type-cx21
              count: 2
              replenish_immediately: true

:✋ Note:
   This is a simple configuration file. You can find a complete example in the `examples/config.yaml <https://github.com/testflows/TestFlows-github-hetzner-runners/blob/main/examples/config.yaml>`_.

==================
Specifying SSH Key
==================

All server instances that are created are accessed via SSH using the **ssh** utility and therefore you must provide a valid SSH key
using the **--ssh-key** option. If the **--ssh-key** option is not specified, then the *~/.ssh/id_rsa.pub* default key path will be used.

The SSH key will be automatically added to your project using the MD5 hash of the public key as the SSH key name.

:❗Warning:
   Given that each new SSH key is automatically added to your Hetzner project, you must manually delete them when no longer needed.

Most GitHub users already have an SSH key associated with the account. If you want to know how to add an SSH key, see `Adding a new SSH key to your GitHub account    <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>`_ article.

------------------------
Generating a New SSH Key
------------------------

If you need to generate a new SSH key, see `Generating a new SSH key and adding it to the ssh-agent <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`_ article.

----------------------------
SSH Keys in Cloud Deployment
----------------------------

If you are deploying the **github-hetzner-runners** program as a cloud service using the **github-hetzner-runners <options> cloud deploy** command, then
after provisioning a new cloud server instance that will host the **github-hetzner-runners** service, a new SSH key will be
auto-generated to access the runners. The auto-generated key will be placed in */home/runner/.ssh/id_rsa*, where **runner**
is the user under which the **github-hetzner-runners** service runs on the cloud instance. The auto-generated SSH key will be automatically
added to your project using the MD5 hash of the public key as the SSH key name.

==============================
Specifying Additional SSH Keys
==============================

In addition to the main SSH key specified by the **--ssh-key** option, which is used to connect to the servers, you
can specify additional SSH keys using the **additional_ssh_keys**  property in the configuration file.
This is needed in cases where there is more than one user that should have access to the servers used for the runners.

:✋ Note:
   Additional SSH keys can only be defined using a configuration file.
   See `Using a Configuration File`_ for more details.

Note that the additional SSH keys are defined using only the public key. This enables additional users to hold the matching private key
to connect to the servers.

For example,

:config.yaml:
   .. code-block:: yaml

      config:
         additional_ssh_keys:
            - ssh-rsa AAAAB3Nza3... user@user-node
            - ssh-rsa AADDDFFFC1... another_user@another-node

====================
Running as a Service
====================

You can run **github-hetzner-runners** as a service.

:✋ Note:
   In order to install the service, the user who installed the module must have **sudo** privileges.

---------------------------
Installing and Uninstalling
---------------------------

After installation, you can use **service install** and **service uninstall** commands to install and
uninstall the service.

:✋ Note:
   The options that are passed to the **github-hetzner-runners <options> service install** command
   will be the same options with which the service will be executed.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/github-hetzner-runners
   export HETZNER_TOKEN=GJzdc...

   github-hetzner-runners service install

The **/etc/systemd/system/github-hetzner-runners.service** file is created with the following content.

:✋ Note:
   The service will use the *User* and the *Group* of the user executing the program.


:/etc/systemd/system/github-hetzner-runners.service:

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
      Environment=GITHUB_REPOSITORY=testflows/testflows-github-hetzner-runners
      Environment=HETZNER_TOKEN=GJ..
      ExecStart=/home/user/.local/lib/python3.10/site-packages/testflows/github/hetzner/runners/bin/github-hetzner-runners --workers 10 --max-powered-off-time 20 --max-unused-runner-time 120 --max-runner-registration-time 60 --scale-up-interval 10 --scale-down-interval 10
      [Install]
      WantedBy=multi-user.target

-------------------------
Modifying Program Options
-------------------------

If you want to modify service program options, you can stop the service,
edit the **/etc/systemd/system/github-hetzner-runners.service** file by hand, then reload the service daemon,
and start the service back up.

.. code-block:: bash

   github-hetzner-runners service stop
   sudo vim /etc/systemd/system/github-hetzner-runners.service
   sudo systemctl daemon-reload
   github-hetzner-runners service starts

---------------
Checking Status
---------------

After installation, you can check the status of the service using the **service status** command.

.. code-block:: bash

   github-hetzner-runners service status:

:service status:

   ::

      ● github-hetzner-runners.service - Autoscaling GitHub Actions Runners
           Loaded: loaded (/etc/systemd/system/github-hetzner-runners.service; enabled; vendor preset: enabled)
           Active: active (running) since Mon 2023-07-24 14:38:33 EDT; 1h 31min ago
         Main PID: 66188 (python3)
            Tasks: 3 (limit: 37566)
           Memory: 28.8M
              CPU: 8.274s
           CGroup: /system.slice/github-hetzner-runners.service
                   └─66188 python3 /usr/local/bin/github-hetzner-runners --workers 10 --max-powered-off-time 20 --max-unused-runner-time 120 --max->

      Jul 24 14:38:33 user-node systemd[1]: Started Autoscaling GitHub Actions Runners.
      Jul 24 14:38:33 user-node github-hetzner-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Logging in to Hetzner >
      Jul 24 14:38:33 user-node github-hetzner-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Logging in to GitHub
      Jul 24 14:38:33 user-node github-hetzner-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Getting repository vza>
      Jul 24 14:38:33 user-node github-hetzner-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Creating scale up serv>
      Jul 24 14:38:33 user-node github-hetzner-runners[66188]: 07/24/2023 02:38:33 PM   INFO MainThread            main 🍀 Creating scale down se>
      lines 1-16/16 (END)

---------------------
Manual Start and Stop
---------------------

You can start and stop the service using the **service start** and **service stop** commands as follows:

.. code-block:: bash

   github-hetzner-runners service starts
   github-hetzner-runners service stop

or using **service** system utility

.. code-block:: bash

   sudo service github-hetzner-runners start
   sudo service github-hetzner-runners stop

:✋ Note:
   The **service stop** command will send the *SIGINT* signal to the **github-hetzner-runners** process and will wait for the
   program to perform a clean shutdown, which includes stopping scale up and scale down loops.
   Given that the **github-hetzner-runners** program might be in the middle of configuring servers, the **service stop**
   command might take sometime to complete.

-------------
Checking Log
-------------

You can get the log for the service using the **service log** command.

Following The Log
=================

Use the **-f, --follow** option to follow the log journal. By default, the last *1000* lines will be shown and
then the log will be followed, and the new messages will be displayed as they are added to the log.

.. code-block:: bash

   github-hetzner-runners service log -f

:followed log:

   ::

      github-hetzner-runners service log -f
      Using config file: /home/user/.github-hetzner-runners/config.yaml
      18:11:49 api_watch      INFO     🍀 Consumed 0 calls in 60 sec, 5000 calls left, reset in 3599 sec
      18:12:49 api_watch      INFO     🍀 Logging in to GitHub
      18:12:49 api_watch      INFO     🍀 Checking current API calls consumption rate
      18:12:49 api_watch      INFO     🍀 Consumed 0 calls in 60 sec, 5000 calls left, reset in 3599 sec
      18:13:49 api_watch      INFO     🍀 Logging in to GitHub
      18:13:49 api_watch      INFO     🍀 Checking current API calls consumption rate
      18:13:50 api_watch      INFO     🍀 Consumed 0 calls in 60 sec, 5000 calls left, reset in 3599 sec
      ...

You can dump the full log by omitting the **-f, --follow** option.

.. code-block:: bash

   github-hetzner-runners service log

:full log:

   ::

      Using config file: /home/user/.github-hetzner-runners/config.yaml
      09:44:28 http_cache     INFO     🍀 Enabling HTTP cache at /tmp/tmp60wo30tc/http_cache
      09:44:28 main           INFO     🍀 Logging in to Hetzner Cloud
      09:44:28 main           INFO     🍀 Logging in to GitHub
      09:44:28 main           INFO     🍀 Getting repository testflows/testflows-github-hetzner-runners
      09:44:28 main           INFO     🍀 Checking if default image exists
      09:44:29 main           INFO     🍀 Checking if default location exists
      09:44:29 main           INFO     🍀 Checking if default server type exists
      09:44:29 main           INFO     🍀 Getting server prices
      09:44:30 main           INFO     🍀 Checking if SSH key exists
      ...

Selecting Log Columns
=====================

You can use the **-c name[:width][,...], --columns name[:width][,...]** option to specify
a comma-separated list of columns to include in the output as well as their optional width.

For example,

.. code-block:: bash

   github-hetzner-runners service log -f -c time,message:50

::

   Using config file: /home/user/.github-hetzner-runners/config.yaml
   Using config file: /home/user/.github-hetzner-runners/config.yaml
   18:13:50 🍀 Consumed 0 calls in 60 seconds, 5000 calls left,
            reset in 3599 sec
   18:14:50 🍀 Logging in to GitHub
   18:14:50 🍀 Checking current API calls consumption rate
   ...

By default, the following columns are available unless you redefine the **logger_format** in your configuration file:

* *date*
* *time*
* *level*
* *interval*
* *funcName*
* *threadName*
* *run_id*
* *job_id*
* *server_name*
* *message*

Selecting the Number of Lines
=============================

You can select the number of lines you would like to output from the log using the
**-n [+]number, --lines [+]number** option. With the **--follow** the default is *10*.

You can use the **+** before the *number* to output a log starting with the specified line number.

For example,

.. code-block:: bash

   github-hetzner-runners service log -n 50
   github-hetzner-runners service log -n +100
   github-hetzner-runners service log -f -n 1

Raw Log
=======

By default, the log is processed and broken up into columns based on the **logger_format** configuration.
You can output the raw log by specifying the **--raw** option.

==========================
Running as a Cloud Service
==========================

Instead of running **github-hetzner-runners** program locally as a standalone application or as a service.
You can easily deploy **github-hetzner-runners** to run on a Hetzner Cloud instance.

See **-h, --help** for all the available commands.

:✋ Note:
   By default, the server name where the **github-hetzner-runners** service will be running
   is **github-hetzner-runners**. If you want to use a custom server name, then
   you must use the **cloud --name** option for any **cloud** commands.

.. code-block:: bash

   github-hetzner-runners cloud -h

---------
Deploying
---------

You can deploy **github-hetzner-runners** as a service to a new Hetzner Cloud server instance, that will be created for you automatically,
using the **cloud deploy** command.

:✋ Note:
   The options that are passed to the **github-hetzner-runners <options> cloud deploy** command
   will be the same options with which the service will be executed.

.. code-block:: bash

   export GITHUB_TOKEN=ghp_...
   export GITHUB_REPOSITORY=testflows/github-hetzner-runners
   export HETZNER_TOKEN=GJzdc...

   github-hetzner-runners cloud deploy

You can specify the version of the package to be installed using the **--version** option. By default, the current local package
version will be installed on the cloud service server. You can also pass *latest* as the value to install the latest available
version.

.. code-block:: bash

   github-hetzner-runners cloud deploy --version latest

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

   github-hetzner-runners cloud deploy --location nbg1 --type cx11 --image ubuntu-22.04

The cloud instance that runs the **github-hetzner-runners** service can either be x64 or ARM64 instance. By default, **cpx11**
AMD, 2 vCPU, 2GB RAM, shared-cpu x64 instance type is used.

Using an ARM64 Instance
=======================

If you want to deploy the **github-hetzner-runners** service to an ARM64 instance, then you must specify the instance
type using the **--type** option.

:✋ Note:
   Currently, Hetzner Cloud has ARM64 instances only available in Germany, Falkenstein (**fsn1**) location.

For example, to use an Ampere Altra, 4 vCPU, 8GB RAM shared-cpu ARM64 instance, you must specify **cax21**
as the value of the **--type** as follows:

.. code-block:: bash

   github-hetzner-runners cloud deploy --location fsn1 --type cax21 --image ubuntu-22.04

Using x64 Instance
==================

By default, the **cpx11** AMD, 2 vCPU, 2GB RAM, shared-cpu x64 instance type is used. If you want to use
a different x64 instance, then specify the desired type using the **--type** option.

-------------------------
Redeploying Cloud Service
-------------------------

You can change the cloud service configuration or cloud service package version without deleting the existing cloud service server
using the **cloud redeploy** command.

.. code-block:: bash

   github-hetzner-runners <options> cloud redeploy

:✋ Note:
   The options that are passed to the **github-hetzner-runners <options> cloud redeploy** command
   will be the same options with which the service will be executed.

You can specify the version of the package to be installed using the **--version** option.

-----------------
Cloud Service Log
-----------------

You can check the log for the **github-hetzner-runners** service running on a cloud instance using the **github-hetzner-runners cloud log** command.
Specify **-f, --follow** if you want to follow the log journal.

For example,

:dump the full log:

   .. code-block:: bash

      github-hetzner-runners cloud log

:follow the log journal:

   .. code-block:: bash

      github-hetzner-runners cloud log -f

You can also specify the **--raw** option to output the raw log as well as use the **-c name[:width][,...], --columns name[:width][,...]**
option to specify a comma separated list of columns to include in the output and their optional width.

--------------------
Cloud Service Status
--------------------

You can check the status of the **github-hetzner-runners** service running on a cloud instance using the **github-hetzner-runners cloud status** command.

For example,

.. code-block:: bash

   github-hetzner-runners cloud status

----------------------
Stopping Cloud Service
----------------------

You can manually stop the **github-hetzner-runners** service running on a cloud instance using the **github-hetzner-runners cloud stop** command.

.. code-block:: bash

   github-hetzner-runners cloud stop

----------------------
Starting Cloud Service
----------------------

You can manually start the **github-hetzner-runners** service running on a cloud instance after it was manually stopped
using the **github-hetzner-runners cloud start** command.

.. code-block:: bash

   github-hetzner-runners cloud start

------------------------
Installing Cloud Service
------------------------

You can manually force installation of the **github-hetzner-runners** service running on a cloud instance using
the **github-hetzner-runners cloud install** command.

:✋ Note:
   Just like with the `github-hetzner-runners <options> service install` command,
   the options that are passed to the `github-hetzner-runners <options> cloud install` command
   will be the same options with which the service will be executed.

You can specify **-f, --force** option to force service reinstallation if it is already installed.

.. code-block:: bash

   github-hetzner-runners <options> cloud install -f

------------------------------
Uninstalling the Cloud Service
------------------------------

You can manually force the uninstallation of the **github-hetzner-runners** service running on a cloud instance using
the **github-hetzner-runners cloud uninstall** command.

.. code-block:: bash

   github-hetzner-runners cloud uninstall

-----------------------------------
Upgrading the Cloud Service Package
-----------------------------------

You can manually upgrade the **github-hetzner-runners** service package running on a cloud instance using
the **github-hetzner-runners cloud upgrade** command.

If a specific '--version' is specified, then the *testflows.github.hetzner.runners* package is upgraded to
the specified version, otherwise the version is upgraded to the latest available.

:✋ Note:
   The service is not reinstalled during the package upgrade process.
   Instead, it is stopped before the upgrade and then started back up
   after the package upgrade is complete.

.. code-block:: bash

   github-hetzner-runners cloud upgrade --version <version>

The service is not reinstalled during the package upgrade process.
Instead, it is stopped before the upgrade and then started back up

------------------------------
Changing Cloud Service Options
------------------------------

If you need to change cloud service options such as the **--setup-script** or the **--max-runners** etc.,
you can keep the existing server and use **cloud redeploy** command.

.. code-block:: bash

   github-hetzner-runners <options> cloud redeploy --version latest

When needed, you can also SSH into the cloud service manually and perform changes manually.

You can do a complete service teardown using the **cloud delete** and then the **cloud deploy** commands.

.. code-block:: bash

   github-hetzner-runners cloud delete
   github-hetzner-runners <options> cloud deploy --version latest

:✋ Note:
   A complete teardown will not affect any current jobs, as the service is designed to
   be restartable. However, some servers might be left in an unfinished state
   but they will be cleaned up when the service is restarted.

--------------------------
Deleting the Cloud Service
--------------------------

You can delete the **github-hetzner-runners** cloud service and the cloud instance that is running on it using
the **github-hetzner-runners cloud delete** command.

The **cloud delete** command, deletes the cloud service by first stopping the service and then deleting the server instance.

:❗Warning:
   The default server name where the cloud service is deployed is **github-hetzner-runners**.
   Please make sure to specify the **cloud --name** option if you have deployed the service to a server with a different name.

For example,

:default name:
   .. code-block:: bash

      github-hetzner-runners cloud delete

:custom name:
   .. code-block:: bash

      github-hetzner-runners cloud --name <custom_name> delete

-----------------------
SSH in to Cloud Service
-----------------------

You can open an SSH client to the cloud service using the **cloud ssh** command. For example,

.. code-block:: bash

   github-hetzner-runners cloud ssh

You can also manually SSH into the cloud service using the **ssh** utility. For convenience, you can
retrieve the SSH client command using the **cloud ssh command** command. For example,

.. code-block:: bash

   github-hetzner-runners cloud ssh command

The output will contain the full **ssh** command including the IP address of the cloud service server.

::

   ssh -q -o "StrictHostKeyChecking no" root@5.161.87.21

==================
Scaling Up Runners
==================

The program scales up runners by looking for any jobs that have **queued** status.
For each such job, a corresponding Hetzner Cloud server instance is created with the following name:

::

   github-hetzner-runner-{job.run_id}-{job.id}

The server is configured using the default **setup** and **startup** scripts. The runner's name is set
to be the same as the server name so that servers can be deleted for any unused runner that, for some reason
does not pick up a job for which it was created within the **max-unused-runner-time** period.

:Note:
   Given that the server name is fixed and specific for each *job.id*, if multiple `github-hetzner-runners` are running in parallel, then
   only one server will be created for a given `job`, and any other attempts to create a server with the same name will be rejected
   by the Hetzner Cloud.

Also,

:Note:
   There is no guarantee that a given runner will pick the job with the exact *job.id* that caused it to be created.
   This is expected, and for each **queued** job a unique runner will be created. The number of runners will be
   equal the number of jobs, and therefore, under normal conditions, all jobs will be executed as expected.

-------------------------
Maximum Number of Runners
-------------------------

By default, the maximum number of runners and, therefore, the maximum number of server instances are not set and are therefore unlimited.
You can set the maximum number of runners using the **--max-runners** option.

.. code-blocks::bash

   github-hetzner-runners --max-runners 10

----------
New Server
----------

The new server is accessed using SSH. It boots up with the specified OS image and is configured using
the **setup** and **startup** scripts.

:Server Type:

   The default server type is **cx11** which is an Intel, 1 vCPU, 2GB RAM shared-cpu x64 instance.

   You can specify different x64 server instance type by using the **type-{name}** runner label.
   The **{name}** must be a valid `Hetzner Cloud <https://www.hetzner.com/cloud>`_
   server type name such as *cx11*, *cpx21* etc.

   For example, to use an AMD, 3 vCPU, 4GB RAM shared-cpu x64 instance, you can define the **runs-on**
   as follows:

   .. code-block:: yaml

      job-name:
         runs-on: [self-hosted, type-cpx21]

:Server Location:

   The server location can be specified by using the **--default-location** option or the **in-<name>** runner label.
   By default, location is not set, as some server types are not available in some locations.

:Image:

   The server is configured to have the image specified by the **--default-image** option or the **image-{architecture}-{type}-{name}** runner label.

:SSH Access:

   The server is configured to be accessed using the *ssh* utility, and the SSH public key path is specified using the **--ssh-key**
   option.

:Image Configuration:
   Each new server instance is configured using the `setup <#the-setup-script>`_ and the `startup <#the-start-up-script>`_ scripts.

----------------
The Setup Script
----------------

The **setup** script creates and configures a **runner** user that has **sudo** privileges.

:Setup:

   .. code-block:: bash

        set -x

        echo "Create and configure ubuntu user"

        adduser ubuntu --disabled-password --gecos ""
        echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
        addgroup wheel
        usermod -aG wheel ubuntu
        usermod -aG sudo ubuntu

-------------------
The Start-up Script
-------------------

The **startup** script installs the GitHub Actions runner. After installation, it configures the runner to start in an *--ephemeral* mode.
The *--ephemeral* mode causes the runner to exit as soon as it completes a job. After the runner exits, the server is powered off.

:✋ Note:
   The **startup** script is executed as a **ubuntu** user, and therefore you must use **sudo** for any commands that need *root* privileges.

The x64 **startup** script installs and configures the x64 version of the runner.

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


The ARM64 **startup** script is similar to the x64 script but installs an ARM64 version of the runner.

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

====================
Scaling Down Runners
====================

-------------------
Powered Off Servers
-------------------

The program scales down runners by first cleaning up powered-off servers. The scaled-down service relies on the fact
that the `startup <#the-start-up-script>`_ script starts an ephemeral runner that will pick up only 1 job and then power itself off after the job is complete.

The powered-off servers are deleted after the **max-powered-off-time** interval, which
can be specified using the **--max-powered-off-time** option, which by default is set to *20* sec.

--------------
Unused Runners
--------------

The scale-down service also monitors all the runners that have **unused** status and tries to delete any servers associated with such
runners if the runner is **unused** for more than the **max-unused-runner-time** period. This is needed in case a runner never gets a job
assigned to it, and the server will stay in the power-on state. This cycle relies on the fact that the runner's name
is the same as the server's name. The **max-unused-runner-time** can be specified using the **--max-unused-runner-time** option, which by default
is set to *180* sec.

--------------
Zombie Servers
--------------

The scale-down service will delete any zombie servers. A zombie server is defined as any server that fails to register its runner within
the **max-runner-registration-time**. The **max-runner-registration-time** can be specified using the **--max-runner-registration-time** option
which by default is set to *180* sec.

===========================
Handling Failing Conditions
===========================

The program is designed to handle the following failing conditions:

:The server Never Registers a Runner:
   The server will remain in a **running** state and should be reclaimed by the scale-down service when it checks the actual runners registered for the current servers.
   If it finds a server that is **running** but no runner is active for it it will be deleted after the **max-runner-registration-time** period.

:The *./config.sh* Command Fails:
   The behavior will be the same as for the **Server Never Registers a Runner** case above.

:The *./run.sh* Command Fails:
   The server will be powered-off by the **startup** script and deleted by the scale-down service.

:Creating A Server For Queued Job Fails:
   If creation of the server fails for some reason, then the scale-up service will retry the operation in the next interval, as the job's status will remain **queued**.

:Runner Never Gets a Job Assigned:
   If the runner never gets a job assigned, then the scale-down service will remove the runner and delete its server after the **max-unused-runner-time** period.

:Runner Created With a Mismatched Labels:
   The behavior will be the same as in the **Runner Never Gets a Job Assigned** case above.

===============
Program Options
===============

The following options are supported:

* **-h, --help**
  show this help message and exit

* **-v, --version**
  show the program's version number and exit

* **--license**
  show the program's license and exit

* **-r {on,off}, --recycle {on,off}**
  turn on or off recycling of powered-off servers, either 'on' or 'off', default: *on*

* **--end-of-life minutes**
  number of minutes in an hour (60 minutes) period after which a recyclable server
  is considered to have reached its end of life and thus is deleted; default: *50*

* **-c path, --config path**
  program configuration file

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
  default runner server location name, default: *not specified*

* **--default-image architecture:type:name_or_description**
  default runner server image type and name or description,
  where the architecture is either: 'x86' or 'arm',
  and type is either: 'system','snapshot','backup','app',
  default: *system:ubuntu-22.04*

* **-m count, --max-runners count**
  maximum number of active runners, default: *10*

* **--delete-random**
  delete random recyclable server when the maximum number of servers is reached, by default, server prices are used

* **--max-runners-in-workflow-run count**
  maximum number of runners allowed to be created for a single workflow run, default: not set

* **--with-label label**
  only create runners for jobs that have the specified label,
  by default, jobs are not skipped, and runners will be created for any queued job

* **--label-prefix prefix**
  support type, image, and location job labels with the specified prefix

* **-w count, --workers count**
  number of concurrent workers, default: *10*

* **--setup-script path**
  path to the custom server setup script

* **--startup-x64-script path**
  path to the custom server startup script

* **--startup-arm64-script path**
  path to the custom ARM64 server startup script

* **--max-powered-off-time sec**
  maximum time after which a powered-off server is deleted, default: *60* sec

* **--max-unused-runner-time sec**
  maximum time after which an unused runner is removed and its server deleted, default: *180* sec

* **--max-runner-registration-time**
  maximum time after which the server will be deleted if its runner is not registered with GitHub, default: *180* sec

* **--max-server-ready-time sec**
  maximum time to wait for the server to be in the running state, default: *180* sec

* **--scale-up-interval sec**
  scale-up service interval, default: *15* sec

* **--scale-down-interval sec**
  scale-down service interval, default: *15* sec

* **--debug**
  enable debugging mode, default: *False*

* **commands:**

  * *command*

    * **delete**
      delete all servers

    * **list**
      list all servers

    * **ssh**
      ssh to a server

    * **cloud**
      cloud service commands

      * **-n server, --name server**
        deployment server name, default: *github-hetzner-runners*

      * **deploy**
        deploy cloud service

        * **-f, --force**
          force deployment if it already exists

        * **--version number|latest**
          service package version to deploy, either a version number or 'latest',
          default: current package version

        * **-l name, --location name**
          deployment server location, default: *ash*

        * **-t name, --type name**
          deployment server type, default: *cpx11*

        * **-i architecture:type:name_or_description, --image architecture:type:name_or_description**
          deployment server image type and name or description,
          where the architecture is either: 'x86' or 'arm',
          and the type is either: 'system','snapshot','backup','app',
          default: *system:ubuntu-22.04*

        * **--setup-script path**
          path to custom deployment server setup script

      * **redeploy**
        redeploy on the same cloud service server

        * **--version number|latest**
          service package version to deploy, either a version number or 'latest',
          default: current package version

      * **log**
        get cloud service log

        * **-c name[:width][,...], --columns name[:width][,...]**
          comma separated list of columns to include and their optional width

        * **--raw**
          output raw log

        * **-f, --follow**
          follow log journal, default: *False*

        * **-n [+]number, --lines [+]number**
          output the last number of lines, with --follow the default is 10,
          use '+' before the number to output the log, starting with the line number

        * **command**

          * **delete**
            delete log

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

      * **log**
        get service log

        * **-c name[:width][,...], --columns name[:width][,...]**
          comma separated list of columns to include and their optional width

        * **-f, --follow**
          follow log journal, default: *False*

        * **-n [+]number, --lines [+]number**
          output the last number of lines, with --follow the default is 10,
          use '+' before the number to output the log, starting with the line number

        *  **--raw**
           output raw log

        * **command**

          * **format**
            format log

          * **delete**
            delete log

      * **start**
        start service

      * **stop**
        stop service

.. _Config class: https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/blob/main/testflows/github/hetzner/runners/config.py#L45
