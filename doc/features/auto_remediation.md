% Feature Highlight: Auto-Remediation

# General overview

The CoGuard CLI comes with the ability to perform auto-remediation
steps on scanned folders. Rules which are candidates for
auto-remediation are marked on the CLI formatted scan output with the
symbol 🔧.

The changes are applied using the CLI in-place. This means, ensure
that you are **backing up any data before running the CLI** with the
`--fix=true` instruction. The general assumption is that the folder
where the fixes are performed is version controlled (e.g. by
[Git](https://git-scm.com)).

The changes are not meant to be used right away for production, but to
be reviewed e.g. via a [pull
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

# Current level of auto-remediation

Currently, auto-remediation can only be applied to folder scans.

From our current rule-set, about 70% do have the possibility to be
auto-remediated. However, depending on the project, the distribution
of failed rules may lead to different percentages.

We are aiming to increase this number as part of our roadmap.
