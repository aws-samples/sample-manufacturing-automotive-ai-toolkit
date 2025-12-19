#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) runner module.
Handles running SFC configurations locally in test environments.
"""

import os
import json
import datetime
import requests
import subprocess
import logging
import threading
import queue
from logging.handlers import RotatingFileHandler
from typing import List, Optional, Tuple
from .sfc_module_analyzer import analyze_sfc_config_for_modules
from .log_operations import SFCLogOperations


class SFCRunner:
    """Handles running SFC configurations locally"""

    @staticmethod
    def run_sfc_config_locally(
        config_json: str,
        config_name: str = "",
        active_processes: Optional[List] = None,
        log_tail_thread: Optional[threading.Thread] = None,
        log_tail_stop_event: Optional[threading.Event] = None,
        log_buffer: Optional[queue.Queue] = None,
    ) -> Tuple[str, str, str, str, List, Optional[threading.Thread]]:
        """Run SFC configuration locally in a test environment

        Args:
            config_json: SFC configuration to run
            config_name: Optional name for the configuration and test folder
            active_processes: List to track active SFC processes
            log_tail_thread: Current log tail thread reference
            log_tail_stop_event: Event to signal log tail thread to stop
            log_buffer: Queue for log messages

        Returns:
            Tuple containing:
            - Result message (str)
            - Current config name (str)
            - Last config name (str)
            - Last config file path (str)
            - Updated active processes list (List)
            - Updated log tail thread (Optional[threading.Thread])
        """
        if active_processes is None:
            active_processes = []

        try:
            # First, terminate any existing SFC processes
            if active_processes:
                print("🛑 Stopping existing SFC processes before starting a new one...")
                for process in active_processes:
                    if process.poll() is None:  # Process is still running
                        try:
                            process.terminate()
                            process.wait(timeout=2)  # Wait for up to 2 seconds
                        except:
                            # If termination fails, force kill
                            try:
                                process.kill()
                            except:
                                pass
                # Clear the list of active processes
                active_processes.clear()
                print("✅ Existing SFC processes terminated")

            # Parse the JSON to ensure it's valid
            config = json.loads(config_json)

            # Generate a name for the config and test directory if not provided
            if not config_name:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                config_name = f"sfc_test_{timestamp}"

            # Create base directories
            base_dir = os.getcwd()

            # Create the modules directory at the same level as runs
            modules_dir = os.path.join(base_dir, ".sfc", "modules")
            if not os.path.exists(modules_dir):
                os.makedirs(modules_dir)

            # Create the runs directory
            runs_dir = os.path.join(base_dir, ".sfc", "runs")
            if not os.path.exists(runs_dir):
                os.makedirs(runs_dir)

            # Add a timestamp suffix to the test directory name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"{config_name}_{timestamp}"

            # Create a test directory with the config name and timestamp inside the runs folder
            test_dir = os.path.join(runs_dir, folder_name)
            if not os.path.exists(test_dir):
                os.makedirs(test_dir)

            # Save the configuration to a file in the test directory
            config_filename = os.path.join(test_dir, "config.json")
            with open(config_filename, "w") as file:
                json.dump(config, file, indent=2)

            # Fetch the latest SFC release information
            response = requests.get(
                "https://api.github.com/repos/awslabs/industrial-shopfloor-connect/releases/latest"
            )
            if response.status_code != 200:
                result = f"❌ Failed to fetch SFC release information: HTTP {response.status_code}"
                return (
                    result,
                    folder_name,
                    folder_name,
                    config_filename,
                    active_processes,
                    log_tail_thread,
                )

            release_data = response.json()
            sfc_version = release_data["tag_name"]

            # Analyze the configuration to determine which modules are needed
            needed_modules = analyze_sfc_config_for_modules(config)

            # Check if SFC main module exists in shared modules directory or download it
            sfc_main_module = "sfc-main"
            module_target_dir = os.path.join(modules_dir, sfc_main_module)

            if not os.path.exists(module_target_dir):
                sfc_main_url = f"https://github.com/awslabs/industrial-shopfloor-connect/releases/download/{sfc_version}/{sfc_main_module}.tar.gz"

                # Download the SFC main binary
                print(f"⬇️ Downloading SFC main {sfc_version}...")
                try:
                    tarball_response = requests.get(sfc_main_url, stream=True)
                    if tarball_response.status_code != 200:
                        result = f"❌ Failed to download SFC main binary: HTTP {tarball_response.status_code}"
                        return (
                            result,
                            folder_name,
                            folder_name,
                            config_filename,
                            active_processes,
                            log_tail_thread,
                        )

                    tarball_file_path = os.path.join(
                        modules_dir, f"{sfc_main_module}.tar.gz"
                    )
                    with open(tarball_file_path, "wb") as f:
                        for chunk in tarball_response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    # Extract the SFC main binary to modules directory
                    print(f"📦 Extracting SFC main binary...")
                    import tarfile

                    os.makedirs(module_target_dir, exist_ok=True)

                    # Extract with proper path handling to avoid duplicate directories
                    with tarfile.open(tarball_file_path, "r:gz") as tar:
                        # Check if all files are under a common root directory
                        root_dirs = set()
                        for member in tar.getmembers():
                            parts = member.name.split("/")
                            if parts:
                                root_dirs.add(parts[0])

                        # If everything is under one directory (likely named same as the module)
                        # extract contents directly without the extra directory level
                        if len(root_dirs) == 1:
                            common_prefix = list(root_dirs)[0] + "/"
                            for member in tar.getmembers():
                                if member.name.startswith(common_prefix):
                                    member.name = member.name[len(common_prefix) :]
                                    # Skip directories that would extract to root
                                    if member.name:
                                        tar.extract(member, path=module_target_dir)
                        else:
                            # No common prefix, extract normally
                            tar.extractall(path=module_target_dir)
                except Exception as e:
                    result = (
                        f"❌ Error downloading/extracting SFC main binary: {str(e)}"
                    )
                    return (
                        result,
                        folder_name,
                        folder_name,
                        config_filename,
                        active_processes,
                        log_tail_thread,
                    )
            else:
                print(f"✅ Using cached SFC main binary from {module_target_dir}")

            # We don't need to copy or link anymore, as we'll use the SFC_DEPLOYMENT_DIR

            # Download and extract needed modules
            successful_modules = []
            failed_modules = []

            for module in needed_modules:
                module_target_dir = os.path.join(modules_dir, module)

                # Check if module already exists in shared modules directory
                if not os.path.exists(module_target_dir):
                    module_url = f"https://github.com/awslabs/industrial-shopfloor-connect/releases/download/{sfc_version}/{module}.tar.gz"
                    print(f"⬇️ Downloading module: {module}...")

                    try:
                        module_response = requests.get(module_url, stream=True)
                        if module_response.status_code != 200:
                            print(
                                f"⚠️ Module {module} not found or cannot be downloaded"
                            )
                            failed_modules.append(module)
                            continue

                        # Save the module tar.gz file
                        module_file_path = os.path.join(modules_dir, f"{module}.tar.gz")
                        with open(module_file_path, "wb") as f:
                            for chunk in module_response.iter_content(chunk_size=8192):
                                f.write(chunk)

                        # Extract the module to shared modules directory
                        print(f"📦 Extracting module: {module}...")
                        import tarfile

                        os.makedirs(module_target_dir, exist_ok=True)

                        # Extract with proper path handling to avoid duplicate directories
                        with tarfile.open(module_file_path, "r:gz") as tar:
                            # Check if all files are under a common root directory
                            root_dirs = set()
                            for member in tar.getmembers():
                                parts = member.name.split("/")
                                if parts:
                                    root_dirs.add(parts[0])

                            # If everything is under one directory (likely named same as the module)
                            # extract contents directly without the extra directory level
                            if len(root_dirs) == 1:
                                common_prefix = list(root_dirs)[0] + "/"
                                for member in tar.getmembers():
                                    if member.name.startswith(common_prefix):
                                        member.name = member.name[len(common_prefix) :]
                                        # Skip directories that would extract to root
                                        if member.name:
                                            tar.extract(member, path=module_target_dir)
                            else:
                                # No common prefix, extract normally
                                tar.extractall(path=module_target_dir)

                        successful_modules.append(module)
                    except Exception as e:
                        print(f"⚠️ Error processing module {module}: {str(e)}")
                        failed_modules.append(module)
                        continue
                else:
                    print(f"✅ Using cached module: {module}")
                    successful_modules.append(module)

                # No need to copy or link as we'll use SFC_DEPLOYMENT_DIR

            # Find the SFC main executable in the modules directory
            sfc_executable = None
            sfc_main_lib_dir = os.path.join(modules_dir, "sfc-main", "lib", "*")

            # Determine the Java command to use - try multiple approaches
            java_cmd = "java"  # Default fallback to system Java

            # First try: Use JAVA_HOME if available
            java_home = os.environ.get("JAVA_HOME")
            if java_home:
                java_home_cmd = os.path.join(java_home, "bin", "java")
                if os.path.isfile(java_home_cmd) and os.access(java_home_cmd, os.X_OK):
                    java_cmd = java_home_cmd
                    print(f"✅ Using Java from JAVA_HOME: {java_cmd}")
                else:
                    print(
                        f"⚠️ Java not found at JAVA_HOME path: {java_home_cmd}, falling back to system Java"
                    )
            else:
                print("⚠️ JAVA_HOME not set, using system Java")

            # Second try: Check if common Java installations exist (MacOS specific paths)
            common_java_paths = [
                "/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home/bin/java",
                "/Library/Java/JavaVirtualMachines/temurin-11.jdk/Contents/Home/bin/java",
                "/Library/Java/JavaVirtualMachines/adoptopenjdk-11.jdk/Contents/Home/bin/java",
                "/Library/Java/JavaVirtualMachines/adoptopenjdk-8.jdk/Contents/Home/bin/java",
                "/usr/bin/java",
            ]

            if java_cmd == "java":  # If we're still using the default
                for path in common_java_paths:
                    if os.path.isfile(path) and os.access(path, os.X_OK):
                        java_cmd = path
                        print(f"✅ Found Java at common location: {java_cmd}")
                        break

            # Verify that Java is available before proceeding
            try:
                version_check = subprocess.run(
                    [java_cmd, "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                if version_check.returncode == 0:
                    print(f"✅ Java verified: {version_check.stderr.splitlines()[0]}")
                else:
                    print(
                        f"⚠️ Java version check returned non-zero exit code: {version_check.returncode}"
                    )
            except Exception as e:
                print(f"⚠️ Error checking Java version: {str(e)}")

            sfc_executable = (
                f'{java_cmd} -cp "{sfc_main_lib_dir}" com.amazonaws.sfc.MainController'
            )

            if not sfc_executable:
                result = (
                    f"❌ Could not find SFC main executable in the modules directory"
                )
                return (
                    result,
                    folder_name,
                    folder_name,
                    config_filename,
                    active_processes,
                    log_tail_thread,
                )

            # Run the configuration with SFC
            print(f"▶️ Running SFC with configuration " + config_filename)

            # We need to expand the wildcard in the classpath ourselves
            # Find all JAR files in the lib directory
            lib_dir = os.path.join(modules_dir, "sfc-main", "lib")
            jar_files = []
            if os.path.exists(lib_dir):
                for file in os.listdir(lib_dir):
                    if file.endswith(".jar"):
                        jar_files.append(os.path.join(lib_dir, file))

            # Build the classpath string with appropriate separator
            classpath = os.pathsep.join(jar_files)
            if not classpath:
                classpath = os.path.join(
                    modules_dir, "sfc-main", "lib"
                )  # Fallback to directory if no JARs found

            # print(f"Using classpath: {classpath}")

            # Get log level from environment variable (default to "info")
            sfc_log_level = os.getenv("SFC_LOG_LEVEL", "info").lower()

            # Validate log level and set the appropriate command line option
            if sfc_log_level == "trace":
                log_option = "-trace"
            else:  # Default to info for any other value
                log_option = "-info"

            # Construct the command properly as an array
            command = [
                java_cmd,  # Java executable
                "-cp",
                classpath,  # Classpath with properly expanded JAR files
                "com.amazonaws.sfc.MainController",  # Main class
                "-config",
                config_filename,  # SFC arguments
                log_option,
            ]

            # Set up environment variables for the SFC process
            env = os.environ.copy()
            env["SFC_DEPLOYMENT_DIR"] = os.path.abspath(modules_dir)
            env["MODULES_DIR"] = os.path.abspath(modules_dir)
            # print(os.path.abspath(modules_dir))

            # Set up log file with rotation
            log_dir = os.path.join(test_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file_path = os.path.join(log_dir, "sfc.log")

            # Create a rotating file handler
            log_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                mode="a",
            )

            # Create logger
            logger = logging.getLogger(f"sfc_{config_name}")
            logger.setLevel(logging.INFO)
            logger.addHandler(log_handler)

            # Create log file and open it for the process output
            log_file = open(log_file_path, "a")

            # Run in background with environment variables and redirect output to log file
            process = subprocess.Popen(
                command,
                cwd=test_dir,
                env=env,
                stdout=log_file,
                stderr=log_file,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )

            # Add to active processes for cleanup when wizard exits
            active_processes.append(process)

            # Create runner shell scripts for Linux and Windows that can execute the config directly
            # Get relative paths from test_dir to modules_dir for the scripts
            rel_modules_dir = os.path.relpath(os.path.abspath(modules_dir), test_dir)
            config_rel_path = (
                "config.json"  # Config is in the test directory, so just the filename
            )

            # Create Linux shell script
            linux_script_path = os.path.join(test_dir, "run_sfc.sh")
            with open(linux_script_path, "w") as sh_file:
                sh_file.write("#!/bin/bash\n")
                sh_file.write("# Auto-generated SFC runner script\n\n")
                # Set environment variables
                sh_file.write(f'export SFC_DEPLOYMENT_DIR="$(pwd)/{rel_modules_dir}"\n')
                sh_file.write(f'export MODULES_DIR="$(pwd)/{rel_modules_dir}"\n\n')
                # Find JAR files
                sh_file.write("# Build classpath dynamically\n")
                sh_file.write('CLASSPATH=""\n')
                sh_file.write(
                    f"for jar in $(pwd)/{rel_modules_dir}/sfc-main/lib/*.jar; do\n"
                )
                sh_file.write('  if [ -z "$CLASSPATH" ]; then\n')
                sh_file.write('    CLASSPATH="$jar"\n')
                sh_file.write("  else\n")
                sh_file.write('    CLASSPATH="$CLASSPATH:$jar"\n')
                sh_file.write("  fi\n")
                sh_file.write("done\n\n")
                # Execute Java command
                sh_file.write(
                    f'java -cp "$CLASSPATH" com.amazonaws.sfc.MainController -config {config_rel_path} {log_option}\n'
                )

            # Make the shell script executable
            os.chmod(linux_script_path, 0o755)

            # Create Windows batch script
            windows_script_path = os.path.join(test_dir, "run_sfc.bat")
            with open(windows_script_path, "w") as bat_file:
                bat_file.write("@echo off\n")
                bat_file.write("REM Auto-generated SFC runner script\n\n")
                # Enable delayed expansion at the beginning
                bat_file.write("setlocal EnableDelayedExpansion\n\n")
                # Set environment variables
                windows_modules_dir = rel_modules_dir.replace("/", "\\")
                bat_file.write(f"set SFC_DEPLOYMENT_DIR={windows_modules_dir}\n")
                bat_file.write(f"set MODULES_DIR={windows_modules_dir}\n\n")
                # Build classpath dynamically
                bat_file.write("REM Build classpath dynamically\n")
                bat_file.write("set CLASSPATH=\n")
                windows_lib_path = rel_modules_dir.replace("/", "\\")
                bat_file.write(
                    f'for %%F in ("{windows_lib_path}\\sfc-main\\lib\\*.jar") do (\n'
                )
                bat_file.write('  if "!CLASSPATH!"=="" (\n')
                bat_file.write("    set CLASSPATH=%%F\n")
                bat_file.write("  ) else (\n")
                bat_file.write("    set CLASSPATH=!CLASSPATH!;%%F\n")
                bat_file.write("  )\n")
                bat_file.write(")\n\n")
                # Execute Java command - exact same format as in the runner method
                bat_file.write("REM Execute SFC MainController\n")
                bat_file.write(f"java ^\n")
                bat_file.write('  -cp "!CLASSPATH!" ^\n')
                bat_file.write("  com.amazonaws.sfc.MainController ^\n")
                bat_file.write(f"  -config {config_rel_path} ^\n")
                bat_file.write(f"  {log_option}\n")
                bat_file.write("\nendlocal\n")

            # Start log tail thread if it's not already running
            if log_tail_stop_event is None:
                log_tail_stop_event = threading.Event()
            if log_buffer is None:
                log_buffer = queue.Queue(maxsize=100)

            log_tail_thread = SFCLogOperations.start_log_tail_thread(
                log_file_path, log_tail_thread, log_tail_stop_event, log_buffer
            )

            # Prepare the response message
            modules_status = ""
            if successful_modules:
                modules_status += (
                    f"\nSuccessfully installed modules: {', '.join(successful_modules)}"
                )
            if failed_modules:
                modules_status += f"\nModules that could not be installed: {', '.join(failed_modules)}"

            result = f"""✅ SFC configured and running!

Configuration: {config_name}
Directory: {test_dir}
SFC Version: {sfc_version}
Configuration File: {config_filename}{modules_status}

Runner scripts created:
- Linux: {os.path.join(test_dir, "run_sfc.sh")}
- Windows: {os.path.join(test_dir, "run_sfc.bat")}

SFC is running with your configuration in a new process.
You can check the logs in the test directory for status information.
You can also run the configuration again later by executing the runner scripts directly.
"""

            return (
                result,
                folder_name,  # Use the timestamped folder name instead of just config_name
                folder_name,  # Use the timestamped folder name instead of just config_name
                config_filename,
                active_processes,
                log_tail_thread,
            )

        except json.JSONDecodeError:
            result = "❌ Invalid JSON configuration provided"
            # Even in error cases, generate a timestamped folder name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            error_folder_name = f"{config_name or 'error'}_{timestamp}"
            return (
                result,
                error_folder_name,
                error_folder_name,
                "",
                active_processes,
                log_tail_thread,
            )
        except requests.RequestException as e:
            result = f"❌ Network error while fetching SFC: {str(e)}"
            # Even in error cases, generate a timestamped folder name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            error_folder_name = f"{config_name or 'error'}_{timestamp}"
            return (
                result,
                error_folder_name,
                error_folder_name,
                "",
                active_processes,
                log_tail_thread,
            )
        except Exception as e:
            result = f"❌ Error running SFC configuration: {str(e)}"
            # Even in error cases, generate a timestamped folder name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            error_folder_name = f"{config_name or 'error'}_{timestamp}"
            return (
                result,
                error_folder_name,
                error_folder_name,
                "",
                active_processes,
                log_tail_thread,
            )
