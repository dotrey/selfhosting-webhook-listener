from flask import Flask, request, jsonify, abort
import os
import git
import subprocess

# === CONFIGURATION ===
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")
REPO_URL = os.environ.get("NGINX_REPO_URL", "https://github.com/username/your-repo.git")
REPO_BRANCH = os.environ.get("NGINX_REPO_BRANCH", "master")
NGINX_CONTAINER = os.environ.get("NGINX_CONTAINER", "nginx-1")
TARGET_PATH = os.environ.get("NGINX_REPO_TARGET", "/app/html_root")  # where to clone/pull

app = Flask(__name__)

def update_repo():
    if not os.path.exists(TARGET_PATH):
        # Clone fresh
        repo = git.Repo.clone_from(REPO_URL, TARGET_PATH, branch=REPO_BRANCH)
        print(f"Cloned {REPO_URL} into {TARGET_PATH}")
    else:
        # Pull latest
        repo = git.Repo(TARGET_PATH)
        origin = repo.remotes.origin
        origin.fetch()
        repo.git.checkout(REPO_BRANCH)
        origin.pull()
        print(f"Updated branch {REPO_BRANCH}")

    # Update submodules
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=TARGET_PATH)
    print("Submodules updated")
    
    # Reload Nginx
    subprocess.run([
        "docker", "exec", NGINX_CONTAINER, "nginx", "-s", "reload"
    ])

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
    port = int(os.environ.get("PORT", 5000))
    # Host 0.0.0.0 so it’s reachable from outside container
    app.run(host="0.0.0.0", port=port)
