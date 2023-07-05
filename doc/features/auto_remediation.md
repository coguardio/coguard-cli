% Feature Highlight: Auto-Remediation

# General overview

The CoGuard CLI comes with the ability to perform auto-remediation
steps on scanned folders. Rules which are candidates for
auto-remediation are identified on the CLI formatted scan output with the
symbol 🔧.

Auto-remediation changes are applied by the CLI are in-place. This means,
that changes are executed live in the filesystem. We assume that the folder
being scanned and where the changes are performed is version controlled (e.g. by
[Git](https://git-scm.com)). Please ensure you have **backed up any files before 
running the CLI** with the `--fix=true` instruction. 

The changes are meant to be reviewed before being deployed, i.e., they are not meant
to be used immediately in production. Changes can be reviewed as part of the IaC develop review 
process, e.g. via a [pull
request](https://www.git-scm.com/docs/git-request-pull).

In many cases, the desired value is right away filled in. For other
rules, the value is set to a placeholder called `USER_INSERT_VALUE`.
An example for such a control are the recommended health-check
instructions for a Dockerfile
([reference](https://docs.docker.com/engine/reference/builder/#healthcheck)). This
value should exist, but it is very custom to each container. Hence,
the auto-fix instruction is adding the line
```
HEALTHCHECK USER_INSERT_VALUE
```
to instruct the user to add some basic parameter there.

# Current state of auto-remediation

Auto-remediation can be applied only to folder scans.

The current rule-set does not have 100% coverage for auto-remediation, we have auto-remediation 
coverage for about 70% of our existing rules. Depending
on the project, the distribution of failed rules with auto-remediation fixes will 
vary. The product roadmap has increase coverage in future releases to address the current rule
set. 
