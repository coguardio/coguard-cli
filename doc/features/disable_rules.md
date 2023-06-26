% Disabling rules

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
