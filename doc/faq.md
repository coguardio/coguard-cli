% Frequently asked Questions (FAQ)

# Why is the CLI tool not published as a Docker image?

Since much of our scanning is performed on Docker images, the
execution of the CoGuard CLI inside a container would require for the
container to either run in `privileged` mode or to have access the
host's Docker socket as a volume. Both options are considered bad
practice and even security violations. Hence, the best way to run the
CoGuard CLI is by installing it through PIP directly.
