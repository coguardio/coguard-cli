#!/bin/bash

set -e

test -n "$COGUARD_USER_NAME"
test -n "$COGUARD_PASSWORD"

IS_TEST=${1:-false};

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TEMP_DIR="$(mktemp -d)";

echo "Created temp directory $TEMP_DIR to store the temporary directory results."

test_image_checksum() {
    IMAGE_NAME="$1";
    EXPECTED_CHECKSUM="$2"
    COMPLIANCE=${3:-""}
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth docker-image "$IMAGE_NAME") | sed 1,18d | tee "$TEMP_DIR/image_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        if [ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]
        then
            echo "ACTUAL checksum matched EXPECTED checksum for $IMAGE_NAME";
        else
            echo "ACTUAL: $ACTUAL_CHECKSUM";
            echo "EXPECTED: $EXPECTED_CHECKSUM";
            echo "ACTUAL OUTPUT:";
            cat "$TEMP_DIR/image_check.txt";
            exit 1;
        fi
    fi
    rm -rf "${TEMP_DIR:-?}/image_check.txt"
}

test_folder_checksum() {
    GIT_REPO="$1";
    GIT_HASH="$2";
    EXPECTED_CHECKSUM="$3";
    COMPLIANCE=${4:-""}
    git clone "$GIT_REPO" "$TEMP_DIR"/tmp_repo_dir;
    git -C "$TEMP_DIR"/tmp_repo_dir checkout "$GIT_HASH";
    ACTUAL_CHECKSUM=$( (cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --ruleset="$COMPLIANCE" --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/tmp_repo_dir) | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}' );
    if [ "$IS_TEST" == "true" ]
    then
        echo "ACTUAL: $ACTUAL_CHECKSUM";
        echo "EXPECTED: $EXPECTED_CHECKSUM"
    else
        if [ "$ACTUAL_CHECKSUM" == "$EXPECTED_CHECKSUM" ]
        then
            echo "ACTUAL checksum matched EXPECTED checksum for $GIT_REPO";
        else
            echo "ACTUAL: $ACTUAL_CHECKSUM";
            echo "EXPECTED: $EXPECTED_CHECKSUM";
            echo "ACTUAL OUTPUT:";
            cat "$TEMP_DIR/folder_check.txt";
            exit 1;
        fi
    fi
    rm -rf "${TEMP_DIR:-?}/tmp_repo_dir";
    rm -rf "$TEMP_DIR/folder_check.txt";
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

test_image_checksum "nginx:1.23.2" "fa46fc577dafcb4684287a4854102a12f90dd940"
docker image rm "nginx:1.23.2"
test_image_checksum "mysql:8.0.31" "dda34193c1d3213626bc1a5f155c380eb5cbd323"
test_image_checksum "mysql:8.0.31" "d65610214bb17cbf3b9c65f3a2467acdd0a7857c" stig
docker image rm "mysql:8.0.31"
test_image_checksum "postgres:15.1" "2ff64048c2bfec0b486923b7f3f4696f079fc333"
test_image_checksum "postgres:15.1" "b9ee3668416f2241e75e29bc2aa263898c56d52f" soc2
docker image rm "postgres:15.1"
test_image_checksum "mongo:6.0.2" "ed1b781f6c4766492f5dfec9a08911103d4a7709"
docker image rm "mongo:6.0.2"
test_image_checksum "mariadb:10.9.4" "5e02a7ee3af81d441a4618cb64013024439e772e"
test_image_checksum "mariadb:10.9.4" "7c3b9cf5dff36df9c4f4a1a6411c2a7731542bd8" hipaa
docker image rm "mariadb:10.9.4"
test_image_checksum "bitnami/kafka:3.3.1" "a002a4c5a0319e0ddfbd0c6c565a1fdd1848c811"
docker image rm "bitnami/kafka:3.3.1"
test_image_checksum "httpd:2.4.54" "f906d9ed32513540a12d73603b98b8678742d59e"
docker image rm "httpd:2.4.54"
test_image_checksum "elasticsearch:8.5.0" "2138601d688615ad6ac277e2de1bb07fb0176a36"
docker image rm "elasticsearch:8.5.0"
test_image_checksum "tomcat:9.0.69-jre17" "23bd82b42026bbd427c3e76747e70bd41be70be5"
docker image rm "tomcat:9.0.69-jre17"
test_image_checksum "redis:7.0.5" "55afff4ee9dc3c807550a68ed332e035d388273a"
docker image rm "redis:7.0.5"
test_image_checksum "rethinkdb:2.4.4-bookworm-slim" "728e5bff42a891911520e394a04a11f05439159a"
docker image rm "rethinkdb:2.4.4-bookworm-slim"
test_image_checksum "amazon/aws-otel-collector:v0.22.1" "9a8076467bd2e789f61c72a828633b29477bdca9"
docker image rm "amazon/aws-otel-collector:v0.22.1"

# Git repository tests

test_folder_checksum https://github.com/ethereum/remix-project.git 56a08b2d913355002087492781d008286b1348df e3c991f1c2cc98a0af2f50913ea764ecc38d4d22
test_folder_checksum https://github.com/jaegertracing/jaeger-operator.git 7e668d84b948b8366b46eaf5dfe0c0a849e943e4 b90fd3d318af7f0cb3c9a134681733a34ddbc63e
test_folder_checksum https://github.com/open-telemetry/opentelemetry-collector.git 7318c14f1a2b5a91d02171a0649be430cb27da94 5ab34c83e55232b65d09458c406030def9a8b058
test_folder_checksum https://github.com/prisma/prisma.git 98eb6ed30dd41d2978142f704b8caa4a0ed412f6 d556d05bdb095d2278a450240ae92e7f384520ac
test_folder_checksum https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244 be34aedb726dcf8b82fef179d804d0de592fbca2
test_folder_fix https://github.com/zabbix/zabbix.git 3cbf261947d2b4148dd6a29dfcf5b1a15a857244

# Test with a weird name
git clone https://github.com/ethereum/remix-project.git "$TEMP_DIR"/"tmp_repo_dir (1)";
(cd "$SCRIPTPATH"/../src && python3 -m coguard_cli --coguard-api-url https://test.coguard.io/server --coguard-auth-url https://test.coguard.io/auth folder "${TEMP_DIR:-?}"/"tmp_repo_dir (1)") | sed 1,18d | tee "$TEMP_DIR/folder_check.txt" | sort | sha1sum | awk '{print $1}'

rm -rf "$TEMP_DIR"
