# CoGuard Coverity integration

## Overview

CoGuard integrates seamlessly with BlackDuck's Coverity product,
enhancing the static code analysis capabilities with configuration file
discovery and misconfiguration detection.

## Prerequisites

To enable this integration, ensure the following:

- A valid Coverity license.
- A valid CoGuard Enterprise subscription.

## How It Works

CoGuard and Coverity are designed to be included in your CI/CD pipeline. This can
be achieved via a simple bash script, or the domain specific language of your
CI/CD tool.

Asides from setting up the Coverity executables and the CoGuard CLI,
there are four steps involved for your pipeline script.

1. Perform the Coverity scan.
2. Perform the CoGuard scan.
3. Execute the `coguard-coverity-translator` (shipped with the CoGuard CLI) script on the CoGuard result folder.
4. Run the Coverity import and commit scripts.

An example shell script can be found [here](https://github.com/coguardio/coverity_integration/blob/main/example_scripts/example_1.sh).

## Features

## Integration Features

### Coverity scans your code, CoGuard scans your configurations.

Coverity is the leader in static code analysis for any leading
programming language. Modern softare depends on infrastructure for
delivery and functionality, and hence scanning these configurations
is a canonical extension of security efforts to ensure secure and
reliable functionality of your services.

### Coverity and CoGuard reports, all in one dashboard.

This integration enables you to see both infrastructure related issues,
as well as code issues, to be displayed in one dashboard: Coverity.

### Remediation help

Iterate quickly through your issues by using CoGuard's auto-remediation feature,
allowing your developers to save time and focus on the most important and complex
issues.

## FAQs

## Coverity was already scanning my IaC files through. How does this integration extend the current capabilities?

While the current scanning capabilities capture IaC misconfigurations,
this extension allows to also detect misconfigurations for software commonly deployed
in your infrastructure (Postgres, Kafka, Hadoop, Cassandra, MongoDB, Redis, etc.).

## The adoption of IaC tools is not that far yet in our organization. Can we still benefit from this integration?

CoGuard can extract your current configurations from your cloud
environment, and the CLI can even find configurations within your
running servers and containers. This allows you to already have the
visibility into your infrastructure security posture, while enabling
you to move towards an automated, infrastructure as code environment.

## How much extra time does the scan require in my CI/CD pipeline?

The average scan is done in 30s or less. Cloud snapshot extractions
and scans depend on the number of different resources you have running
on the cloud, but average out to take 20 minutes.

## The initial examples are using GitHub Actions. Is there support for other CI/CD tooling?

The evidence uploads can be performed on any other common CI/CD
platform, such as Jenkins, Bitbucket pipelines, CircleCI, etc. Our
team is happy to help you get set up.


## Get Started

Start leveraging CoGuard’s powerful scanning capabilities in
conjunction with Coverity today. Contact us to get
started today.
