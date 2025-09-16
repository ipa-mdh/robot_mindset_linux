#!/bin/bash
# Default variable values
VERBOSE_MODE=false
CONTAINER_ARGS=()

# Function to display script usage
function usage {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo " -h, --help           Display this help message"
    echo " -v, --verbose        Enable verbose mode"
    echo " -- [arguments]       Forward all remaining arguments to the Docker container"
}

function has_argument {
    [[ ("$1" == *=* && -n ${1#*=}) || ( ! -z "$2" && "$2" != -*)  ]];
}

function extract_argument {
  echo "${2:-${1#*=}}"
}

# Function to handle options and arguments
function handle_options {
  while [ $# -gt 0 ]; do
    case $1 in
        -h | --help)
            usage
            exit 0
            ;;
        -v | --verbose)
            VERBOSE_MODE=true
            ;;
        --)
            shift
            CONTAINER_ARGS=("$@")
            break
            ;;
        *)
            echo "Invalid option: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
  done
}

# Main script execution
handle_options "$@"

if [ "$VERBOSE_MODE" = true ]; then
    set -x
fi

function run_container_with_arguments {
    docker run -it \
	    --publish=8080:8080 \
        robot_mindset_linux:run-1.0 \
        "${CONTAINER_ARGS[@]}"
}

function run_container_without_arguments {
    docker run -it \
	    --publish=8080:8080 \
        robot_mindset_linux:run-1.0
}

# If CONTAINER_ARGS empty
if [ -z "$CONTAINER_ARGS" ]; then
    run_container_without_arguments
else
    run_container_with_arguments
fi