#!/bin/bash

set -ex

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

IS_TEST=${1:-false};

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/$IMAGE_NAME" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    fi
    rm -rf "${TEMP_DIR:-?}/$IMAGE_NAME"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        test "$ACTUAL_CHECKSUM" = "$EXPECTED_CHECKSUM"
    fi
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

test_folder_fix() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir --fix=true)
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
}

# Docker image tests

test_image_checksum "nginx:1.23.2" "e1ccb91d20bcee9271b0546e4f7499da8b1deb4e"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "ab23c1f34b955ee1b429fdf098330e9cdd8dde01"
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "4fa159437ff236e7cf2195a53e213e2f17f7b5d5"
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "11573dd2bb16683135ca303bb029ee0b1b1ae4a1"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "4f418ef75d40ce02afe4cc0bdf8e4e226988a524"
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "4b5aecbe74d0fbd6a68c68e832747e44e3a66768"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "e6d488c86d9dfea31744f5f92c1c149c3735771a"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "15fdb4ff7d4e8cdfddd18eeb73dbdb84dc99e003"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "d15dcf7d045acbf0de181104ac3dcfe6006d1342"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "80d3e29fc531047a40430194b6df1f0451db1fbc"
docker image rm "redis:7.0.5"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "675d7d4d5c7767c4b7d5206de773ef103085c96e"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df 867e652184afe21bb64595a7979d5f05f8dec121
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 0b431aedcbb590656f66690564d0a4ea332963bd
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 19fdae45c1fce89367fda1c667ece3f98ddf30e9
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 96dc98e625b5373406ad619fd7d4af951a316df9
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 7adf1f439662c5f433044a63b63462e88149bb86
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

rm -rf "$TEMP_DIR"
