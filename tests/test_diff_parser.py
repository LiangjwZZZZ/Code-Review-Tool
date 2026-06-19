import subprocess
from pathlib import Path

from review.engine.diff_parser import parse_diff, get_changed_symbols, get_commit_info, get_diff


SAMPLE_DIFF = """diff --git a/src/auth/session.py b/src/auth/session.py
index 123..456 100644
--- a/src/auth/session.py
+++ b/src/auth/session.py
@@ -10,7 +10,7 @@ class SessionManager:
         self.timeout = timeout

-    def validate(self, token: str) -> bool:
+    def validate(self, token: str, user_id: str) -> bool:
         if not token:
             return False
+        return self._check_user(token, user_id)
diff --git a/src/api/routes.py b/src/api/routes.py
index 789..012 100644
--- a/src/api/routes.py
+++ b/src/api/routes.py
@@ -5,6 +5,7 @@ from auth.session import SessionManager
 def login():
     sm = SessionManager()
-    sm.validate(request.token)
+    sm.validate(request.token, request.user_id)
"""


def test_parse_diff_counts():
    changes = parse_diff(SAMPLE_DIFF)
    assert len(changes) == 2
    assert changes[0].file == "src/auth/session.py"
    assert changes[0].added == 2
    assert changes[0].removed == 1
    assert changes[1].file == "src/api/routes.py"
    assert changes[1].added == 1
    assert changes[1].removed == 1


def test_parse_diff_hunks():
    changes = parse_diff(SAMPLE_DIFF)
    assert len(changes[0].hunks) == 1
    assert changes[0].hunks[0].startswith("@@")


def test_get_changed_symbols():
    changes = parse_diff(SAMPLE_DIFF)
    symbols = get_changed_symbols(changes)
    assert "session" in symbols
    assert "routes" in symbols


def _git_sha(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def _git_init(repo: Path):
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, capture_output=True)


def test_get_commit_info(tmp_path):
    repo = Path(tmp_path / "repo")
    _git_init(repo)
    (repo / "f.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, capture_output=True)
    (repo / "f.txt").write_text("world")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second commit"], cwd=repo, capture_output=True)
    sha = _git_sha(repo)

    info = get_commit_info(sha, str(repo))
    assert info["hash"] == sha
    assert info["message"] == "second commit"
    assert info["author"] == "Tester"


def test_get_diff(tmp_path):
    repo = Path(tmp_path / "repo2")
    _git_init(repo)
    (repo / "f.txt").write_text("line1\nline2\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=repo, capture_output=True)
    (repo / "f.txt").write_text("line1\nline2\nline3\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=repo, capture_output=True)
    sha = _git_sha(repo)

    diff = get_diff(sha, str(repo))
    assert "f.txt" in diff
    assert "+line3" in diff


def test_get_diff_root_commit(tmp_path):
    repo = Path(tmp_path / "repo3")
    _git_init(repo)
    (repo / "init.txt").write_text("init content\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True)
    sha = _git_sha(repo)

    diff = get_diff(sha, str(repo))
    assert "init.txt" in diff
    assert "+init content" in diff


def test_parse_diff_empty():
    assert parse_diff("") == []


def test_parse_diff_binary_file():
    diff = """diff --git a/icon.png b/icon.png
index 000..111 100644
Binary files a/icon.png and b/icon.png differ
"""
    changes = parse_diff(diff)
    assert len(changes) == 1
    assert changes[0].file == "icon.png"
    assert changes[0].added == 0
    assert changes[0].removed == 0


def test_get_changed_symbols_extracts_java_methods():
    """Test that get_changed_symbols extracts actual Java method names from diff."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Foo.java b/src/com/example/Foo.java
--- a/src/com/example/Foo.java
+++ b/src/com/example/Foo.java
@@ -10,6 +10,10 @@ public class Foo {
     public void oldMethod() {
     }

+    public void newMethod(String param) {
+        return;
+    }
+
     public static int helper(int x) {
"""
    changes = [DiffChange(file="src/com/example/Foo.java", added=4, removed=0, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert "newMethod" in symbols
    assert "helper" not in symbols  # helper 没被修改


def test_get_changed_symbols_extracts_class_name():
    """Test that get_changed_symbols extracts class name when class declaration is modified."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Bar.java b/src/com/example/Bar.java
--- a/src/com/example/Bar.java
+++ b/src/com/example/Bar.java
@@ -5,7 +5,7 @@
- public class Bar {
+ public class Bar extends BaseActivity {
"""
    changes = [DiffChange(file="src/com/example/Bar.java", added=1, removed=1, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert "Bar" in symbols


def test_get_changed_symbols_no_duplicates():
    """Test that duplicate symbols are removed."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Foo.java b/src/com/example/Foo.java
--- a/src/com/example/Foo.java
+++ b/src/com/example/Foo.java
@@ -10,6 +10,8 @@
+    public void doSomething() {
+    }
+    public void doSomething(int x) {
+    }
"""
    changes = [DiffChange(file="src/com/example/Foo.java", added=4, removed=0, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert symbols.count("doSomething") == 1
