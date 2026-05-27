# Android SDK Environment Setup
To be able to build and test the Weather Application, the [Android SDK Command Line Tools](https://developer.android.com/tools) are required.  
Setup instructions are described here.

## Host Environments
Although an Android application can be built on pretty much every host environment, the Android Emulator is not available for Linux ARM. Moreover, for a performant emulator, hardware acceleration and preferrably a GPU is required.  
Therefore, the recommended host environments are desktops and laptops running either Mac OS Apple Silicon, Linux Intel/AMD, or Windows, with preferrably a GPU.  
For cloud environments, either [Android Cuttlefish](https://source.android.com/docs/devices/cuttlefish), or an AWS EC2 instance type such as `g4dn.metal` should be considered, however are out of scope of these instruction steps. Note also that using cloud environments would required securely enabling access to the different ports required by the Android Debug Bridge (adb) and WebRTC (for UI access).

## Pre-requisites
The Android SDK Command Line Tools require a Java Development Kit (JDK), and the setup of some environment variables. Installation instructions for JDK 17 is listed in the following sections. Additionally, installation of [brew](https://brew.sh/) as a package manager is listed for Mac OS and Linux.

## Setup Steps
To ease in following the setup steps, a sub-section for each supported host environment has been created below.

### Mac

1. Install `brew` if not already installed:
```bash
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
and enable it for the terminal:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.profile
```

2. Install `jdk 17` if not already installed:
```bash
brew install openjdk@17
```
and add it to `PATH`:
```bash
brew link openjdk@17
```

3. Install the Android Command Line Tools:
```bash
brew install --cask android-commanlinetools
```
and define the `ANDROID_HOME` environment variable:
```bash
echo 'export ANDROID_HOME="$(brew --prefix)/share/android-commandlinetools"' >> ~/.profile
```
and double-check the path and adjust [local.properties](./android-auto/local.properties) file if needed


4. (_Optional_) Accept all Android licenses so as not to be prompted in future instructions:
```bash
yes y | sdkmanager --licenses
```

5. Install the Android Platform Tools and Emulator:
```bash
sdkmanager --install platform-tools emulator
```
and add them to `PATH`:
```bash
echo 'export PATH="$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools"' >> ~/.profile
```

6. Download the Android Automotive System Image:
```bash
sdkmanager --install "system-images;android-33;android-automotive;arm64-v8a"
```

7. Create an Android Virtual Device (avd) using the downloaded Android Automotive System Image and a pre-defined automotive device layout:
```bash
avdmanager create avd \
    --name weather-app-env \
    --package "system-images;android-33;android-automotive;arm64-v8a" \
    --device "automotive_1080p_landscape"
```

8. Whenever needed, start the emulated Android Virtual Device named `weather-app-env`:
```bash
emulator -avd weather-app-env
```
Note: `emulator` supported multiple arguments to control the behavior and interaction with the AVD, run `emulator --help` to view all options

### Linux (Intel/AMD)

1. Install `brew` if not already installed:
```bash
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
and enable it for the terminal:
```bash
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> ~/.profile
```

2. Install `jdk 17` if not already installed:
```bash
brew install openjdk@17
```
and add it to `PATH`:
```bash
brew link openjdk@17
```

3. Install the Android Command Line Tools:
```bash
brew install --cask android-commanlinetools
```
and define the `ANDROID_HOME` environment variable:
```bash
echo 'export ANDROID_HOME="$(brew --prefix)/share/android-commandlinetools"' >> ~/.profile
```
and double-check the path and adjust [local.properties](./android-auto/local.properties) file if needed

4. (_Optional_) Accept all Android licenses so as not to be prompted in future instructions:
```bash
yes y | sdkmanager --licenses
```

5. Install the Android Platform Tools and Emulator:
```bash
sdkmanager --install platform-tools emulator
```
and add them to `PATH`:
```bash
echo 'export PATH="$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools"' >> ~/.profile
```

6. Download the Android Automotive System Image:
```bash
sdkmanager --install "system-images;android-33;android-automotive;x86_64"
```

7. Create an Android Virtual Device (avd) using the downloaded Android Automotive System Image and a pre-defined automotive device layout:
```bash
avdmanager create avd \
    --name weather-app-env \
    --package "system-images;android-33;android-automotive;x86_64" \
    --device "automotive_1080p_landscape"
```

8. Whenever needed, start the emulated Android Virtual Device named `weather-app-env`:
```bash
emulator -avd weather-app-env
```
Note: `emulator` supported multiple arguments to control the behavior and interaction with the AVD, run `emulator --help` to view all options

### Windows

1. Follow the instruction steps listed [here](https://developer.android.com/tools/sdkmanager) to install the Android SDK Command Line Tools.  

2. Install OpenJDK 17 using the following [link](https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_windows-x64_bin.zip).

3. Edit the user environment variables to define the `ANDROID_HOME` and `JAVA_HOME` environment variables. Additionally update the `PATH` environment variable to include the path `$ANDROID_HOME\cmdline-tools\latest\bin`.

Double-check the path and adjust [local.properties](./android-auto/local.properties) file if needed

4. (_Optional_) Accept all Android licenses so as not to be prompted in future instructions:
```bash
yes y | sdkmanager --licenses
```

5. Install the Android Platform Tools and Emulator:
```bash
sdkmanager --install platform-tools emulator
```
and add them to `PATH` by editing the user environment variables, i.e., `$ANDROID_HOME\emulator` and `$ANDROID_HOME\platform-tools`.

6. Download the Android Automotive System Image:
```bash
sdkmanager --install "system-images;android-33;android-automotive;x86_64"
```

7. Create an Android Virtual Device (avd) using the downloaded Android Automotive System Image and a pre-defined automotive device layout:
```bash
avdmanager create avd \
    --name weather-app-env \
    --package "system-images;android-33;android-automotive;x86_64" \
    --device "automotive_1080p_landscape"
```

8. Whenever needed, start the emulated Android Virtual Device named `weather-app-env`:
```bash
emulator -avd weather-app-env
```
Note: `emulator` supported multiple arguments to control the behavior and interaction with the AVD, run `emulator --help` to view all options
