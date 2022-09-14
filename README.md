![CoGuard Logo Dark](https://github.com/coguardio/coguard-cli/raw/master/logo_dark_mode.png#gh-dark-mode-only)![CoGuard_Light_Logo](https://github.com/coguardio/coguard-cli/raw/master/logo.png#gh-light-mode-only)

# CoGuard

## Why CoGuard

Infrastructure as Code (IaC) is here to stay. The versioning and
continuous scanning of every layer of your IT (on premise and cloud)
infrastructure is crucial.

CoGuard's team observed that there are a lot of policy checks on the layers
communicating to the cloud, but the configurations inside specific
compute devices such as physical servers, virtual machines or
containers are mostly neglected, or have silo-ed solutions at best.

In order to have static analysis practices for IaC that go as deep as
the available tools for code, every layer needs to be equally addressed.

In our practice, we observed that, at times, even an awareness of
locations of configuration files is lacking. This is why we created a
command line tool helping with discovering those configurations, and
scanning them.

As an initial starting point for the CLI, we chose Docker images. Modern
container scanners check for versions of software and libraries
installed on those containers, and establish if there are common known
vulnerabilities and exposures (CVEs). The
CoGuard CLI is trying to find known configuration files for e.g. web
servers or databases, and scans these for security and best practice.
Additionally, the last Docker file used to create an image is analyzed
as well.

## Introduction to the CoGuard CLI

CoGuard is a comprehensive static analysis tool for IT infrastructure
configurations (cloud and on-premise).

This project is the command line interface to CoGuard, with additional
auto-discovery functionality.

In its current release, it scans Docker images and its contents.
In particular, it searches for known configuration files of different
software packages (like webservers, databases, etc.), and scans these
configurations for security and best practice.

## How to install it

### Pre-Requisites

You need to have `python3`, `pip3` and `docker` installed on your system.
Here are the different operating systems and commands to be used for Python and Pip.

<details>
<summary>Ubuntu/Debian</summary>

```shell
sudo apt install -y python3 python3-pip
```
</details>

<details>
<summary>Alpine</summary>

```shell
apk add python3 py3-pip
```
</details>

<details>
<summary>CentOS/Fedora</summary>

```shell
sudo yum install -y python3 python3-pip
```
</details>

<details>
<summary>Arch Linux</summary>

```shell
sudo pacman -S python python-pip
```
</details>

<details>
<summary>Mac OS</summary>
Assuming you are using [Homebrew](https://brew.sh), you have to run

```shell
brew install python3
```
</details>

<details>
<summary>Windows</summary>

Download Python3 for Windows using [this link](https://www.python.org/downloads/windows/), and
install it.

</details>

### Installation

CoGuard CLI can either be pulled from this repository and used
directly, or installed via `pip`:

```shell
pip3 install coguard-cli
```

Keep in mind that it is a requirement to have Docker installed locally.

## How to use it

After installing the CoGuard CLI, you can run a scan on your local images
using

```shell
coguard docker-image [<YOUR-IMAGE-NAME-OR-ID>]
```

**Remark 1**: It may happen that the folder where `pip` is installing packages is not
in included in `PATH`. We have observed it on some Ubuntu installations, and on
Homebrew Mac installs. For the Linux case, such as Ubuntu,
you can find the binary usually under `$HOME/.local/bin/coguard`, i.e. you run
```shell
$HOME/.local/bin/coguard docker-image [<YOUR-IMAGE-NAME-OR-ID>]
```
For the Mac case, it is often installed under `~/Library/Python/<YOUR_PYTHON_VERSION>/bin/coguard`, i.e. you would run
```shell
~/Library/Python/<YOUR_PYTHON_VERSION>/bin/coguard docker-image [<YOUR-IMAGE-NAME-OR-ID>]
```

**Remark 2**: Windows users need to be allowed to create and read symbolic links.
This can be achieved using three options:
<details>
<summary>Option 1</summary>
1. Run the CoGuard execution as admin temporarily. This can be achieved by opening the
   PowerShell or command prompt as administrative user (right click on the icon),
   or by issuing the command
   ```shell
   Start-Process powershell -Verb runAs
   ```
   inside an already open command/Powershell window.
</details>
<details>
<summary>Option 2</summary>
2. Run Windows in Developer Mode (instructions on how to run Windows as a developer can
   be found [here](https://docs.microsoft.com/en-us/gaming/game-bar/guide/developer-mode)).
</details>
<details>
<summary>Option 3</summary>
3. Run CoGuard on a Linux virtual machine, e.g. using the Windows subsystem for Linux.
   This is commonly installed with Docker Desktop for Windows. If you do not have it installed,
   then installation instructions can be found
   [here](https://docs.microsoft.com/en-us/windows/wsl/install).
   The installation steps for CoGuard using WSL are equivalent to the pre-requisites
   and installation steps described for Linux (dependent on the distribution you choose).
</details>


If you omit the image ID parameter, CoGuard will scan all the images currently
stored on your device.

This step requires you to create a CoGuard account.
After completion, this image check will return the findings of CoGuard
on this particular image. You can view the latest historical scan results
when logging in to [https://portal.coguard.io](https://portal.coguard.io).

Here is a screenshot of a sample scan:

![](./screenshot.png)

As you can see, CoGuard also analyzes the last Dockerfile used.

The checks are gathered from different security benchmarks, such as CIS, but also
directly from the user manuals of these software projects. At times, known issues for
certain versions and security remediations specific to a certain version are being taken
into account as well.

## Current support and future plans

The currently supported auto-discovery of configuration files inside
Docker containers is limited to the finders
[in this folder](https://github.com/coguardio/coguard-cli/tree/master/src/coguard_cli/image_check/config_file_finders).
The list includes, among others,

- Apache Kafka
- Apache Tomcat
- Apache WebServer
- ElasticSearch
- Kerberos
- MongoDB
- MySQL
- NGINX
- OpenTelemetry Collector
- PostgreSQL

This list
will expand in the future. In addition, we are scanning the
Dockerfile used to create the images, and will add some Linux
configuration files in the near future.

## Learn more

- [CoGuard Website](https://www.coguard.io)
- [CoGuard Blog](https://www.coguard.io/blog)
