#!/bin/bash

set -ex

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python -m coguard_cli docker-image "$IMAGE_NAME") | sort | shasum | awk '{print $1}' );
    test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
}

test_image_checksum "nginx:1.23.2" "2b1fdf1b027b303030902e10f493b31addd46133"
test_image_checksum "mysql:8.0.31" "fb0533458790eea3fd06fcc4b101f4f5148c8b0a"
test_image_checksum "postgres:15.1" "08aaf45a31d803a808ef536c0c52386f1a5e1682"
test_image_checksum "mongo:6.0.2" "5971491c217172119cea82e3847858f61df9188e"
test_image_checksum "mariadb:10.9.4" "2a7fe655123379d622dfc7bee507b5fdca6b8f3d"
test_image_checksum "bitnami/kafka:3.3.1" "46588b16697777169a16a4b989e879dc59bce07f"
test_image_checksum "httpd:2.4.54" "c09dbf644a9f06f1ca0c89aff50c064883d534ef"
test_image_checksum "elasticsearch:8.5.0" "695f9d62841dc59801dba57b1ef37247ae7fa386"
test_image_checksum "tomcat:9.0.69-jre17" "2c571b24ffad034ab6290a05b0fda37e32c6a3b9"
test_image_checksum "redis:7.0.5" "4284cefdfcdfaf844e70107670bdb4f83d910f89"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "e3a76c9b09a79eff23d95672c6fd5d067cc15db7"
