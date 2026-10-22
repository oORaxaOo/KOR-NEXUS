"""Secure, local GitHub API bridge for KOR-NEXUS.

Credentials are read from the process environment or GitHub CLI's OS-managed
authentication. They are never returned to the browser or written to SQLite.
"""
from __future__ import annotations
import json, os, subprocess, urllib.error, urllib.parse, urllib.request

API = "https://api.github.com"
MAX_RESPONSE = 3_000_000
TIMEOUT = 12

class GitHubError(RuntimeError):
    pass

def _token():
    token = os.environ.get("KOR_NEXUS_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    try:
        proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=3, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise GitHubError("GitHub ist nicht verbunden. Bitte auf diesem Rechner 'gh auth login' ausführen oder KOR_NEXUS_GITHUB_TOKEN setzen.")

def request(method="GET", path="/user/repos?per_page=100&sort=updated", payload=None):
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise GitHubError("Ungültiger GitHub-API-Pfad.")
    url = API + path
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + _token(),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "KOR-NEXUS-Local-Development-Center",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise GitHubError("GitHub-Antwort ist zu groß.")
            if not raw:
                return {"ok": True}
            try: return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise GitHubError("GitHub lieferte eine ungültige Antwort.")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            raw = exc.read(4096)
            detail = json.loads(raw.decode("utf-8")).get("message", "")
        except Exception: pass
        if exc.code == 401: raise GitHubError("GitHub-Anmeldung abgelaufen oder Token ungültig.")
        if exc.code == 403: raise GitHubError("GitHub hat die Aktion verweigert (Berechtigungen oder API-Limit prüfen).")
        if exc.code == 404: raise GitHubError("GitHub-Ressource nicht gefunden oder nicht autorisiert.")
        raise GitHubError("GitHub API Fehler " + str(exc.code) + (": " + detail[:240] if detail else ""))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubError("GitHub nicht erreichbar: " + str(exc)[:180])

def _repo(owner, repo):
    for part in (owner, repo):
        if not part or len(part) > 100 or not all(c.isalnum() or c in "-._" for c in part):
            raise GitHubError("Ungültiger Repository-Name.")
    return urllib.parse.quote(owner, safe="") + "/" + urllib.parse.quote(repo, safe="")

def overview():
    user = request("GET", "/user")
    repos = request("GET", "/user/repos?per_page=100&sort=updated&affiliation=owner,collaborator,organization_member")
    return {"connected": True, "user": {"login": user.get("login", ""), "avatar_url": user.get("avatar_url", "")},
            "repositories": [{"full_name":r.get("full_name"),"description":r.get("description") or "",
              "private":bool(r.get("private")),"default_branch":r.get("default_branch","main"),
              "html_url":r.get("html_url"),"updated_at":r.get("updated_at"),
              "permissions":r.get("permissions") or {}} for r in repos if isinstance(r,dict)]}

def repository_data(owner, repo):
    name = _repo(owner, repo)
    base = "/repos/" + name
    repo_info = request("GET", base)
    branches = request("GET", base + "/branches?per_page=100")
    issues = request("GET", base + "/issues?state=open&per_page=30")
    pulls = request("GET", base + "/pulls?state=open&per_page=30")
    runs = request("GET", base + "/actions/runs?per_page=10")
    commits = request("GET", base + "/commits?per_page=10")
    return {
      "repository":{"full_name":repo_info.get("full_name"),"description":repo_info.get("description") or "",
        "default_branch":repo_info.get("default_branch"),"html_url":repo_info.get("html_url"),
        "private":bool(repo_info.get("private")),"permissions":repo_info.get("permissions") or {}},
      "branches":[{"name":x.get("name"),"protected":bool(x.get("protected")),"commit":(x.get("commit") or {}).get("sha","")} for x in branches if isinstance(x,dict)],
      "issues":[{"number":x.get("number"),"title":x.get("title"),"html_url":x.get("html_url"),
        "state":x.get("state"),"user":(x.get("user") or {}).get("login"),"updated_at":x.get("updated_at")}
        for x in issues if isinstance(x,dict) and "pull_request" not in x],
      "pulls":[{"number":x.get("number"),"title":x.get("title"),"html_url":x.get("html_url"),
        "state":x.get("state"),"draft":bool(x.get("draft")),"mergeable":x.get("mergeable"),
        "head":(x.get("head") or {}).get("ref"),"base":(x.get("base") or {}).get("ref")}
        for x in pulls if isinstance(x,dict)],
      "runs":[{"id":x.get("id"),"name":x.get("name"),"status":x.get("status"),
        "conclusion":x.get("conclusion"),"html_url":x.get("html_url"),"created_at":x.get("created_at"),
        "branch":(x.get("head_branch") or "")} for x in runs.get("workflow_runs",[])],
      "commits":[{"sha":x.get("sha","")[:12],"message":((x.get("commit") or {}).get("message") or "").splitlines()[0][:180],
        "html_url":x.get("html_url"),"author":((x.get("commit") or {}).get("author") or {}).get("name","")}
        for x in commits if isinstance(x,dict)]
    }

def create_issue(owner, repo, title, body=""):
    if not isinstance(title,str) or not title.strip() or len(title)>200: raise GitHubError("Der Titel muss 1–200 Zeichen lang sein.")
    if not isinstance(body,str) or len(body)>10000: raise GitHubError("Der Beschreibungstext ist zu lang.")
    result=request("POST","/repos/"+_repo(owner,repo)+"/issues",{"title":title.strip(),"body":body})
    return {"number":result.get("number"),"html_url":result.get("html_url"),"title":result.get("title")}

def create_branch(owner, repo, branch, source):
    if not isinstance(branch,str) or not branch.strip() or len(branch)>240 or any(c.isspace() for c in branch) or ".." in branch or branch.startswith("/") or branch.endswith("/"):
        raise GitHubError("Ungültiger Branch-Name.")
    if branch.strip() in ("main","master","production","release"):
        raise GitHubError("Geschützte Standard-/Release-Namen können hier nicht angelegt werden.")
    name=_repo(owner,repo); base="/repos/"+name
    ref=request("GET",base+"/git/ref/heads/"+urllib.parse.quote(source,safe="/-._"))
    sha=((ref.get("object") or {}).get("sha"))
    if not sha: raise GitHubError("Quell-Branch konnte nicht aufgelöst werden.")
    result=request("POST",base+"/git/refs",{"ref":"refs/heads/"+branch.strip(),"sha":sha})
    return {"branch":branch.strip(),"sha":((result.get("object") or {}).get("sha",""))}

def dispatch_workflow(owner, repo, workflow, branch):
    if not isinstance(workflow,str) or not workflow or "/" in workflow or ".." in workflow:
        raise GitHubError("Ungültige Workflow-Datei.")
    if not isinstance(branch,str) or not branch or len(branch)>240:
        raise GitHubError("Ungültiger Branch.")
    request("POST","/repos/"+_repo(owner,repo)+"/actions/workflows/"+urllib.parse.quote(workflow,safe="")+"/dispatches",
            {"ref":branch})
    return {"dispatched":True,"workflow":workflow,"branch":branch}
