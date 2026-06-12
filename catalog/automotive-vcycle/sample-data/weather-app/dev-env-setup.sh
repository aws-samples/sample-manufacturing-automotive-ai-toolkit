#!/usr/bin/env bash
set -euo pipefail

# This script is intended for Mac OS Apple Silicon and Linux Intel/AMD environments
HOST_OS=""
HOST_ARCH=""

check_host_env() {
    if ! type uname >/dev/null 2>&1; then
        echo "[ERROR] - 'uname' command is not available, cannot check host environment ... Exiting!"
        exit 1
    else
        HOST_OS=`uname`
        echo "[INFO] - Detected OS is: $HOST_OS"
        HOST_ARCH=`uname -m`
        echo "[INFO] - Detected ARCH is: $HOST_ARCH"
        if ! ([[ "$HOST_OS" == "Darwin" && "$HOST_ARCH" == "arm64" ]] || [[ "$HOST_OS" == "Linux" && "$HOST_ARCH" == "x86_64" ]]); then
            echo "[INFO] - This script supports Mac OS Apple Silicon OR Linux Intel/AMD environments only ... Exiting!"
        fi
    fi
}

# Step 1. Install `brew`, if not already installed, and enable it for the terminal
install_brew() {
    if type brew >/dev/null 2>&1; then
        echo "[INFO] - 'brew' already installed ... skipping this step!"
        return
    else
        echo "[INFO] - Installing 'brew' ..."
        NONINTERACTIVE=1 \
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        echo "[INFO] - Installing 'brew' ... Done!"
        echo "[INFO] - Enabling 'brew' for bash ..."
        if [[ "$HOST_OS" == "Darwin" ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.profile
        else
            echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> ~/.profile
        fi
        echo "[INFO] - Enabling 'brew' for bash ... Done!"
    fi
}

# Step 2. Install `jdk 17`, if not already installed, and add it to `PATH`
install_jdk() {
    echo "[INFO] - Installing OpenJDK 17 ..."
    brew install openjdk@17
    echo "[INFO] - Installing OpenJDK 17 ... Done!"
    echo "[INFO] - Adding OpenJDK 17 to 'PATH' ..."
    brew link openjdk@17
    echo "[INFO] - Adding OpenJDK 17 to 'PATH' ... Done!"
}

# Step 3. Install the Android Command Line Tools, and define the `ANDROID_HOME` environment variable
install_sdk() {
    echo "[INFO] - Installing Android Command Line Tools ..."
    brew install --cask android-commandlinetools
    if ! grep ANDROID_HOME ~/.profile >/dev/null 2>&1; then
        echo 'export ANDROID_HOME="$(brew --prefix)/share/android-commandlinetools"' >> ~/.profile
    fi
    echo "[INFO] - Installing Android Command Line Tools ... Done!"
}

# Step 4. Accept all Android licenses so as not to be prompted in future instructions
accept_licenses() {
    echo "[INFO] - Accepting all Android licenses ..."
    yes y | sdkmanager --licenses
    echo "[INFO] - Accepting all Android licenses ... Done!"
}

# Step 5. Install the Android Platform Tools and Emulator, and add them to `PATH`
install_tools() {
    echo "[INFO] - Installing Android Platform Tools and Emulator ..."
    sdkmanager --install emulator platform-tools
    if ! grep '$ANDROID_HOME/emulator' ~/.profile >/dev/null 2>&1; then
        echo 'export PATH="$PATH:$ANDROID_HOME/emulator"' >> ~/.profile
    fi
    if ! grep '$ANDROID_HOME/platform-tools' ~/.profile >/dev/null 2>&1; then
        echo 'export PATH="$PATH:$ANDROID_HOME/platform-tools"' >> ~/.profile
    fi
    echo "[INFO] - Installing Android Platform Tools and Emulator ... Done!"
}

# Step 6. Download the Android Automotive System Image
download_aaos() {
    echo "[INFO] - Downloading Android Automotive System Image ..."
    if [[ "$HOST_ARCH" != "x86_64" ]]; then
        ANDROID_ARCH="arm64-v8a"
    else
        ANDROID_ARCH="$HOST_ARCH"
    fi
    sdkmanager --install "system-images;android-33;android-automotive;$ANDROID_ARCH"
    echo "[INFO] - Downloading Android Automotive System Image ... Done!"
}

# Step 7. Create an Android Virtual Device (avd) using the downloaded Android Automotive System Image and a pre-defined automotive device layout
# Name of the AVD to create
AVD_NAME="weather-app-env"
create_avd() {
    if avdmanager list avd 2>&1 | grep "$AVD_NAME" >/dev/null 2>&1; then
        echo "[INFO] - Android Virtual Device with name: $AVD_NAME already exists ... skipping this step!"
        return
    else
        echo "[INFO] - Creating Android Virtual Device with name: $AVD_NAME ..."
        if [[ "$HOST_ARCH" != "x86_64" ]]; then
            ANDROID_ARCH="arm64-v8a"
        else
            ANDROID_ARCH="$HOST_ARCH"
        fi
        avdmanager create avd \
            --name weather-app-env \
            --package "system-images;android-33;android-automotive;$ANDROID_ARCH" \
            --device "automotive_1080p_landscape"
        echo "[INFO] - Creating Android Virtual Device with name: $AVD_NAME ... Done!"
    fi
}

# Step 8. Whenever needed, start the emulated Android Virtual Device
print_usage() {
    echo "[INFO] - Run the created Android Virtual Device using 'emulator -avd $AVD_NAME'"
}

# Run all steps
check_host_env
install_brew
install_jdk
install_sdk
accept_licenses
install_tools
download_aaos
create_avd
print_usage
