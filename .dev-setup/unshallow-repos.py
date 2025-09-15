from pathlib import Path
import subprocess
import argparse
from loguru import logger

def arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Scan a folder for Git repositories and unshallow selected ones."
    )
    parser.add_argument(
        "root_dir",
        nargs="?",
        default="/workspace/src",
        help="Path to scan for git repositories"
    )
    args = parser.parse_args()

    return args

def is_git_repo(path: Path) -> bool:
    """
    Check if a directory is a Git repository.
    """
    return (path / ".git").is_dir()

def is_shallow_clone(repo_path: Path) -> bool:
    """
    Check if a Git repository is a shallow clone.
    """
    return (repo_path / ".git" / "shallow").is_file()

def find_git_repos(root_dir: Path):
    """
    Find all Git repositories under the given root directory.
    """
    repos = []
    # Use rglob to find .git dirs
    for path in root_dir.rglob(".git"):
        if path.is_dir():
            repos.append(path.parent)
    return repos

def unshallow_git_repo(cwd: Path):
    """
    Unshallow a Git repository.
    """
    logger.info(f"Unshallowing repository: {cwd}")
    subprocess.run(["git", "fetch", "--unshallow"], cwd=cwd)
    subprocess.run(["git", "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"], cwd=cwd)
    subprocess.run(["git", "fetch", "--all"], cwd=cwd)
    logger.success("Repository is now a full clone!")

def main():
    args = arguments()

    if args.root_dir:
        root_dir = Path(args.root_dir).expanduser().resolve()
    else:
        root_input = input("Enter the folder to scan for git repositories: ").strip()
        root_dir = Path(root_input).expanduser().resolve()

    if not root_dir.is_dir():
        logger.error(f"Invalid directory: {root_dir}")
        return

    repos = find_git_repos(root_dir)
    if not repos:
        logger.warning("No git repositories found.")
        return

    logger.info("Found repositories:")
    for idx, repo in enumerate(repos, start=1):
        mark = "[SHALLOW]" if is_shallow_clone(repo) else ""
        logger.info(f" - {repo} {mark}")

    shallows = [repo for repo in repos if is_shallow_clone(repo)]
    if not shallows:
        logger.success("No shallow clones found. All repositories are full clones.")
        return

    logger.info("Shallow repositories:")
    for idx, repo in enumerate(shallows, start=1):
        logger.info(f"  {idx}. {repo}")

    choice = input("Enter the number to unshallow (blank to skip): ").strip()
    if choice:
        try:
            repo_to_unshallow = shallows[int(choice) - 1]
        except (ValueError, IndexError):
            logger.error("Invalid selection.")
            return

        unshallow_git_repo(repo_to_unshallow)

if __name__ == "__main__":
    main()
