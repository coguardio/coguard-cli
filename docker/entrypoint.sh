#!/bin/sh

DID_SOMETHING="";

if [ "$(ls -A "$SCAN_FOLDER")" ]
then
    coguard folder "$SCAN_FOLDER";
    DID_SOMETHING=true;
fi

if [ -n "$DOCKER_IMAGE" ]
then
    coguard docker-image "$DOCKER_IMAGE";
    DID_SOMETHING=true;
fi

if [ -n "$CLOUD" ]
then
    coguard cloud "$CLOUD"
    DID_SOMETHING=true;
fi

if [ -z "$DID_SOMETHING" ]
then
    echo "No valid folder/docker-image/cloud was supplied."
fi
