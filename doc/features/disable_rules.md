# Disabling rules

In some cases, a failed check may be chosen to be ignored by the
respective DevOps team. One of the many possible reasons would be
because legacy components are being used.

Similar to all common scanners/linters, CoGuard enables the disabling
of rules through a comment in the respective configuration file.

The comment format is

```
coguard-config-checker: disable <RULE_IDENTIFIER> <REASON>
```

The `<RULE_IDENTIFIER>` is the `snake_case` identifier that appears in
the report (e.g. `dockerfile_shell_check_on_run_commands`). The
`<REASON>` field is a description as of why this rule should be
disabled. It is possible to span it over multiple lines.

In this way, the disabling of the rule is tracked in the
code-repository, and reasons are provided so that the rationale can be
understood in the future (and always determined if it still applies).

# Ignoring files or whole directories

To instruct CoGuard-CLI to ignore specific sections or files during
analysis, you can utilize a file named `.coguardignore`. This file
should be placed at the root directory of your repository.

## Syntax

The .coguardignore file supports Unix-shell style wildcards or concrete file paths, all specified relative to the directory where the .coguardignore file is located.

The following syntax rules apply:

- Lines starting with # are treated as comments and are ignored.
- Empty lines are also ignored.
- Each non-comment, non-empty line represents a pattern to be matched against section names or file paths.
- The paths are interpreted to be relative to the location of the
  `.coguardignore` file.
- Otherwise, the pattern is matched against the names of sections or files within the repository.

## Examples

Here are some examples of valid patterns:

To ignore a specific file named `example.js`, add the following line:

```
example.js
```

To ignore all yaml files, you can use the wildcard *.yaml:

```
*.yaml
```

To ignore a directory named tests, you can use:

```
tests/*
```
