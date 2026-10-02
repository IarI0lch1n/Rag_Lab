import os
import subprocess

from pathlib import Path
from tempfile import TemporaryDirectory

from src.db.models import Source
from src.grabber.base import (
    BaseGrabber,
    GrabbedDocument,
)


class GitGrabber(BaseGrabber):
    MAX_FILES = 500

    MAX_FILE_SIZE = (
        2 * 1024 * 1024
    )

    IGNORED_FILENAMES = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "poetry.lock",
    }

    IGNORED_DIRECTORIES = {
        ".git",
        ".github",
        ".idea",
        ".vs",
        ".vscode",

        "__pycache__",

        "node_modules",
        "vendor",

        "venv",
        ".venv",

        "dist",
        "build",
        "coverage",

        ".next",
        "target",

        "bin",
        "obj",
    }

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
        ".markdown",
        ".rst",

        ".py",

        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".vue",

        ".php",

        ".java",
        ".cs",

        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",

        ".go",
        ".rs",
        ".rb",

        ".swift",
        ".kt",
        ".kts",

        ".sql",

        ".html",
        ".htm",

        ".css",
        ".scss",
        ".sass",
        ".less",

        ".json",
        ".xml",

        ".yaml",
        ".yml",

        ".toml",
        ".ini",
        ".cfg",

        ".sh",
        ".ps1",
        ".bat",

        ".pdf",
        ".docx",
        ".pptx",
    }

    SPECIAL_FILENAMES = {
        "readme",
        "license",
        "copying",
        "dockerfile",
        "makefile",
        "procfile",
        "gemfile",
        "rakefile",
    }

    def grab(
        self,
        source: Source,
    ) -> list[GrabbedDocument]:

        if source.source_type != "git":
            raise ValueError(
                f"GitGrabber cannot process "
                f"source type '{source.source_type}'."
            )

        if not source.uri:
            raise ValueError(
                f"Source {source.id} "
                f"has no repository URL."
            )

        documents: list[
            GrabbedDocument
        ] = []

        with TemporaryDirectory(
            prefix="rag_git_"
        ) as temp_directory:

            self._clone_repository(
                repository_url=source.uri,
                target_directory=temp_directory,
                branch=source.git_branch,
            )

            commit_sha = (
                self._run_git(
                    temp_directory,
                    [
                        "rev-parse",
                        "HEAD",
                    ],
                )
            )

            branch = (
                self._get_branch(
                    temp_directory
                )
            )

            root = Path(
                temp_directory
            )

            stop = False

            for (
                current_directory,
                directory_names,
                file_names,
            ) in os.walk(
                root,
                topdown=True,
                followlinks=False,
            ):

                directory_names[:] = [
                    directory_name
                    for directory_name
                    in directory_names
                    if (
                        directory_name.lower()
                        not in
                        self.IGNORED_DIRECTORIES
                    )
                ]

                for file_name in file_names:

                    if (
                        file_name.lower()
                        in self.IGNORED_FILENAMES
                    ):
                        continue

                    lower_name = (
                        file_name.lower()
                    )

                    if (
                        lower_name.endswith(
                            ".min.js"
                        )
                        or lower_name.endswith(
                            ".min.css"
                        )
                    ):
                        continue

                    if (
                        len(documents)
                        >= self.MAX_FILES
                    ):
                        stop = True
                        break

                    path = (
                        Path(
                            current_directory
                        )
                        / file_name
                    )

                    if not path.is_file():
                        continue

                    if not self._is_supported(
                        path
                    ):
                        continue

                    try:
                        file_size = (
                            path.stat().st_size
                        )

                    except OSError:
                        continue

                    if (
                        file_size <= 0
                        or file_size
                        > self.MAX_FILE_SIZE
                    ):
                        continue

                    try:
                        content = (
                            path.read_bytes()
                        )

                    except OSError:
                        continue

                    extension = (
                        path.suffix.lower()
                        or None
                    )

                    if (
                        self._looks_binary(
                            content
                        )
                        and extension
                        not in {
                            ".pdf",
                            ".docx",
                            ".pptx",
                        }
                    ):
                        continue

                    relative_path = (
                        path.relative_to(
                            root
                        )
                    )

                    relative_id = (
                        relative_path
                        .as_posix()
                    )

                    documents.append(
                        GrabbedDocument(
                            name=relative_id,
                            content=content,
                            mime_type=(
                                self._get_mime_type(
                                    extension
                                )
                            ),
                            file_extension=(
                                extension
                            ),
                            external_id=(
                                relative_id
                            ),
                            metadata={
                                "source": "git",
                                "repository": (
                                    source.uri
                                ),
                                "path": (
                                    relative_id
                                ),
                                "branch": (
                                    branch
                                ),
                                "commit_sha": (
                                    commit_sha
                                ),
                            },
                        )
                    )

                if stop:
                    break

        if not documents:
            raise ValueError(
                f"No supported documents "
                f"were found in repository "
                f"'{source.uri}'."
            )

        return documents

    def _clone_repository(
        self,
        repository_url: str,
        target_directory: str,
        branch: str | None,
    ) -> None:

        command = [
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
        ]

        if branch:
            command.extend(
                [
                    "--branch",
                    branch,
                ]
            )

        command.extend(
            [
                repository_url,
                target_directory,
            ]
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                "Git executable was not found. "
                "Make sure Git is installed and "
                "available in PATH."
            ) from exc

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Git clone timed out after "
                "180 seconds."
            ) from exc

        if result.returncode != 0:
            error = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown git clone error."
            )

            raise RuntimeError(
                f"Could not clone repository "
                f"'{repository_url}'. "
                f"Git error: {error}"
            )

    @staticmethod
    def _run_git(
        repository_directory: str,
        arguments: list[str],
    ) -> str:

        result = subprocess.run(
            [
                "git",
                "-C",
                repository_directory,
                *arguments,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )

        if result.returncode != 0:
            error = (
                result.stderr.strip()
                or result.stdout.strip()
            )

            raise RuntimeError(
                f"Git command failed: "
                f"{error}"
            )

        return (
            result.stdout.strip()
        )

    def _get_branch(
        self,
        repository_directory: str,
    ) -> str:

        try:
            branch = self._run_git(
                repository_directory,
                [
                    "branch",
                    "--show-current",
                ],
            )

            if branch:
                return branch

        except Exception:
            pass

        return "HEAD"

    def _is_supported(
        self,
        path: Path,
    ) -> bool:

        extension = (
            path.suffix.lower()
        )

        if (
            extension
            in self.SUPPORTED_EXTENSIONS
        ):
            return True

        filename = (
            path.name.lower()
        )

        return (
            filename
            in self.SPECIAL_FILENAMES
        )

    @staticmethod
    def _looks_binary(
        content: bytes,
    ) -> bool:

        sample = (
            content[:8192]
        )

        if not sample:
            return False

        if b"\x00" in sample:
            return True

        control_characters = sum(
            1
            for byte in sample
            if (
                byte < 9
                or (
                    13 < byte < 32
                )
            )
        )

        return (
            control_characters
            / len(sample)
            > 0.10
        )

    @staticmethod
    def _get_mime_type(
        extension: str | None,
    ) -> str:

        mime_types = {
            ".md": (
                "text/markdown"
            ),
            ".markdown": (
                "text/markdown"
            ),

            ".txt": (
                "text/plain"
            ),
            ".rst": (
                "text/plain"
            ),

            ".json": (
                "application/json"
            ),

            ".xml": (
                "application/xml"
            ),

            ".html": (
                "text/html"
            ),
            ".htm": (
                "text/html"
            ),

            ".yaml": (
                "text/yaml"
            ),
            ".yml": (
                "text/yaml"
            ),

            ".pdf": (
                "application/pdf"
            ),

            ".docx": (
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml."
                "document"
            ),

            ".pptx": (
                "application/vnd.openxmlformats-"
                "officedocument.presentationml."
                "presentation"
            ),
        }

        if extension in mime_types:
            return (
                mime_types[
                    extension
                ]
            )

        return "text/plain"


git_grabber = GitGrabber()