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
docker run -it -e DOCKER_IMAGE=${YOUR_DOCKER_IMAGE} -v /var/run/docker.sock:/var/run/docker.sock coguard-cli
```

### Scanning a cloud snapshot

In order to scan a snapshot of your current cloud setup, you can run
the following.

```
docker run -it -e CLOUD=${YOUR_CLOUD} -v /var/run/docker.sock:/var/run/docker.sock coguard-cli
```

Currently, the three valid options for CLOUD are `aws`, `gcp` and
`azure`. Any authentication-relevant information needs to be entered
via environment variables.

## Challenges

Since CoGuard is scanning Docker-images and referenced Docker-images
whenever it finds it in the repository, CoGuard needs access to the
host's Docker socket.

For that, it needs to be ensured that the permissions on the
`/var/run/docker.sock` are set so that the `other` user category can
access it.
