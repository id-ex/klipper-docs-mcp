"""Git Manager for Klipper Docs MCP Server.

Handles Git operations including cloning, pulling, and checking for updates.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import GitConfig
from ..exceptions import GitOperationError


@dataclass
class SyncResult:
    """Result of a repository sync operation."""

    repo_name: str
    success: bool
    message: str
    was_cloned: bool = False
    was_updated: bool = False


class GitManager:
    """Manages Git repository operations for documentation."""

    def __init__(self, config: Optional[GitConfig] = None):
        """Initialize the Git manager.

        Args:
            config: Git configuration. If None, uses default config.
        """
        self.config = config or GitConfig()

    @property
    def docs_dir(self) -> Path:
        """Get the documentation directory path."""
        return self.config.docs_dir

    @property
    def repositories(self) -> dict:
        """Get repository configurations."""
        return self.config.repositories

    def _run_git_command(
        self,
        args: list[str],
        cwd: Path,
        timeout: int,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a Git command.

        Args:
            args: Command arguments (excluding 'git').
            cwd: Working directory for the command.
            timeout: Command timeout in seconds.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            Completed process result.
        """
        cmd = ["git"] + args
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=capture_output,
            timeout=timeout,
        )

    def sync_repository(self, name: str, repo_config: dict) -> SyncResult:
        """Sync a single repository.

        Args:
            name: Repository name.
            repo_config: Repository configuration dict with 'url' and 'sparse_path'.

        Returns:
            SyncResult with operation outcome.
        """
        repo_dir = self.docs_dir / name
        url = repo_config["url"]
        sparse_path = repo_config.get("sparse_path", "")

        try:
            if not repo_dir.exists():
                return self._clone_repository(name, repo_dir, url, sparse_path)
            else:
                return self._update_repository(name, repo_dir)
        except Exception as e:
            return SyncResult(
                repo_name=name,
                success=False,
                message=f"Error: {e}",
            )

    def _clone_repository(self, name: str, repo_dir: Path, url: str, sparse_path: str) -> SyncResult:
        """Clone a new repository.

        Args:
            name: Repository name.
            repo_dir: Target directory for clone.
            url: Repository URL.
            sparse_path: Sparse checkout path (empty for full clone).

        Returns:
            SyncResult with clone outcome.
        """
        # Clone with no checkout initially if sparse is needed
        if sparse_path:
            clone_cmd = ["git", "clone", "--depth=1", "--no-checkout", url, str(repo_dir)]
        else:
            clone_cmd = ["git", "clone", "--depth=1", url, str(repo_dir)]

        result = self._run_git_command(
            clone_cmd[1:],  # Exclude 'git' prefix
            cwd=self.docs_dir.parent,
            timeout=self.config.clone_timeout,
        )

        if result.returncode != 0:
            return SyncResult(
                repo_name=name,
                success=False,
                message=f"Clone failed:\n{result.stderr}",
            )

        # Configure sparse checkout if needed
        if sparse_path:
            self._run_git_command(
                ["config", "core.sparseCheckout", "true"],
                cwd=repo_dir,
                timeout=self.config.rev_parse_timeout,
            )
            self._run_git_command(
                ["sparse-checkout", "set", sparse_path],
                cwd=repo_dir,
                timeout=self.config.rev_parse_timeout,
            )
            self._run_git_command(
                ["checkout"],
                cwd=repo_dir,
                timeout=self.config.rev_parse_timeout,
            )

        return SyncResult(
            repo_name=name,
            success=True,
            message="Successfully cloned.",
            was_cloned=True,
        )

    def _update_repository(self, name: str, repo_dir: Path) -> SyncResult:
        """Update an existing repository.

        Args:
            name: Repository name.
            repo_dir: Repository directory.

        Returns:
            SyncResult with update outcome.
        """
        result = self._run_git_command(
            ["pull", "--depth=1"],
            cwd=repo_dir,
            timeout=self.config.clone_timeout,
        )

        if result.returncode != 0:
            return SyncResult(
                repo_name=name,
                success=False,
                message=f"Update failed:\n{result.stderr}",
            )

        output = result.stdout.strip() or "Already up to date."
        return SyncResult(
            repo_name=name,
            success=True,
            message=output,
            was_updated=True,
        )

    def sync_all(self) -> list[SyncResult]:
        """Sync all configured repositories.

        Returns:
            List of SyncResult objects for each repository.
        """
        # Ensure docs directory exists
        if not self.docs_dir.exists():
            self.docs_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for name, config in self.repositories.items():
            results.append(self.sync_repository(name, config))

        return results

    def check_if_outdated(self) -> bool:
        """Check if any local repository is outdated compared to remote.

        Returns:
            True if any repository is outdated, False otherwise.
        """
        if not self.docs_dir.exists():
            return False

        for name in self.repositories:
            repo_dir = self.docs_dir / name
            if not repo_dir.exists():
                continue

            try:
                # Fetch without downloading data
                self._run_git_command(
                    ["fetch"],
                    cwd=repo_dir,
                    timeout=self.config.fetch_timeout,
                )

                # Compare HEAD with remote
                local_rev = self._run_git_command(
                    ["rev-parse", "HEAD"],
                    cwd=repo_dir,
                    timeout=self.config.rev_parse_timeout,
                )
                remote_rev = self._run_git_command(
                    ["rev-parse", "@{u}"],
                    cwd=repo_dir,
                    timeout=self.config.rev_parse_timeout,
                )

                if local_rev.returncode == 0 and remote_rev.returncode == 0:
                    local_hash = local_rev.stdout.strip()
                    remote_hash = remote_rev.stdout.strip()
                    if local_hash != remote_hash:
                        return True

            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        return False
