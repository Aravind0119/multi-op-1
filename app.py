
import os
import json
import pandas as pd
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from docx import Document
from PyPDF2 import PdfReader

app = Flask(__name__)

# =============================
# CONFIG
# =============================

BASE_INTERNAL = "internal_files"
os.makedirs(BASE_INTERNAL, exist_ok=True)

API_KEY = os.environ.get("API_KEY", "Aravind-sai-0119")

temporary_data = {}

# =============================
# API KEY VALIDATION
# =============================

def require_api_key():
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        return False
    return True

# =============================
# FILE CONVERTER
# =============================

def convert_file(file, filename):
    name = filename.lower()

    try:
        if name.endswith(".csv"):
            df = pd.read_csv(file)
            return df.to_dict(orient="records")

        elif name.endswith(".json"):
            return json.load(file)

        elif name.endswith(".xlsx"):
            sheets = pd.read_excel(file, sheet_name=None)
            return {s: df.to_dict(orient="records") for s, df in sheets.items()}

        elif name.endswith(".txt"):
            return {"text_content": file.read().decode("utf-8", errors="ignore")}

        elif name.endswith(".pdf"):
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return {"pdf_text": text}

        elif name.endswith(".docx"):
            doc = Document(file)
            return {"docx_text": "\n".join([p.text for p in doc.paragraphs])}

        else:
            return {"error": "Unsupported file type"}

    except Exception as e:
        return {"error": str(e)}

# =============================
# UI
# =============================

@app.route("/")
def home():
    folders = os.listdir(BASE_INTERNAL)

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Enterprise File Manager</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background:#f4f6f9; }
.section { background:white; padding:20px; border-radius:10px; margin-bottom:20px; }
</style>
</head>
<body>

<div class="container mt-5">
<h2 class="text-center mb-4">📂 Enterprise File Manager</h2>

<div class="section">
<h5>Temporary Upload (Replace Mode)</h5>
<form action="/upload_temp" method="POST" enctype="multipart/form-data">
<input type="file" name="files" multiple class="form-control mb-2" required>
<button class="btn btn-primary">Upload Temporary</button>
</form>
</div>

<div class="section">
<h5>Upload to Root Internal Folder</h5>
<form action="/upload_internal" method="POST" enctype="multipart/form-data">
<input type="file" name="files" multiple class="form-control mb-2" required>
<button class="btn btn-success">Upload Internal</button>
</form>
</div>

<div class="section">
<h5>Create / Upload to Custom Folder</h5>
<form action="/upload_custom_internal" method="POST" enctype="multipart/form-data">
<input type="text" name="folder_name" placeholder="Folder Name" class="form-control mb-2" required>
<input type="file" name="files" multiple class="form-control mb-2" required>
<button class="btn btn-dark">Upload to Folder</button>
</form>
</div>

<hr>
<h5>Internal Folders</h5>
<ul class="list-group">
{% for folder in folders %}
<li class="list-group-item d-flex justify-content-between">
{{folder}}
<div>
<a href="/api/internal/{{folder}}" class="btn btn-sm btn-outline-primary">View</a>
<a href="/api/internal/delete-folder/{{folder}}" class="btn btn-sm btn-outline-danger">Delete</a>
</div>
</li>
{% endfor %}
</ul>

<hr>
<a href="/view_temp" class="btn btn-dark mt-3">View Temporary JSON</a>

</div>
</body>
</html>
""", folders=folders)

# =============================
# TEMPORARY UPLOAD
# =============================

@app.route("/upload_temp", methods=["POST"])
def upload_temp():
    global temporary_data
    temporary_data = {}

    files = request.files.getlist("files")
    for file in files:
        temporary_data[file.filename] = convert_file(file, file.filename)

    return redirect(url_for("home"))

# =============================
# INTERNAL ROOT UPLOAD
# =============================

@app.route("/upload_internal", methods=["POST"])
def upload_internal():
    files = request.files.getlist("files")

    for file in files:
        path = os.path.join(BASE_INTERNAL, file.filename + ".json")

        if os.path.exists(path):
            continue

        data = convert_file(file, file.filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    return redirect(url_for("home"))

# =============================
# CUSTOM FOLDER UPLOAD
# =============================

@app.route("/upload_custom_internal", methods=["POST"])
def upload_custom_internal():
    folder_name = request.form.get("folder_name")
    folder_path = os.path.join(BASE_INTERNAL, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    files = request.files.getlist("files")

    for file in files:
        safe_name = os.path.basename(file.filename)
        path = os.path.join(folder_path, safe_name + ".json")

        if os.path.exists(path):
            continue

        data = convert_file(file, safe_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    return redirect(url_for("home"))

# =============================
# API: LIST ALL INTERNAL
# =============================

@app.route("/api/internal")
def list_internal():
    if not require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    result = {}
    for folder in os.listdir(BASE_INTERNAL):
        folder_path = os.path.join(BASE_INTERNAL, folder)
        if os.path.isdir(folder_path):
            result[folder] = os.listdir(folder_path)

    return jsonify(result)

# =============================
# API: VIEW FOLDER DATA
# =============================

@app.route("/api/internal/<folder>")
def view_folder(folder):
    if not require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    folder_path = os.path.join(BASE_INTERNAL, folder)

    if not os.path.exists(folder_path):
        return jsonify({"error": "Folder not found"})

    data = {}

    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            with open(os.path.join(folder_path, file), "r", encoding="utf-8") as f:
                data[file] = json.load(f)

    return jsonify({
        "folder": folder,
        "total_files": len(data),
        "data": data
    })

# =============================
# API: DELETE FILE
# =============================

@app.route("/api/internal/delete-file/<folder>/<file>")
def delete_file(folder, file):
    if not require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    path = os.path.join(BASE_INTERNAL, folder, file)

    if os.path.exists(path):
        os.remove(path)
        return jsonify({"status": "File deleted"})
    else:
        return jsonify({"error": "File not found"})

# =============================
# API: DELETE FOLDER
# =============================

@app.route("/api/internal/delete-folder/<folder>")
def delete_folder(folder):
    if not require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    folder_path = os.path.join(BASE_INTERNAL, folder)

    if not os.path.exists(folder_path):
        return jsonify({"error": "Folder not found"})

    for f in os.listdir(folder_path):
        os.remove(os.path.join(folder_path, f))
    os.rmdir(folder_path)

    return jsonify({"status": "Folder deleted"})

# =============================
# API: DELETE ALL
# =============================

@app.route("/api/internal/delete-all")
def delete_all():
    if not require_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    for folder in os.listdir(BASE_INTERNAL):
        folder_path = os.path.join(BASE_INTERNAL, folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                os.remove(os.path.join(folder_path, f))
            os.rmdir(folder_path)

    return jsonify({"status": "All internal data deleted"})

# =============================
# VIEW TEMP
# =============================

@app.route("/view_temp")
def view_temp():
    if not temporary_data:
        return jsonify({"message": "No temporary files uploaded"})
    return jsonify(temporary_data)

# =============================
# RUN
# =============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


