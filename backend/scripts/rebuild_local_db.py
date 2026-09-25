"""Rebuild a local database and migrate it to head — the recovery for a database a squash left behind.

A squash folds the migration chain into `0001`, so a database still recorded at a revision the
squash removed can no longer be upgraded: alembic cannot find the revision to start from. Stamping
it at the new head (`alembic stamp --purge`) would be wrong — it would claim the migrations after
its revision ran when they never did. The fix is to drop it and build it again from the chain.

Only the known local databases can be rebuilt, never under a staging or production
`APPODUS_ACTIVE_ENV`, and nothing is dropped without `--yes` (without it, the script prints what it
would do). The database lives in the compose Postgres container; `alembic` runs with `DB_NAME` set
to the target, over the caller's environment (so pick the env file with `APPODUS_ACTIVE_ENV`, and
`DB_SERVER=127.0.0.1` on Windows, where `localhost` can resolve to WSL's relay).

Run from backend/:
    APPODUS_ACTIVE_ENV=test python scripts/rebuild_local_db.py veriprops_test --yes
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Optional, Sequence

# The databases a developer's compose Postgres holds. Anything else — above all a deployed
# database reached through a mistyped env — is refused.
_LOCAL_DATABASES = re.compile(r"^veriprops_(test|local|e2e|uat)$")
_DEPLOYED_ENVS = {"staging", "prod", "production"}
_DEFAULT_CONTAINER = "veriprops-mono-postgres-1"


class RefusedTarget(Exception):
    """The database or environment is not one this script may rebuild."""


def check_target(name: str, active_env: Optional[str]) -> None:
    """Refuse anything but a known local database, and any deployed environment."""
    if not _LOCAL_DATABASES.match(name):
        raise RefusedTarget(f"{name!r} is not a local database (expected veriprops_test|local|e2e|uat)")
    if (active_env or "").lower() in _DEPLOYED_ENVS:
        raise RefusedTarget(f"refusing to rebuild a database under APPODUS_ACTIVE_ENV={active_env}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", help="veriprops_test | veriprops_local | veriprops_e2e | veriprops_uat")
    parser.add_argument("--container", default=_DEFAULT_CONTAINER, help="the compose Postgres container")
    parser.add_argument("--yes", action="store_true", help="actually drop and rebuild (irreversible)")
    args = parser.parse_args(argv)

    try:
        check_target(args.database, os.environ.get("APPODUS_ACTIVE_ENV"))
    except RefusedTarget as refused:
        print(f"Refused: {refused}", file=sys.stderr)
        return 2

    recreate = [
        "docker", "exec", args.container, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
        "-c", f"DROP DATABASE IF EXISTS {args.database} WITH (FORCE)",
        "-c", f"CREATE DATABASE {args.database}",
    ]
    migrate = [sys.executable, "-m", "alembic", "upgrade", "head"]

    if not args.yes:
        print(f"Would drop and recreate {args.database} in {args.container}, then run "
              f"`alembic upgrade head` against it. Every row in it is lost. Re-run with --yes.")
        return 0

    for step, command, env in (
        ("recreate", recreate, None),
        ("migrate", migrate, {**os.environ, "DB_NAME": args.database}),
    ):
        print(f"── {step}: {' '.join(command)}")
        if subprocess.run(command, env=env).returncode != 0:
            print(f"Failed at {step}; {args.database} may be empty — re-run once the cause is fixed.",
                  file=sys.stderr)
            return 1
    print(f"{args.database} rebuilt at head.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
