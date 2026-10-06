"""Coverage for the deploy/ backup + restore scripts.

``backend/tests`` is the only pytest root wired into CI, so the operational
shell scripts that protect the data are exercised here rather than by eye. They
are driven with stubbed ``rclone`` / ``docker`` executables on PATH, which lets
the tests assert *what the scripts ask those tools to do* (arguments, ordering,
exit codes) without Docker, rclone, or any real object storage.

The behaviours worth locking down are the ones whose failure mode is silence:

* a half-configured off-site run must fail loudly — a missing ``rclone`` or a
  missing ``OFFSITE_REMOTE`` is how "we have backups" quietly becomes untrue;
* ``rclone copy`` is used, never ``sync`` (a mirror must not be able to delete
  the remote), and only our own artifact patterns are shipped;
* a failing ``rclone`` propagates a non-zero exit so cron records it;
* ``restore.sh`` restores the **uploads** archive too, and warns loudly when it
  is omitted (a database-only restore silently loses every receipt).
"""
from __future__ import annotations

import configparser
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
OFFSITE = REPO / "deploy" / "offsite-backup.sh"
RESTORE = REPO / "deploy" / "restore.sh"
RCLONE_OCI = REPO / "deploy" / "rclone-oci.conf.example"
OFFSITE_ENV_EXAMPLE = REPO / "deploy" / "offsite.env.example"

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is required")

PGDUMP = "bahraini28-20260101-020000.pgdump"
UPLOADS = "uploads-20260101-020000.tar.gz"


def _spy(bin_dir: Path, name: str) -> Path:
    """Create a stub ``name`` that appends its argv to ``$<NAME>_LOG``.

    Honours ``$<NAME>_EXIT`` so a failure can be simulated. Appends (rather than
    truncates) because ``restore.sh`` invokes ``docker`` twice.
    """
    upper = name.upper()
    body = (
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$@" >> "$' + upper + '_LOG"\n'
        'exit "${' + upper + '_EXIT:-0}"\n'
    )
    path = bin_dir / name
    path.write_text(body)
    path.chmod(0o755)
    return bin_dir / f"{name}.log"


def _env(bin_dir: Path, tmp_path: Path, *, path: str | None = None, **extra: str):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["PATH"] = path if path is not None else f"{bin_dir}:{env['PATH']}"
    env.update(extra)
    return env


def _app_dir(tmp_path: Path) -> Path:
    """A stand-in for /opt/bahraini28 (restore.sh cds here)."""
    app = tmp_path / "app"
    (app / "deploy").mkdir(parents=True)
    (app / "deploy" / "docker-compose.yml").write_text("services: {}\n")
    return app


def _backup_dir(tmp_path: Path) -> Path:
    backup = tmp_path / "backups"
    backup.mkdir()
    (backup / PGDUMP).write_bytes(b"dump")
    (backup / UPLOADS).write_bytes(b"archive")
    return backup


def _run(script: Path, *args: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, str(script), *args], env=env, capture_output=True, text=True
    )


# --- off-site backups: fail loudly rather than silently ------------------------


def test_offsite_requires_a_remote(tmp_path):
    """An unset OFFSITE_REMOTE must fail: otherwise nothing leaves the host."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _spy(bin_dir, "rclone")

    result = _run(
        OFFSITE,
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(_backup_dir(tmp_path)),
            OFFSITE_REMOTE="",
        ),
    )

    assert result.returncode == 1
    assert "OFFSITE_REMOTE is not set" in result.stderr


def test_offsite_requires_rclone(tmp_path):
    """A missing rclone is a hard failure, not a silent skip."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Coreutils only: the directories rclone usually lives in are absent.
    core_path = f"{bin_dir}:/usr/bin:/bin"
    if shutil.which("rclone", path=core_path) is not None:
        pytest.skip("rclone lives in /usr/bin or /bin on this machine")

    result = _run(
        OFFSITE,
        env=_env(
            bin_dir,
            tmp_path,
            path=core_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(_backup_dir(tmp_path)),
            OFFSITE_REMOTE="oci:test-bucket",
        ),
    )

    assert result.returncode == 1
    assert "rclone" in result.stderr


def test_offsite_errors_when_there_is_nothing_to_send(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _spy(bin_dir, "rclone")
    empty = tmp_path / "empty-backups"
    empty.mkdir()

    result = _run(
        OFFSITE,
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(empty),
            OFFSITE_REMOTE="oci:test-bucket",
        ),
    )

    assert result.returncode == 1
    assert "no backup artifacts" in result.stderr


# --- off-site backups: what actually gets sent ---------------------------------


def test_offsite_uses_copy_for_our_artifacts_only(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "rclone")
    backup = _backup_dir(tmp_path)
    # A stray file must never be shipped to the bucket.
    (backup / "operator-notes.txt").write_text("not a backup")

    result = _run(
        OFFSITE,
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(backup),
            OFFSITE_REMOTE="oci:test-bucket",
            RCLONE_LOG=str(log),
        ),
    )

    assert result.returncode == 0, result.stderr
    args = log.read_text().splitlines()
    assert args[0] == "copy"  # never `sync`: the remote must not be prunable here
    assert str(backup) in args
    assert "oci:test-bucket" in args
    assert "bahraini28-*.pgdump" in args
    assert "uploads-*.tar.gz" in args


def test_offsite_propagates_a_rclone_failure(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "rclone")

    result = _run(
        OFFSITE,
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(_backup_dir(tmp_path)),
            OFFSITE_REMOTE="oci:test-bucket",
            RCLONE_LOG=str(log),
            RCLONE_EXIT="1",
        ),
    )

    assert result.returncode == 1
    assert "failed" in result.stderr


def test_offsite_dry_run_uploads_nothing(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "rclone")

    result = _run(
        OFFSITE,
        "--dry-run",
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            BACKUP_DIR=str(_backup_dir(tmp_path)),
            OFFSITE_REMOTE="oci:test-bucket",
            RCLONE_LOG=str(log),
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "--dry-run" in log.read_text().splitlines()
    assert "DRY RUN" in result.stdout


def test_offsite_reads_deploy_offsite_env(tmp_path):
    """The documented config file is honoured when the env var is absent."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "rclone")
    app = _app_dir(tmp_path)
    (app / "deploy" / "offsite.env").write_text("OFFSITE_REMOTE=oci:from-the-file\n")

    env = _env(
        bin_dir,
        tmp_path,
        BAHRAINI28_DIR=str(app),
        BACKUP_DIR=str(_backup_dir(tmp_path)),
        RCLONE_LOG=str(log),
    )
    env.pop("OFFSITE_REMOTE", None)

    result = _run(OFFSITE, env=env)

    assert result.returncode == 0, result.stderr
    assert "oci:from-the-file" in log.read_text().splitlines()


# --- off-site target: the Oracle Object Storage example stays installable ------


def test_rclone_oci_example_is_a_valid_single_remote():
    """The file the docs tell operators to install must stay installable.

    It is copied verbatim to ``~/.config/rclone/rclone.conf``, so it has to parse
    and declare **exactly one** ``oci`` remote — uncommenting two of the flavour
    examples (or adding a second section) would make rclone reject the file.
    """
    config = configparser.ConfigParser()
    config.read(RCLONE_OCI)
    assert config.sections() == ["oci"]
    # oracleobjectstorage is the native API; s3 is the S3-compatible flavour.
    assert config["oci"]["type"] in {"oracleobjectstorage", "s3"}


def test_offsite_env_example_points_at_the_oci_remote():
    """The env template must name the destination the example config backs."""
    text = OFFSITE_ENV_EXAMPLE.read_text()
    assert "oci:bahraini28-backups" in text
    assert "rclone-oci.conf.example" in text


# --- restore: the uploads volume is part of the backup -------------------------


def test_restore_requires_a_dump(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _spy(bin_dir, "docker")

    result = _run(RESTORE, env=_env(bin_dir, tmp_path, BAHRAINI28_DIR=str(_app_dir(tmp_path))))

    assert result.returncode == 1
    assert "usage:" in result.stderr


def test_restore_restores_database_and_uploads(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "docker")
    backup = _backup_dir(tmp_path)

    result = _run(
        RESTORE,
        str(backup / PGDUMP),
        str(backup / UPLOADS),
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            DOCKER_LOG=str(log),
        ),
    )

    assert result.returncode == 0, result.stderr
    lines = log.read_text().splitlines()
    assert "compose" in lines
    assert any("pg_restore" in line for line in lines)
    # ... and the receipts/logos archive is unpacked into the uploads volume.
    assert "bahraini28_uploads:/data" in lines
    assert f"/backup/{UPLOADS}" in lines
    assert "xzf" in lines
    assert "Uploads restore OK" in result.stdout


def test_restore_warns_when_the_uploads_archive_is_missing(tmp_path):
    """A database-only restore must say out loud that the files are now gone."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = _spy(bin_dir, "docker")
    backup = _backup_dir(tmp_path)

    result = _run(
        RESTORE,
        str(backup / PGDUMP),
        env=_env(
            bin_dir,
            tmp_path,
            BAHRAINI28_DIR=str(_app_dir(tmp_path)),
            DOCKER_LOG=str(log),
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stdout
    assert "404" in result.stdout
    assert "xzf" not in log.read_text().splitlines()
