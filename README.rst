.. image:: https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/master/images/logo_small.png
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
   See `Wiki <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki>`_ for full documentation.

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

========
Features
========

* simpler alternative to what GitHub lists in `Recommended Autoscaling Solutions <https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#recommended-autoscaling-solutions>`_
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
* supports meta labels to keep your job label list short
* supports estimating the cost of a job, a run, or a set of runs 

=================
Table of Contents
=================

* `Home <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki>`_
* `Installation <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Installation>`_
* `Quick Start <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Quick-Start>`_
* `Getting Started Tutorial <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Getting-Started-Tutorial>`_
* `Basic Configuration <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Basic-Configuration>`_
* `Specifying the Maximum Number of Runners <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-the-Maximum-Number-of-Runners>`_
* `Specifying the Maximum Number of Runners Used in Workflow a Run <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-the-Maximum-Number-of-Runners-Used-in-Workflow-a-Run>`_
* `Recycling Powered‐Off Servers <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Recycling-Powered‐Off-Servers>`_
* `Skipping Jobs <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Skipping-Jobs>`_
* `Using Custom Label Prefix <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Using-Custom-Label-Prefix>`_
* `Jobs That Require the Docker Engine <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Jobs-That-Require-the-Docker-Engine>`_
* `Specifying The Runner Type <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-The-Runner-Type>`_
* `Specifying The Runner Location <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-The-Runner-Location>`_
* `Specifying The Runner Image <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-The-Runner-Image>`_
* `Specifying The Custom Runner Server Setup Script <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-The-Custom-Runner-Server-Setup-Script>`_
* `Specifying The Custom Runner Server Startup Script <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-The-Custom-Runner-Server-Startup-Script>`_
* `Disabling Setup or Startup Scripts <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Disabling-Setup-Or-Startup-Scripts>`_
* `Specifying Standby Runners <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-Standby-Runners>`_
* `Specifying Logger Configuration <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-Logger-Configuration>`_
* `Listing All Current Servers <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Listing-All-Current-Servers>`_
* `Opening The SSH Client To The Server <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Opening-The-SSH-Client-To-The-Server>`_
* `Deleting All Runners and Their Servers <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Deleting-All-Runners-and-Their-Servers>`_
* `Using a Configuration File <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Using-a-Configuration-File>`_
* `Specifying SSH Key <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-SSH-Key>`_
* `Specifying Additional SSH Keys <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Specifying-Additional-SSH-Keys>`_
* `Running as a Service <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Running-as-a-Service>`_
* `Running as a Cloud Service <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Running-as-a-Cloud-Service>`_
* `Scaling Up Runners <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Scaling-Up-Runners>`_
* `Scaling Down Runners <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Scaling-Down-Runners>`_
* `Handling Failing Conditions <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Handling-Failing-Conditions>`_
* `Meta Labels <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Meta-Labels>`_
* `Program Options <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Program-Options>`_

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

-------------------------
Installation from Sources
-------------------------

For development, you can install from sources as follows:

.. code-block:: bash

   git clone https://github.com/testflows/testflows-github-hetzner-runners.git
   ./package && ./install

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

❶ Before we get started, you will need to install **testflows.github.hetzner.runners** Python package. See the `Installation <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Installation>`_ section for more details.

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
See the `Running as a Cloud Service <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Running-as-a-Cloud-Service>`_ section for details.

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
   **github-hetzner-runners cloud log -f** command. For other cloud service commands, see the `Running as a Cloud Service <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki/Running-as-a-Cloud-Service>`_ section.

   .. code-block:: bash

      github-hetzner-runners cloud log -f

----

🔍 See `Wiki <https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/wiki>`_ for full documentation.

Developed and maintained by the `TestFlows <https://testflows.com>`_ team.

.. _Config class: https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners/blob/main/testflows/github/hetzner/runners/config.py#L45
