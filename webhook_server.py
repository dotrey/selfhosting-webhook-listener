from flask import Flask, request, jsonify
import os
import git
import subprocess

# === CONFIGURATION ===
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")
REPO_URL = os.environ.get("REPO_URL", "https://github.com/username/your-repo.git")
REPO_BRANCH = os.environ.get("REPO_BRANCH", "master")
NGINX_CONTAINER = os.environ.get("NGINX_CONTAINER", "nginx-1")
LOCAL_PATH = os.environ.get("LOCAL_PATH", "/app/repo")  # where to clone/pull

app = Flask(__name__)

def update_repo():
    if not os.path.exists(LOCAL_PATH):
        # Clone fresh
        repo = git.Repo.clone_from(REPO_URL, LOCAL_PATH, branch=REPO_BRANCH)
        print(f"Cloned {REPO_URL} into {LOCAL_PATH}")
    else:
        # Pull latest
        repo = git.Repo(LOCAL_PATH)
        origin = repo.remotes.origin
        origin.fetch()
        repo.git.checkout(REPO_BRANCH)
        origin.pull()
        print(f"Updated branch {REPO_BRANCH}")

    # Update submodules
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=LOCAL_PATH)
    print("Submodules updated")
    
    # Reload Nginx
    subprocess.run([
        "docker", "exec", NGINX_CONTAINER, "nginx", "-s", "reload"
    ])

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Check token
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {WEBHOOK_TOKEN}":
            abort(403, "Forbidden: invalid token")

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
