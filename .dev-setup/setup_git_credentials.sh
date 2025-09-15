#!/bin/bash
# Default variable values
VERBOSE_MODE=false
KEEP_GIT_CREDENTIALS_FILE=false
PATH_PIP_SEARCH_FOLDER="./src"

# Function to display script usage
function usage {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo " -h, --help                     Display this help message"
    echo " -v, --verbose                  Enable verbose mode"
    echo " --git-credentials-file         use this git credentials file"
    echo " --use-ci-job-token             use CI_JOB_TOKEN as password"
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
      --git-credentials-file)
        if ! has_argument $@; then
          echo "File not specified." >&2
          usage
          exit 1
        fi

        GIT_CREDENTIALS_FILE=$(extract_argument $@)

        shift
        ;;
      --keep-git-credentials-file)
        KEEP_GIT_CREDENTIALS_FILE=true
        ;;
      --use-ci-job-token)
        USE_CI_JOB_TOKEN=true
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

function check_git_installed {
    if which git &> /dev/null; then
        echo "Git is installed"
    else
        echo "Installing git"
        apt update && apt install -y git
    fi
    return 0
}

function set_git_credentials {
    # echo "https://gitlab-ci-token:$CI_JOB_TOKEN@gitlab.com" > ~/.git-credentials
    # git config --global credential.helper store

    # git config --global credential.helper '!echo username=gitlab-ci-token && echo password=${CI_JOB_TOKEN}'
    # cd "$SCRIPT_DIR/.gitconfig" ~/
#     cat <<EOF > ~/.gitconfig
# [credential]
# 	username = gitlab-ci-token
# 	helper = "!f() { test \"\$1\" = get && echo \"password=\${CI_JOB_TOKEN}\"; }; f"
# EOF

#     cat ~/.gitconfig

    rv=0
    
    if [ -n "$GIT_CREDENTIALS_FILE" ]; then
        cp $GIT_CREDENTIALS_FILE ~/.git-credentials
        if [ $? -ne 0 ]; then
            echo "Failed to copy git credentials file"
            rv=1
        fi
        git config --global credential.helper store
    elif [ $USE_CI_JOB_TOKEN = true ]; then
        if [ -z "$CI_JOB_TOKEN" ]; then
            echo "CI_JOB_TOKEN is not set"
            rv=1
        fi
        git config --global credential.helper '!echo username=gitlab-ci-token && echo password=${CI_JOB_TOKEN}'
    else
        echo "No credentials provided"
        if [ -f ~/.git-credentials ]; then
            echo "git-credentials file exists"
        fi
        # rv=1
    fi

    return $rv
}


error_counter=0
commands=(
    "check_git_installed"
    "set_git_credentials"
)

# Loop over each command and execute it
for cmd in "${commands[@]}"; do
    # Use eval to allow executing commands with arguments
    eval "$cmd"
    if [ $? -ne 0 ]; then
        error_counter=$(( error_counter + 1 ))
        echo "ERROR: $cmd"
    fi
done

echo "error counter $error_counter"

exit $error_counter