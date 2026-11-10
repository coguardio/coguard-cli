#!/usr/bin/env bash
#
# Sourced by the Cloudera Manager agent before it starts a process of a service
# which requires the `coguard` parcel tag, i.e. the Configuration Check role of
# the Configuration Assurance service. PARCELS_ROOT and PARCEL_DIRNAME are set by
# the agent; the fallback is the name of the active-version symlink, which the
# parcel asks for with `setActiveSymlink`.

COGUARD_DIRNAME=${PARCEL_DIRNAME:-"COGUARD"}
export COGUARD_HOME="${PARCELS_ROOT}/${COGUARD_DIRNAME}"
export PATH="${COGUARD_HOME}/bin:${PATH}"
