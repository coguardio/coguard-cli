![Coguard Logo](./logo.png)

# CoGuard

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

CoGuard CLI can either be pulled from this repository and used
directly, or installed via pip:

```
pip install coguard-cli
```

Keep in mind that it is a requirement to have Docker installed locally.

## How to use it

After installing the CoGuard CLI, you can run a scan on your local images
using

```
coguard docker-image [<YOUR-IMAGE-NAME-OR-ID>]
```

If you omit the image ID parameter, CoGuard will scan all the images currently
stored on your device.

This step requires you to create a CoGuard account.
After completion, this image check will return the findings of CoGuard
on this particular image.

## Current support and future plans

The currently supported auto-discovery of configuration files inside
Docker containers is limited to the finders
[in this folder](./src/image_check/config_file_finders/). This list
will expand in the future. In addition, we are scanning the
Dockerfile used to create the images, and will add some Linux
configuration files in the near future.

## Learn more

[CoGuard Website](https://www.coguard.io)
[CoGuard Blog](https://www.coguard.io/blog)
