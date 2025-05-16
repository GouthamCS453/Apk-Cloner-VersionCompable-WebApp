# Cloner Webapp

## Objective
The Cloner Webapp is a Flask-based application designed to simplify the process of cloning Android APK files for testing and development purposes. It allows a user to upload an APK, modify its package name, rebuild the APK, and download the modified version. This is particularly useful for developers who need to test multiple instances of the same app with different package names on a single device.

## Purpose
The primary purpose of this project is to provide a user-friendly interface for APK cloning, automating the complex process of decompiling, modifying, rebuilding, and signing APK files. 
It aims to:
- Enable developers to test app behavior with different configurations via individual project files.
- Allow multiple app instances on the same device.

## Workflow
The Cloner Webapp follows a structured workflow to process APKs:

1. **User Input**:
   - Users access the web interface at `http://127.0.0.1:5000/upload`.
   - They provide a project name (or select an existing project), a custom name for the APK, and upload an APK file.

2. **APK Processing**:
   - The uploaded APK is saved temporarily in the `user_uploads/<project_name>` directory.
   - The `modify_apk` function in `scripts/modify_apk.py` is called to:
     - Decompile the APK using Apktool (skipping Smali decoding with `--no-src` for faster processing).
     - Modify the `AndroidManifest.xml` to change the package name to `com.cloned.<custom_name>`.
     - Copy original resources to avoid recompilation.
     - Rebuild the APK using Apktool (skipping resource recompilation with `--no-res`).
     - Sign the rebuilt APK using `jarsigner` with a debug keystore.
     - Clean up temporary files.

3. **Storage and Feedback**:
   - The modified APK is stored in the `user_uploads/<project_name>` directory.
   - The APK details are saved in a SQLite database (`app.db`) under the respective project.
   - Users are redirected to a project view page where they can download the modified APK or delete it.

4. **Project Management**:
   - Users can view all projects at `http://127.0.0.1:5000/projects`.
   - They can delete projects or individual APKs, which also removes the associated files from the `user_uploads` directory.

## Current Working Elements
As of the latest update, the following elements are functional:

- **Upload Interface**:
  - Users can upload APK files, specify a custom name, and choose or create a project.
  - Basic input validation ensures a custom name is provided and the file is an APK.

- **Database Integration**:
  - Projects and APKs are stored in a SQLite database (`app.db`) using Flask-SQLAlchemy.
  - Relationships between projects and APKs are maintained, allowing for easy management.

- **File Management**:
  - Uploaded APKs are saved in the `user_uploads` directory, organized by project name.
  - Temporary files are cleaned up after processing (though file locking issues may require manual intervention).

- **Web Interface**:
  - The app provides routes for uploading APKs (`/upload`), viewing projects (`/projects`), and managing individual projects (`/project/<project_name>`).
  - Users can download modified APKs or delete projects and APKs.

- **APK Processing (Partial)**:
  - The `modify_apk` function is implemented to decompile, modify, rebuild, and sign APKs.
  - Real-time logging is in place to monitor the process in the terminal.
  - The process works for smaller APKs (e.g., 10-50 MB) but struggles with larger, complex APKs like CapCut (200 MB), often failing due to resource constraints or timeouts.

## Known Issues
- **Large APK Processing**:
  - The app struggles with large APKs (e.g., 200 MB CapCut APK), often failing due to memory issues (`OutOfMemoryError`) or timeouts.
  - Recommendation: Test with smaller APKs or increase the Java heap size in `modify_apk.py` (e.g., `-Xmx6g`).

- **Error Feedback**:
  - When `modify_apk` fails, the error message on the webpage is sometimes generic ("Check the server logs for details"). More specific feedback is needed.

- **Performance**:
  - The synchronous processing of APKs causes the webpage to hang for large files. Asynchronous processing (e.g., using Celery) is recommended for better user experience.

- **File Issues**:
  - Modified Files show Package error while installing on Android Device.

- **Time Consumption**:
  - Web page take too much time for modifying and changing the package name.

- **UI/UX Modifications**:
  - Need to fix placeholder overwrite issue on pakage name input box. 

- **Database**:
  - Need to add a check to prevent the same APK from being uploaded multiple times.
  - Need to use an alternate more efficient database like MongoDB.

## Setup Instructions
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd Cloner_webapp
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On macOS/Linux
   ```

3. **Install Dependencies**:
   Ensure you have Java and `jarsigner` installed for APK signing.
   ```bash
   pip install -r requirements.txt
   ```

4. **Download Apktool**:
   - Download `apktool_2.11.1.jar` from [Apktool's official site](https://ibotpeaches.github.io/Apktool/) and place it in the project root.

5. **Run the App**:
   ```bash
   python app.py
   ```
   Access the app at `http://127.0.0.1:5000`.

## Future Improvements
- Implement asynchronous processing with Celery to handle large APKs without hanging the webpage.
- Improve error handling to provide more specific feedback to users.
- Add progress indicators for long-running APK processing tasks.
- Optimize memory usage for Apktool to handle larger APKs more efficiently.


This project is a starting point for a web-based APK cloner. It provides a basic structure and functionality but requires further development to meet the needs of afully developed application. This webpage is made for integration with a Mlti Apk Manger desined specificaaly for implementing this functionalty in an Android device.