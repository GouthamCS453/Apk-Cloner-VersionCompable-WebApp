import os
import time
import shutil
import stat
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from scripts.modify_apk import modify_apk

app = Flask(__name__)
app.config.from_object('config.Config')

# Set maximum upload size to 1GB
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB limit

# Increase timeout for long-running processes (in seconds)
app.config['TIMEOUT'] = 600  # 10 minutes

# Initialize database
db = SQLAlchemy(app)

# Models
class Project(db.Model):
    __mapper_args__ = {'confirm_deleted_rows': False}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    apks = db.relationship('APK', backref='project', lazy=True, cascade='all, delete-orphan')

class APK(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    custom_name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

def to_long_path(path):
    """Convert a path to long path format for Windows."""
    path = os.path.abspath(path)
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        return '\\\\?\\' + path
    return path

# Routes
@app.route('/')
def index():
    project_count = Project.query.count()
    return render_template('index.html', project_count=project_count)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        project_name = request.form.get('project_name')
        custom_name = request.form.get('custom_name')
        file = request.files['file']

        # Validate inputs
        if not custom_name or not file or file.filename == '':
            flash('Custom name and APK file are required.', 'error')
            return redirect(url_for('upload'))

        if not file.filename.endswith('.apk'):
            flash('Only APK files are allowed.', 'error')
            return redirect(url_for('upload'))

        # Determine project
        project = None
        try:
            if project_id:  # Existing project selected
                project = db.session.get(Project, project_id)
                if not project:
                    flash('Selected project not found.', 'error')
                    return redirect(url_for('upload'))
            else:  # New project
                if not project_name:
                    flash('New project name is required when creating a new project.', 'error')
                    return redirect(url_for('upload'))
                project = Project.query.filter_by(name=project_name).first()
                if project:
                    flash(f'Project "{project_name}" already exists. Please select it from the dropdown or choose a different name.', 'error')
                    return redirect(url_for('upload'))
                project = Project(name=project_name)
                db.session.add(project)
                db.session.commit()

            # Save and process APK
            project_dir = os.path.join('user_uploads', project.name)
            project_dir = to_long_path(project_dir)
            os.makedirs(project_dir, exist_ok=True)

            temp_apk_path = os.path.join(project_dir, f"temp_{int(time.time())}_{file.filename}")
            temp_apk_path = to_long_path(temp_apk_path)
            file.save(temp_apk_path)

            # Verify the file was saved
            if not os.path.exists(temp_apk_path):
                flash('Error: Failed to save the APK file to the server.', 'error')
                return redirect(url_for('upload'))

            try:
                print(f"Processing APK: {temp_apk_path}")
                modified_filename = modify_apk(temp_apk_path, f"com.cloned.{custom_name}", project_dir)
                if not modified_filename:
                    # Check for specific errors
                    error_log = open('error.log', 'r').read() if os.path.exists('error.log') else ''
                    if "OutOfMemoryError" in error_log:
                        flash('Error modifying APK: Java ran out of memory. Try a smaller APK or increase the Java heap size.', 'error')
                    elif "Failed to parse AndroidManifest.xml" in error_log:
                        flash('Error modifying APK: Invalid AndroidManifest.xml. The APK might be corrupted or not supported.', 'error')
                    elif "not well-formed (invalid token)" in error_log:
                        flash('Error modifying APK: Invalid resources detected. The APK might be obfuscated or protected.', 'error')
                    elif "Process timed out" in error_log:
                        flash('Error modifying APK: The process timed out. The APK might be too large or complex.', 'error')
                    else:
                        flash('Error modifying APK: Unknown error occurred. Check the server logs for details.', 'error')
                    return redirect(url_for('upload'))

                # Save to database
                apk = APK(filename=modified_filename, custom_name=custom_name, project_id=project.id)
                db.session.add(apk)
                db.session.commit()

                flash(f'APK uploaded and modified to {modified_filename}', 'success')
                return redirect(url_for('project_view', project_name=project.name))

            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_apk_path):
                        os.remove(temp_apk_path)
                except Exception as e:
                    flash(f'Warning: Could not clean up temporary file: {e}', 'error')

        except Exception as e:
            # Rollback database changes if an error occurs
            if project and project in db.session:
                db.session.rollback()
            flash(f'Error during upload: {e}', 'error')
            return redirect(url_for('upload'))

    projects = Project.query.all()
    project_count = Project.query.count()
    return render_template('upload.html', projects=projects, project_count=project_count)

@app.route('/projects')
def projects():
    projects = Project.query.all()
    project_count = Project.query.count()
    return render_template('projects.html', projects=projects, project_count=project_count)

@app.route('/project/<project_name>')
def project_view(project_name):
    project = Project.query.filter_by(name=project_name).first_or_404()
    project_count = Project.query.count()
    return render_template('project_view.html', project=project, project_count=project_count)

@app.route('/project/<project_name>/delete', methods=['POST'])
def delete_project(project_name):
    project = Project.query.filter_by(name=project_name).first_or_404()
    project_dir = os.path.join('user_uploads', project.name)
    project_dir = to_long_path(project_dir)
    if os.path.exists(project_dir):
        retries = 3
        delay = 1
        for attempt in range(retries):
            try:
                # Ensure all files are writable
                for root, dirs, files in os.walk(project_dir, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, stat.S_IWRITE)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, stat.S_IWRITE)
                shutil.rmtree(project_dir)
                break
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    flash(f'Warning: Could not fully delete project directory: {e}. Try restarting the app or deleting the directory manually.', 'error')

    # Refresh the project object to ensure it's in sync with the database
    db.session.refresh(project)
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{project_name}" deleted successfully.', 'success')
    return redirect(url_for('projects'))

@app.route('/apk/<int:apk_id>/delete', methods=['POST'])
def delete_apk(apk_id):
    apk = APK.query.get_or_404(apk_id)
    project = apk.project
    apk_path = os.path.join('user_uploads', project.name, apk.filename)
    apk_path = to_long_path(apk_path)
    if os.path.exists(apk_path):
        try:
            os.remove(apk_path)
        except Exception as e:
            flash(f'Warning: Could not delete APK file: {e}', 'error')
    db.session.delete(apk)
    db.session.commit()
    flash(f'APK "{apk.filename}" deleted successfully.', 'success')
    return redirect(url_for('project_view', project_name=project.name))

@app.route('/user_uploads/<project>/<filename>')
def uploaded_file(project, filename):
    directory = os.path.join('user_uploads', project)
    directory = to_long_path(directory)
    return send_from_directory(directory, filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)