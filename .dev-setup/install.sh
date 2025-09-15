#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default variable values
VERBOSE_MODE=false
KEEP_GIT_CREDENTIALS_FILE=false
PATH_CONAN_SEARCH_FOLDER="./src"
PATH_CONAN_OUTPUT_FOLDER="/opt/dev-setup/conan"
PATH_PIP_SEARCH_FOLDER="./src"
PATH_VCS_WORKING_DIRECTORY="./src"
# PIP_VENV_PATH="venv"

# Function to display script usage
function usage {
    echo "Execute this script to install dependencies for the project."
    echo "This script sould be run from the root of the workspace."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo " -h, --help                     Display this help message"
    echo " -v, --verbose                  Enable verbose mode"
    echo " --git-credentials-file         use this git credentials file"
    echo " --keep-git-credentials-file    keep git credentials file (default: does not keep)"
    echo " --use-ci-job-token             use CI_JOB_TOKEN as password"
    echo " --path-pip-search-folder       path to search for directories matching the pattern 'module/resource/module' (default: ./src, if not exists, does not search)"
    # echo " --pip-venv-path                path of the pip virtual environment (default: venv)"
}

# Function to check if an argument is provided
# Arguments:
#   $1: The argument to check
#   $2: The value to check against (optional)
# Returns:
#   0 if the argument is provided, 1 otherwise
# Usage:
#   has_argument --option=value
#   has_argument --option
#   has_argument --option value
function has_argument {
    [[ ("$1" == *=* && -n ${1#*=}) || ( ! -z "$2" && "$2" != -*)  ]];
}

# Function to extract the argument value
# Arguments:
#   $1: The argument to extract from
#   $2: The value to extract (optional)
# Returns:
#   The extracted value
# Usage:
#   extract_argument --option=value
#   extract_argument --option
function extract_argument {
  echo "${2:-${1#*=}}"
}

# Function to handle options and arguments
# Arguments:
#   $1: The options and arguments to handle
# Returns:
#   None
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
      --path-pip-search-folder)
        if ! has_argument $@; then
          echo "Path not specified." >&2
          usage
          exit 1
        fi

        PATH_PIP_SEARCH_FOLDER=$(extract_argument $@)

        shift
        ;;
    #   --pip-venv-path)
    #     if ! has_argument $@; then
    #       echo "Path not specified." >&2
    #       usage
    #       exit 1
    #     fi

    #     PIP_VENV_PATH=$(extract_argument $@)

    #     shift
    #     ;;
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

# Perform the desired actions based on the provided flags and arguments
if [ "$VERBOSE_MODE" = true ]; then
 echo "Verbose mode enabled."
 set -x
fi

# Function to check if the app version is greater than or equal to the specified version
# Arguments:
#   $1: The app version to check
#   $2: The version to compare against
# Returns:
#   1 if the app version is greater than or equal to the specified version, 0 otherwise
# Usage:
#   check_version "1.2.3" "1.2.4"
function check_version_greater_equal {
    APPVER=$1
    VERSION=$2

    rv=0

    if { echo "$APPVER"; echo "$VERSION"; } | sort --reverse --version-sort --check=quiet; then
        echo "App version is $VERSION or greater"
        rv=1
    else
        echo "App version is less than $VERSION"
        rv=0
    fi
    return $rv
}

# Function to check if the pip version is greater than or equal to the specified version where
# the --break-system-packages option was introduced.
# Arguments:
#   None
# Returns:
#   0 if the pip version is less than the required version, 1 otherwise
# Usage:
#   check_pip_version_use_break_system_packages
function check_pip_version_use_break_system_packages {
    # Get the pip version
    pip_version=$(pip3 --version | awk '{print $2}')

    # last version without --break-system-packages option
    # https://pip.pypa.io/en/stable/news/#v23-0-1
    required_version="23.0.1"
    check_version_greater_equal "$pip_version" "$required_version"
    if [ $? -eq 1 ]; then
        echo "Pip version is $pip_version, which is greater than or equal to $required_version"
        return 1
    else
        echo "Pip version is $pip_version, which is less than $required_version"
        return 0
    fi
}

function install_apt_deps {
    rv=0
    apt update
    apt install -y \
        python3-pip \
        python3-virtualenv \
        git
    rv=$?
    return $rv
}

function install_pip_deps {
    rv=0

    # Check if file exists
    requirements_file="$SCRIPT_DIR/requirements.txt"
    if [ ! -f "$requirements_file" ]; then
        echo "ERROR: $requirements_file not found"
        return 1
    fi

    # Install packages

    check_pip_version_use_break_system_packages
    if [ $? -eq 1 ]; then
        pip3 install --break-system-packages -r "$requirements_file"
    else
        pip3 install -r "$requirements_file"
    fi
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install pip dependencies from $requirements_file"
        rv=1
    else
        echo "All pip dependencies installed successfully"
        rv=0
    fi

    return $rv
}

# This script searches for directories matching the pattern 'module/resource/module',
# where 'module' can be any name, and installs files within them using pip.
#
# Arguments:
#   path: The path to search for directories matching the pattern.
#
function install_module_resources {
    rv=0
    path=$1

    if [ -d "$path" ]; then
        # Find directories matching the pattern
        find "$path" -type d | while read -r dir; do
            # Get the components of the path
            IFS='/' read -ra path_components <<< "$dir"

            # Iterate over the indices of the path components
            for i in "${!path_components[@]}"; do
                # Check if the current component is 'resource'
                if [[ "${path_components[$i]}" == "resource" ]]; then
                    echo "------"
                    # Ensure there is a component before and after 'resource'
                    if [[ $i -ge 1 ]]; then
                        # Extract the module names before and after 'resource'
                        module="${path_components[$((i - 1))]}"

                        # Reconstruct the full path to the target directory
                        target_dir="${dir}"

                        # Print information about the directory and its modules
                        echo "Found directory: $target_dir"
                        echo "Module before 'resource': $module"

                        # Install files within the target directory
                        for file in "$target_dir"/*; do
                            filename=$(basename "$file")
                            echo "Checking file: $filename"
                            if [ "$module" == "$filename" ]; then
                                echo "Installing from $file"
                                # Check if pip version supports --break-system-packages
                                check_pip_version_use_break_system_packages
                                if [ $? -eq 1 ]; then
                                    # If pip version is less than required, use --break-system-packages
                                    pip3 install --break-system-packages -r "$file"
                                else
                                    pip3 install -r "$file"
                                fi
                                if [ $? -ne 0 ]; then
                                    rv=$rv+1
                                fi
                            elif [ "$module.apt" == "$filename" ]; then
                                echo "Installing from $file"
                                xargs -a "$file" apt install -y
                                if [ $? -ne 0 ]; then
                                    rv=$rv+1
                                fi
                            fi
                        done

                        # Break to avoid multiple processing of the same directory
                        break
                    fi
                fi
            done
        done
    else
        echo "No directory found at $path"
        ls -l
        rv=1
    fi

    return $rv
}

function install_ros_deps {
    command -v rosdep > /dev/null 2>&1
    installed=$?
    if [ $installed = '0' ]; then
        echo "rosdep is installed"
        rosdep install --from-paths src --ignore-src -r -y
        rv=$?
    else
        echo "rosdep is not installed"
        rv=0
    fi

    return $rv
}

function clone_repos {
    rv=0
    # cd "$SCRIPT_DIR/.."
    # Check if src directory exists
    if [ ! -d "$PATH_VCS_WORKING_DIRECTORY" ]; then
        echo "Directory $PATH_VCS_WORKING_DIRECTORY does not exist. This script should be run from the root of the workspace."
        rv=1
    else
        cd "$PATH_VCS_WORKING_DIRECTORY"

        find . -type f -name ".rosinstall" | while read -r rosinstall_path; do
            rosinstall_dir=$(dirname "$rosinstall_path")
            echo "Running 'vcs import in: $PATH_VCS_WORKING_DIRECTORY"
            
            # Change to the directory containing the .rosinstall file
            vcs import . < "$rosinstall_dir/.rosinstall" --recursive  --shallow
        done
        cd -
    fi
    rv=$?
    return $rv
}

# function update_git_submodules {
#     rv=0
#     # Check if src directory exists
#     if [ ! -d "$PATH_VCS_WORKING_DIRECTORY" ]; then
#         echo "Directory $PATH_VCS_WORKING_DIRECTORY does not exist. This script should be run from the root of the workspace."
#         rv=1
#     else
#         find "$PATH_VCS_WORKING_DIRECTORY" -type d | while read -r dir; do
#             if [ -f "$dir/GET_SUBMODULE" ]; then
#                 echo "Updating git submodules in $dir"
#                 git -C "$dir" submodule update --init --recursive
#                 if [ $? -ne 0 ]; then
#                     rv=1
#                 fi
#             fi
#         done
#     fi
#     rv=$?
#     return $rv
# }

function install_conan_packages {
    rv=0
    path=$1
    conan profile detect --force
    if [ -d "$path" ]; then
        # Find all directories containing conanfile.py or conanfile.txt
        find "$path" -type d | while read -r dir; do
            py_file="$dir/conanfile.py"
            txt_file="$dir/conanfile.txt"
            has_py=false
            has_txt=false
            if [ -f "$py_file" ]; then
                has_py=true
            fi
            if [ -f "$txt_file" ]; then
                has_txt=true
            fi
            if [ "$has_py" = true ]; then
                # Check if it's a package recipe (contains 'class' and 'ConanFile')
                echo "Building package from $py_file"
                conan create "$py_file" --build=missing
                if [ $? -ne 0 ]; then
                    echo "ERROR: Failed to create conan package from $py_file"
                    rv=1
                fi
            fi
            if [ "$has_txt" = true ]; then
                echo "Installing dependencies from $txt_file"
                conan install "$txt_file" --build missing --output-folder "$PATH_CONAN_OUTPUT_FOLDER"
                if [ $? -ne 0 ]; then
                    echo "ERROR: Failed to install conan dependencies from $txt_file"
                    rv=1
                fi
            fi
        done
    else
        echo "No directory found at $path"
        ls -l
        rv=1
    fi

    return $rv
}

error_counter=0
commands=(
    "install_apt_deps"
    "install_pip_deps"
    "clone_repos"
    # "update_git_submodules"
    "install_module_resources \"$PATH_PIP_SEARCH_FOLDER\""
    "install_conan_packages \"$PATH_CONAN_SEARCH_FOLDER\""
)
# Initialize an empty list to accept strings
error_commands=()

# Loop over each command and execute it
for cmd in "${commands[@]}"; do
    # Use eval to allow executing commands with arguments
    eval "$cmd"
    if [ $? -ne 0 ]; then
        error_counter=$(( error_counter + 1 ))
        error_commands+=("$cmd")
        echo "ERROR: $cmd"
    fi
done

if [ $error_counter -eq 0 ]; then
    echo -e "\033[0;32mAll commands executed successfully.\033[0m"
else
    echo -e "\033[0;31mERROR: $error_counter command(s) failed.\033[0m"
    echo -e "\033[0;31mFailed commands: ${error_commands[*]}\033[0m"
fi

exit $error_counter
