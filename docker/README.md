# CoGuard Docker image

## Authentication

If the user wishes to interactively authenticate, the following docker
run instructions should be executed with the flag `-it`. All examples will
be presented in this way. If the user wishes to instead use an environment file for
the authentication, an `.env` file needs to be created with the
variables `COGUARD_USER_NAME` and `COGUARD_PASSWORD` variables, and
run via

```
docker run --env-file=path/to/.env/file ...
```

## Scanning

### Scanning a folder (repository scanning)

In order to scan a folder, it needs to be mounted as a volume.

```
docker run -it \
           -v ${PATH_TO_FOLDER}:/opt/folder \
           -v /var/run/docker.sock:/var/run/docker.sock \
           coguard-cli
```

### Scanning a Docker image

In order to scan a Docker image, it needs to be communicated via a
variable to the system.

```
docker run -it -e DOCKER_IMAGE=${YOUR_DOCKER_IMAGE} --privileged -v /var/run/docker.sock:/var/run/docker.sock coguard-cli
```

### Scanning a cloud snapshot

In order to scan a snapshot of your current cloud setup, you can run
the following.

```
docker run --privileged -it -e CLOUD=${YOUR_CLOUD} -v /var/run/docker.sock:/var/run/docker.sock coguard-cli
```

Currently, the three valid options for CLOUD are `aws`, `gcp` and
`azure`. Any authentication-relevant information needs to be entered
via environment variables.

## Challenges and solutions

Since CoGuard is scanning Docker-images and referenced Docker-images
whenever it finds it in the repository, CoGuard needs to be able to pull
Docker image and perform other Docker-related operations.

One way of achieving this is by giving the container access to the
Docker socket of the host via
```
-v /var/run/docker.sock:/var/run/docker.sock
```
and setting the `--privileged` flag. It also needs to be ensured
that the user inside the Docker container has read privileges to
that socket.

One can also opt of running `dockerd` inside that container. This
will still require the `--privileged` flag, but not the mounting of
the docker-socket. The container supports an own `dockerd` out of the
box by running the container as `root` and setting the environment
variable `RUN_DOCKERD` to a non-empty value.
