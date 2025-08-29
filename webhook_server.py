from flask import Flask, request, jsonify, abort
import os
import subprocess
import tempfile
import shutil
import docker

# === CONFIGURATION ===
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")
WEBHOOK_FOLDER = os.environ.get("WEBHOOK_FOLDER", "/app/shared/html")
REPO_URL = os.environ.get("NGINX_REPO_URL", "https://github.com/username/your-repo.git")
REPO_BRANCH = os.environ.get("NGINX_REPO_BRANCH", "master")
NGINX_CONTAINER = os.environ.get("NGINX_CONTAINER", "nginx-1")
NGINX_FOLDER = os.environ.get("NGINX_FOLDER", "/app/shared/html")

app = Flask(__name__)

def update_repo():
    # Create temporary directory for the fresh clone
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Cloning {REPO_BRANCH} into temp dir: {tmpdir}")
        subprocess.run(
            ["git", "clone", "--branch", REPO_BRANCH, "--depth", "1", REPO_URL, tmpdir],
            check=True
        )

        # Update submodules inside the temp clone
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=tmpdir,
            check=True
        )
        print("Submodules updated in temporary clone")

        # Remove the old target directory
        if os.path.exists(WEBHOOK_FOLDER):
            print(f"Removing old target directory: {WEBHOOK_FOLDER}")
            shutil.rmtree(WEBHOOK_FOLDER)

        # Move the new clone into place
        print(f"Moving new clone to target: {WEBHOOK_FOLDER}")
        shutil.move(tmpdir, WEBHOOK_FOLDER)
    
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    container = client.containers.get(NGINX_CONTAINER)
    print(f"Moving {NGINX_FOLDER}/nginx.conf to /etc/nginx/nginx.conf")
    copy_result =  container.exec_run(f"mv {NGINX_FOLDER}/nginx.conf /etc/nginx/nginx.conf")
    print("move output:", copy_result.output.decode('utf-8'))
    print(f"Reloading nginx")
    reload_result = container.exec_run("nginx -s reload")
    print("reload output:", reload_result.output.decode('utf-8'))
    

@app.route("/webhook", methods=["POST"])
def webhook():
    # Check token
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {WEBHOOK_TOKEN}":
        abort(403, "Forbidden: invalid token")

    try:
        # Optional: validate GitHub secret here if you set one
        update_repo()
        return jsonify({"status": "ok", "message": "Repository updated"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Run once at startup
    try:
        update_repo()
    except Exception as e:
        print(f"Initial update failed: {e}")

    port = int(os.environ.get("PORT", 5000))
    # Host 0.0.0.0 so it’s reachable from outside container
    app.run(host="0.0.0.0", port=port, debug=False)
