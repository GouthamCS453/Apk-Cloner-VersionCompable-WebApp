import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
import time
import stat
import sys

def modify_apk(apk_path, new_package_name, output_dir):
    print(f"Starting modify_apk for APK: {apk_path}")
    
    def to_long_path(path):
        """Convert a path to long path format for Windows."""
        path = os.path.abspath(path)
        if os.name == 'nt' and not path.startswith('\\\\?\\'):
            return '\\\\?\\' + path
        return path
    # Verify APK file exists
    if not os.path.exists(apk_path):
        print(f"Error: APK file does not exist at {apk_path}", file=sys.stderr)
        return None

    # Define paths with a shorter decompiled directory name
    apktool_jar = "apktool_2.11.1.jar"
    decompiled_base = os.path.join(output_dir, "d")  # Shortened from "decompiled" to "d"
    decompiled_dir = to_long_path(decompiled_base)
    rebuilt_apk = os.path.join(output_dir, "rebuilt.apk")
    signed_apk = os.path.join(output_dir, f"signed_{os.path.basename(apk_path)}")

    

    def force_delete_directory(directory, retries=3, delay=1):
        """Attempt to delete a directory with retries in case of file locking, supporting long paths."""
        long_dir = to_long_path(directory)
        for attempt in range(retries):
            try:
                # Ensure all files are writable
                for root, dirs, files in os.walk(long_dir, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, stat.S_IWRITE)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, stat.S_IWRITE)
                shutil.rmtree(long_dir)
                return True
            except Exception as e:
                if attempt < retries - 1:
                    print(f"Failed to delete {directory} (attempt {attempt + 1}/{retries}): {e}. Retrying...")
                    time.sleep(delay)
                else:
                    print(f"Failed to delete {directory} after {retries} attempts: {e}")
                    return False

    def run_subprocess_with_logging(cmd, timeout=600):
        """Run a subprocess command and log output in real-time with a timeout."""
        print(f"Running command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True
        )
        stdout_lines, stderr_lines = [], []
        try:
            while True:
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()
                if stdout_line:
                    print(f"STDOUT: {stdout_line.strip()}")
                    stdout_lines.append(stdout_line)
                if stderr_line:
                    print(f"STDERR: {stderr_line.strip()}", file=sys.stderr)
                    stderr_lines.append(stderr_line)
                if process.poll() is not None:
                    break
            process.stdout.close()
            process.stderr.close()
            process.wait(timeout=timeout)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, output=''.join(stdout_lines), stderr=''.join(stderr_lines))
        except subprocess.TimeoutExpired as e:
            process.kill()
            process.stdout.close()
            process.stderr.close()
            raise Exception(f"Process timed out after {timeout} seconds: {e}")
        except Exception as e:
            process.kill()
            process.stdout.close()
            process.stderr.close()
            raise Exception(f"Subprocess failed: {e}")

    try:
        # Convert paths to long path format
        apk_path = to_long_path(apk_path)
        rebuilt_apk = to_long_path(rebuilt_apk)
        signed_apk = to_long_path(signed_apk)

        # Step 1: Decompile the APK using apktool, skipping Smali decoding
        print("Starting APK decompilation...")
        run_subprocess_with_logging(
            ["java", "-Xmx4g", "-Dapktool.threads=4", "-jar", apktool_jar, "d", apk_path, "-o", decompiled_dir, "-f", "--no-src"],
            timeout=600  # 10-minute timeout
        )

        # Step 2: Modify the package name in AndroidManifest.xml
        print("Modifying AndroidManifest.xml...")
        manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError("AndroidManifest.xml not found after decompiling")

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            root.set("package", new_package_name)
            tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse AndroidManifest.xml: {e}")

        # Step 2.5: Copy original resources to avoid recompilation
        print("Copying original resources...")
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            # Extract resources.arsc
            if "resources.arsc" in apk_zip.namelist():
                apk_zip.extract("resources.arsc", decompiled_dir)
            # Extract the res directory
            for item in apk_zip.namelist():
                if item.startswith("res/"):
                    apk_zip.extract(item, decompiled_dir)

        # Step 3: Rebuild the APK using apktool, skipping resource recompilation
        print("Rebuilding APK...")
        run_subprocess_with_logging(
            ["java", "-Xmx4g", "-Dapktool.threads=4", "-jar", apktool_jar, "b", decompiled_dir, "-o", rebuilt_apk, "--no-res"],
            timeout=600
        )

        # Step 4: Sign the APK
        print("Signing APK...")
        debug_keystore = "debug.keystore"
        run_subprocess_with_logging(
            [
                "jarsigner", "-verbose", "-keystore", debug_keystore,
                "-storepass", "android", "-keypass", "android",
                rebuilt_apk, "androiddebugkey"
            ],
            timeout=300  # 5-minute timeout for signing
        )

        # Step 5: Clean up
        print("Cleaning up...")
        if os.path.exists(decompiled_dir):
            force_delete_directory(decompiled_dir)
        if os.path.exists(rebuilt_apk):
            os.remove(rebuilt_apk)

        print("APK modification completed successfully.")
        return os.path.basename(signed_apk)

    except subprocess.CalledProcessError as e:
        error_message = f"Error modifying APK: {e}\nSTDERR: {e.stderr}"
        print(error_message, file=sys.stderr)
        # Clean up in case of failure
        if os.path.exists(decompiled_dir):
            force_delete_directory(decompiled_dir)
        if os.path.exists(rebuilt_apk):
            os.remove(rebuilt_apk)
        return None
    except Exception as e:
        print(f"Error modifying APK: {e}", file=sys.stderr)
        # Clean up in case of failure
        if os.path.exists(decompiled_dir):
            force_delete_directory(decompiled_dir)
        if os.path.exists(rebuilt_apk):
            os.remove(rebuilt_apk)
        return None