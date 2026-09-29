"""
Git Synchronization Manager — Local Master Architecture
=========================================================
Ensures continuous, seamless synchronization between local workspace and GitHub.
STRICT RULE: Local is ALWAYS the Master Copy (Single Source of Truth).
If any divergence or conflict occurs with remote, local changes always win (-X ours).
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")

logger = logging.getLogger("GitSyncManager")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "git_sync_state.json")


def _run_git_cmd(args: list[str], cwd: str = BASE_DIR, timeout: int = 30) -> tuple[int, str, str]:
    """Runs a git command safely and returns (returncode, stdout, stderr)."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Git command timed out"
    except Exception as e:
        return -2, "", str(e)


class GitSyncManager:
    """
    Manages synchronization with GitHub where Local is the authoritative Master Copy.
    """

    @classmethod
    def load_state(cls) -> Dict[str, Any]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "last_sync_time": "",
            "last_sync_status": "NEVER_SYNCED",
            "last_commit_hash": "",
            "auto_sync_enabled": True
        }

    @classmethod
    def save_state(cls, state: Dict[str, Any]):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    @classmethod
    def get_sync_status(cls) -> Dict[str, Any]:
        """Returns the current Git synchronization status relative to origin/main."""
        ret, out, _ = _run_git_cmd(["status", "--porcelain"])
        has_local_changes = bool(out.strip())

        # Check commits ahead/behind
        _run_git_cmd(["fetch", "origin", "main"], timeout=15)
        ret_ahead, out_ahead, _ = _run_git_cmd(["rev-list", "--count", "origin/main..HEAD"])
        ret_behind, out_behind, _ = _run_git_cmd(["rev-list", "--count", "HEAD..origin/main"])

        ahead_count = int(out_ahead) if ret_ahead == 0 and out_ahead.isdigit() else 0
        behind_count = int(out_behind) if ret_behind == 0 and out_behind.isdigit() else 0

        state = cls.load_state()
        return {
            "has_local_changes": has_local_changes,
            "ahead_commits": ahead_count,
            "behind_commits": behind_count,
            "in_sync": (not has_local_changes and ahead_count == 0 and behind_count == 0),
            "last_sync_time": state.get("last_sync_time", "N/A"),
            "last_sync_status": state.get("last_sync_status", "N/A")
        }

    @classmethod
    def sync_local_to_git(cls, commit_message: Optional[str] = None, auto: bool = False) -> Dict[str, Any]:
        """
        Synchronizes local workspace to GitHub with Local as Master.
        1. Adds all modified, created, or deleted files.
        2. Commits if local changes exist.
        3. Pulls remote updates using merge strategy option 'ours' (local always wins on conflict).
        4. Pushes to origin main.
        """
        now_dt = datetime.now(IST)
        now_str = now_dt.strftime("%Y-%m-%d %I:%M:%S %p IST")
        tag = "[AUTO-SYNC]" if auto else "[SYNC]"

        # Check uncommitted changes
        ret, status_out, _ = _run_git_cmd(["status", "--porcelain"])
        has_changes = bool(status_out.strip())

        committed = False
        if has_changes:
            # Stage all changes
            _run_git_cmd(["add", "-A"])
            msg = commit_message or f"chore(sync): {tag} local master update {now_str}"
            ret_c, out_c, err_c = _run_git_cmd(["commit", "-m", msg])
            if ret_c == 0:
                committed = True
            else:
                logger.debug(f"Commit note: {out_c} {err_c}")

        # Fetch remote to inspect divergence
        _run_git_cmd(["fetch", "origin", "main"], timeout=20)

        # Pull if behind, with LOCAL ALWAYS PREFERRED (strategy: ours)
        ret_behind, out_behind, _ = _run_git_cmd(["rev-list", "--count", "HEAD..origin/main"])
        behind_count = int(out_behind) if ret_behind == 0 and out_behind.isdigit() else 0

        merged = False
        if behind_count > 0:
            # Merge remote changes, but in any file conflict, local master wins!
            ret_m, out_m, err_m = _run_git_cmd([
                "merge", "origin/main",
                "--no-edit",
                "-s", "ort",
                "-X", "ours",
                "-m", f"chore(sync): merge origin/main into local master with local priority {now_str}"
            ], timeout=25)
            if ret_m == 0:
                merged = True
            else:
                logger.warning(f"Merge warning: {err_m}. Proceeding with local as master.")

        # Push local master to origin main
        ret_p, out_p, err_p = _run_git_cmd(["push", "origin", "main"], timeout=30)
        success = (ret_p == 0)

        # If push failed because remote diverged, push with local master precedence
        if not success and ("non-fast-forward" in err_p.lower() or "rejected" in err_p.lower() or "failed to push" in err_p.lower()):
            logger.info("Resolving non-fast-forward push with local master precedence...")
            _run_git_cmd(["merge", "origin/main", "--no-edit", "-X", "ours"])
            ret_p2, out_p2, err_p2 = _run_git_cmd(["push", "origin", "main"], timeout=30)
            if ret_p2 != 0:
                # Fallback: force with lease to ensure local master is preserved
                ret_p2, out_p2, err_p2 = _run_git_cmd(["push", "--force-with-lease", "origin", "main"], timeout=30)
            success = (ret_p2 == 0)
            if not success:
                err_p = err_p2

        # Record state
        ret_rev, last_rev, _ = _run_git_cmd(["rev-parse", "--short", "HEAD"])
        state = cls.load_state()
        state["last_sync_time"] = now_str
        state["last_sync_status"] = "SUCCESS" if success else f"PUSH_FAILED: {err_p[:120]}"
        state["last_commit_hash"] = last_rev if ret_rev == 0 else ""
        cls.save_state(state)

        if success:
            logger.info(f"✅ Git Sync Successful: Local Master -> origin/main ({now_str})")
        else:
            logger.error(f"❌ Git Push Failed: {err_p}")

        return {
            "success": success,
            "committed": committed,
            "merged": merged,
            "time": now_str,
            "message": "Local Master successfully synced to origin/main." if success else f"Sync failed: {err_p}",
            "commit_hash": last_rev if ret_rev == 0 else ""
        }


if __name__ == "__main__":
    print("=" * 60)
    print("🔄 Reliance Quant Engine — Git Sync (Local Master)")
    print("=" * 60)
    res = GitSyncManager.sync_local_to_git()
    print(f"Status  : {'✅ SUCCESS' if res['success'] else '❌ FAILED'}")
    print(f"Time    : {res['time']}")
    print(f"Details : {res['message']}")
    if res.get("commit_hash"):
        print(f"Commit  : {res['commit_hash']}")
    print("=" * 60)
