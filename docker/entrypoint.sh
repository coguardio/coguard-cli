#!/bin/sh

DID_SOMETHING="";

# This is the docorator for the coguard command.
# It ensures that it is not run as root.
coguard_dec(){
    if [ "$(whoami)" = "root" ]
    then
	echo "/home/coguard/.local/bin/coguard $*";
	su coguard -c "/home/coguard/.local/bin/coguard $*";
    else
	coguard "$@";
    fi
}

if [ -n "$RUN_DOCKERD" ]
then
    # This assumes the container is running as root
    dockerd & 2>&1 /dev/null
    WAIT_COUNTER=0;
    MAX_RETRIES=20;
    while [ ! -f /var/run/docker.pid ]
    do
        sleep 1;
        if [ $WAIT_COUNTER -ge $MAX_RETRIES ]
        then
            echo "Failed to start the Docker service";
            exit 1;
        fi
        WAIT_COUNTER=$((WAIT_COUNTER+1))
        echo "Retry No $WAIT_COUNTER of $MAX_RETRIES"
    done
fi

if [ "$(ls -A "$SCAN_FOLDER")" ]
then
    coguard_dec folder "$SCAN_FOLDER";
    DID_SOMETHING=true;
fi

if [ -n "$DOCKER_IMAGE" ]
then
    coguard_dec docker-image "$DOCKER_IMAGE";
    DID_SOMETHING=true;
fi

if [ -n "$CLOUD" ]
then
    coguard_dec cloud "$CLOUD"
    DID_SOMETHING=true;
fi

if [ -z "$DID_SOMETHING" ]
then
    echo "No valid folder/docker-image/cloud was supplied."
fi
