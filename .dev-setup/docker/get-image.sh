#!/bin/bash


# Key Features
# - Attempts pull before prompting for login.
# - Prompts to log in only if the pull fails and you're not logged in.
# - Tries pulling again after login.
# - Returns 0 if image was successfully pulled, 1 if pull failed but build possible, 2 if login failed/declined
function try_pull_image() {
    LOCAL_IMAGE=$1
    REMOTE_IMAGE=$2
    REGISTRY_URL=$(echo "$REMOTE_IMAGE" | cut -d'/' -f1)

    # Try to pull the remote image first
    if docker pull ${REMOTE_IMAGE}; then
        docker tag ${REMOTE_IMAGE} ${LOCAL_IMAGE}
        echo "Successfully pulled remote image ${REMOTE_IMAGE}."
        return 0
    else
        echo "Could not pull remote image ${REMOTE_IMAGE}."
    fi

    # Check if logged in: scan config.json for an entry for your registry
    function is_logged_in() {
        grep "\"$REGISTRY_URL\"" ~/.docker/config.json &>/dev/null
    }

    # Prompt for login if not logged in
    if ! is_logged_in; then
        read -p "You are not logged in to $REGISTRY_URL. Log in now? (y/n): " answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            docker login $REGISTRY_URL || { echo "Docker login failed"; return 2; }
        else
            echo "Cannot continue without login."
            return 2
        fi
    fi

    # Try pulling again after login
    if docker pull ${REMOTE_IMAGE}; then
        docker tag ${REMOTE_IMAGE} ${LOCAL_IMAGE}
        echo "Successfully pulled remote image ${REMOTE_IMAGE} after login."
        return 0
    else
        echo "Remote image ${REMOTE_IMAGE} still not available after login."
        return 1  # Indicates pull failed but build is possible
    fi
}

# --- Pull / Build and tag images ---

# robot_mindset_linux:run-1.0
docker build --file .dev-setup/docker/Dockerfile.run \
    --secret id=gitcreds,src=$HOME/.git-credentials \
    --tag robot_mindset_linux:run-1.0 \
    .

# robot_mindset_linux:base-1.0
if try_pull_image robot_mindset_linux:base-1.0 container-registry.gitlab.cc-asp.fraunhofer.de/multirobot/robot_mindset_linux:base-1.0; then
    echo "Image robot_mindset_linux:base-1.0 ready."
elif [ $? -eq 1 ]; then
    read -p "Do you want to build robot_mindset_linux:base-1.0 locally? (y/n): " build_answer
    if [[ "$build_answer" =~ ^[Yy]$ ]]; then
        echo "Building robot_mindset_linux:base-1.0 locally..."
        docker build --file .dev-setup/docker/Dockerfile.base \
            --secret id=gitcreds,src=$HOME/.git-credentials \
            --tag robot_mindset_linux:base-1.0 \
            . || { echo "Docker build failed"; exit 1; }
        docker tag robot_mindset_linux:base-1.0 container-registry.gitlab.cc-asp.fraunhofer.de/multirobot/robot_mindset_linux:base-1.0
        echo "Successfully built and tagged robot_mindset_linux:base-1.0."
    else
        echo "Skipping robot_mindset_linux:base-1.0 - user declined to build locally."
    fi
else
    echo "Skipping robot_mindset_linux:base-1.0 due to login failure or user declined login."
fi

# robot_mindset_linux:ci-1.0
if try_pull_image robot_mindset_linux:ci-1.0 container-registry.gitlab.cc-asp.fraunhofer.de/multirobot/robot_mindset_linux:ci-1.0; then
    echo "Image robot_mindset_linux:ci-1.0 ready."
elif [ $? -eq 1 ]; then
    read -p "Do you want to build robot_mindset_linux:ci-1.0 locally? (y/n): " build_answer
    if [[ "$build_answer" =~ ^[Yy]$ ]]; then
        echo "Building robot_mindset_linux:ci-1.0 locally..."
        docker build --file .dev-setup/docker/Dockerfile.ci \
            --secret id=gitcreds,src=$HOME/.git-credentials \
            --tag robot_mindset_linux:ci-1.0 \
            . || { echo "Docker build failed"; exit 1; }
        docker tag robot_mindset_linux:ci-1.0 container-registry.gitlab.cc-asp.fraunhofer.de/multirobot/robot_mindset_linux:ci-1.0
        echo "Successfully built and tagged robot_mindset_linux:ci-1.0."
    else
        echo "Skipping robot_mindset_linux:ci-1.0 - user declined to build locally."
    fi
else
    echo "Skipping robot_mindset_linux:ci-1.0 due to login failure or user declined login."
fi