% CLI Manual

# Version

0.2.11

# Installation

For installation instructions, please refer to this repositorie's [README page](../../README.md).

# Usage

## General CLI reference

```
coguard [-h] [--coguard-api-url COGUARD_API_URL]
             [--coguard-auth-url COGUARD_AUTH_URL]
             [--logging-level LOGGING_LEVEL]
             [--minimum-fail-level FAIL_LEVEL]
             [--output-format OUTPUT_FORMAT] [--ruleset {soc2,hipaa,}] [-v]
             {docker-image,folder,cloud,pipeline,scan} ...
```

### Options

| Option               | Parameter        | Documentation                                                                                                  |
|----------------------|------------------|----------------------------------------------------------------------------------------------------------------|
| -h, --help           | N/A              | show help message and exit                                                                                     |
| --coguard-api-url    | COGUARD_API_URL  | The url of the coguard api to call                                                                             |
| --coguard-auth-url   | COGUARD_AUTH_URL | The url of the authentication server                                                                           |
| --logging-level      | LOGGING_LEVEL    | The logging level of this call. Can be one of the following: DEBUG, INFO, WARNING, ERRROR, CRITICAL            |
| --minimum-fail-level | FAIL_LEVEL       | The minimum severity level of failed checks for this program to not give a non-zero exit code.                 |
| --output-format      | OUTPUT_FORMAT    | The format of the output. It is either `formatted` (default), i.e. human readable, or `json`.                  |
| --ruleset            | RULE_SET         | The non-default rule-set to use. The current options are `soc2` or `hipaa`                                     |
| --dry-run            | DRY_RUN          | When set to `true`, the CLI will generate a .zip file, but not upload it to the back-end for scanning/fixing.  |
| -v, --version        |                  | Show the CLI's version number and exit                                                                         |


## CLI usage

### General scanning information

All the scan types described below are run with default parameters by running

```
coguard scan
```

CoGuard requires that users to be authenticated using their CoGuard credentials. On 
first run, it will prompt users to sign in or to set up an account requiring both
an email address and a password. 

In a CI/CD pipeline scenario, user credentials can be set by the
following environment variables:

- `COGUARD_USER_NAME`
- `COGUARD_PASSWORD`

Every scan produces an output, unless the dry-run option is selected, containing the following information:

- A short description of the failed policy.
- A remediation instruction.
- A list of sources.
- Sometimes, references to compliance frameworks (if specific rulesets are chosen).

For CI/CD pipelines, it is possible to set
the severity level for which the CLI exits with a non-zero exit
code. By default, any failed scan result will cause the script to
fail. The `--minimum-fail-level` parameter sets the minimum fail
level, i.e. if one wishes to only fail the script (and subsequently
the pipeline job) for levels 4 or higher, one can set it here.

The `--dry-run` option can be used to create a Zip file that contains a manifest 
with the local ocation of all detected configuration files identified by the CLI. 
These configuration files will be uploaded ans scanned by the back-end. 


### Scanning of Docker images

Docker images are being scanned by running the command

```
coguard docker-image <IMAGE_ID>
```

The parameter `<IMAGE_ID>` specifies the image to be scanned. If the
image is not installed on the current machine, the Docker image will
be downloaded.

The file system of the image will be scanned for known configuration
files, which will be subsequently scanned and an output will be
generated.

For more details on the output format, consider the [subsection on the
output-formats](#output-format)

### Scanning of folders

Given a folder (e.g. your project's repository), a scan can be
performed by typing

```
coguard folder <PATH_TO_FOLDER>
```

The parameter `<PATH_TO_FOLDER>` specifies the folder whose contents
will be scanned for known configuration files.

If there are files that contain references to Docker images, these are
scanned as well. An example for such a reference may be the following
docker-compose file:

```
version: '3'
services:
  db:
    image: postgres
    ,,,
```

Here, the image `postgres` is referenced and will be included in the
report.

#### Auto-remediation

The folder scan can be instructed to perform automated fixes to errors
found. Additional details on the current state of what is auto-fixable,
please refer to [Auto-remediation](../features/auto_remediation.md).

To run auto-remediation, use the following command:

```
coguard folder <PATH_TO_FOLDER> --fix=true
```

The parameter `<PATH_TO_FOLDER>` specifies the folder whose contents
will be scanned for known configuration files. The fixes will be
applied directly to the configuration files. Our general
assumption is that the folder represents a IaC code repository, and that
the user can than review the changes by typing `git diff` or
equivalent commands.

**Remark:** The fixes are currently only applied to the files in the
file system, not to the referenced Docker images.

### Scanning of cloud setups

Using the CLI, snapshots of your current cloud setup can be extracted
as Terraform files and subsequently scanned. Currently, AWS, Azure and GCP are 
supported.

Authentication and credentials access vary for each service. Please see details below
for your service configuration. 

#### AWS

To scan AWS, type

```
coguard cloud aws
```

##### AWS Credentials 

This command assumes that the system where this command is run has the
credentials stored in one of the standard locations. For more details,
we refer to the [AWS SDK and Tools
documentation](https://docs.aws.amazon.com/sdkref/latest/guide/creds-config-files.html).

If there are multiple accounts referenced e.g. in the `credentials`
file, a prompt will be presented to make you choose the desired account.

The minimum requirements for the chosen account is read-only-access to
the cloud resources, as referenced e.g. by [this
policy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/ReadOnlyAccess.html).

#### GCP

To scan GCP, type

```
coguard cloud gcp
```

###### GCP Credentials 

This command assumes that you either are already logged in using the
`gcloud auth` command on your machine
([reference](https://cloud.google.com/sdk/gcloud/reference/auth/login)),
or you can supply the service account credentials using the option `--credentials-file
<YOUR_CREDS_FILE>`
([reference](https://cloud.google.com/iam/docs/keys-create-delete)).

If there are multiple accounts present, you may be prompted to select
the one you wish to use.

The minimum requirements for the chosen account is read-only-access to
the cloud resources, as referenced e.g. by [the viewer
role](https://cloud.google.com/iam/docs/understanding-roles).

#### Azure

To scan Azure, type

```
coguard cloud azure
```

##### Azure Credentials 

This command assumes that you are logged in to your azure account
using the
[Azure CLI](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli).

The minimum requirement for the chosen account is the
[`Reader`](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#reader)
role.


### Adding to CI/CD pipelines

The best way to integrate CoGuard into your workflow is by adding it
to your preferred CI/CD tool. A basic pipeline configuration can be
added to your repository by running

```
coguard pipeline <CI_CD_PROVIDER> add <PATH_TO_YOUR_FOLDER>
```

The `CI_CD_PROVIDER` is the pipeline provider to be used, and the
`<PATH_TO_YOUR_FOLDER` is the path to the repository. Currently, only
GitHub Actions are supported here.

## Supported rule-sets

If activated for your account, you can specify a specific rule set for
your scan. For a folder and a SOC2 ruleset, this is e.g. achieved by the following
command:

```
coguard --ruleset=soc2 folder <PATH_TO_YOUR_FOLDER>
```

This will alter the output of the report to bump any relevant checks
up to high or critical, and reference the respective compliance
sections for each check. Furthermore, for specific compliance
frameworks, some checks are used that are
unique to the compliance framework and would not appear in the normal
ruleset.

## Output format

You can specify the output format of the CLI. The current choices are

- `formatted` (default) and
- `json`

Formatted produces a formatted string of the failed rules and a
summary. The JSON option produces a machine-readable JSON for further
processing.
