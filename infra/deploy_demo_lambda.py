#!/usr/bin/env python3
"""Package, deploy, and tear down the ``calle-demo-ringedingeding`` Lambda Function URL.

Plain boto3 + zipfile, following the same pattern already deployed for `roshambo`
(``roshambo/infra/deploy_demo_lambda.py``, live since 2026-07-30) — no SAM/CDK/
CloudFormation. This function is substantially **simpler** than roshambo's: this
project's only storage is stdlib SQLite (``ringedingeding/store.py``), so there is no
external database, no TLS root certificate to bundle, and no ``uvicorn`` either —
Mangum replaces it, and the whole runtime dependency set is four pure-Python packages
(see ``PACKAGE_DEPENDENCIES``).

Subcommands
-----------

``package``      Build ``calle-demo-ringedingeding.zip``: the whole ``ringedingeding``
                 package (code, fixtures, locales, web templates/static — everything
                 ``pyproject.toml``'s own ``[tool.setuptools.package-data]`` ships),
                 ``demo/`` (the Mangum adapter), and the runtime dependencies as
                 Lambda-compatible (manylinux) wheels regardless of the platform this
                 script runs on.
``create-role``  Create or update the execution role. **Not** the managed
                 ``AWSLambdaBasicExecutionRole`` (that policy's ``Resource`` is ``*`` —
                 every log group in the account) — an inline policy scoped to exactly
                 this function's own log group, nothing else. This function needs no
                 other AWS permission: no Bedrock, no S3, no database access, because
                 there is no database.
``deploy``       Create or update the Lambda function from a packaged zip, with
                 ``ReservedConcurrentExecutions=1`` (see "Cost guard" and
                 "Live-path hardening" below) and a short ``--timeout`` (default 15s,
                 see "Why a short timeout").
``enable-url``   Create the public Function URL (``AuthType=NONE``) and the matching
                 resource-policy statements that actually allow anonymous invocation.
``teardown``     Best-effort delete of the function, its Function URL, its role's
                 inline policy and the role itself, and its log group. Not a
                 transactional stack deletion.

Live-path hardening — the point this deployment exists to prove
------------------------------------------------------------------

Two independent things make it structurally impossible for this deployment to place a
real telephone call, and both are enforced here, not left to a comment:

1. ``_demo_environment()`` returns **exactly** ``{"DEMO_MODE": "1"}`` — no ``CALLE_*``
   variable is ever read from the deploying shell or passed through. There is no
   passthrough mechanism in this file at all; a key that is never set cannot be spent.
2. ``DEMO_MODE=1`` is what actually blocks a call, at the code layer:
   ``ringedingeding.transports.calle.CalleTransport.__init__`` checks it *before*
   the confirmation phrase and *before* the credential resolver, and refuses
   unconditionally, for both ``CalleTransport`` and ``CalleBatchTransport``
   (`tests/test_live_guard.py`, the "demo mode" section, including a test that
   monkeypatches ``urllib.request.urlopen`` to explode and asserts it is never
   called). Losing (1) alone — a future refactor that starts passing environment
   variables through — still leaves (2) standing.

Why a short timeout
--------------------

The web UI's live round-progress page (``/projects/{id}/live``) polls over
Server-Sent-Events, which a Lambda Function URL cannot upgrade to a WebSocket but can
serve as an ordinary long-lived HTTP response. Combined with
``ReservedConcurrentExecutions=1``, an SSE connection left open indefinitely (a judge's
tab, or a stuck job) would hold the function's one execution slot for as long as the
connection stays open. Lambda itself enforces ``--timeout`` as a hard per-invocation
cap, so a short one (15s, matching roshambo) self-heals that: the connection is cut,
the slot frees, and the page's own meta-refresh fallback (``live.html``, 5s interval —
the SSE stream is a convenience, never the only path to a fresh view, see that
template's own comment) keeps the page usable regardless. No dedicated app-level
change was made for this; the general-purpose ``live_stream`` route already exits its
loop the moment a round finishes, so the only actual risk was an indefinitely open
idle connection, and the timeout alone closes that gap without adding a
demo-deployment-only branch to a route every other deployment also uses.

Cost guard
----------

``ReservedConcurrentExecutions=1`` (lower than roshambo's 5 — this demo needs to prove
it works, not sustain concurrent load) plus AWS Lambda's Free Tier (1M requests/month,
checked against real judge-scale traffic in the task this script was built for) keep
an accidental traffic spike inexpensive. Cost guards, not security controls — the
Function URL itself has no authentication, same as roshambo's; the endpoint being
public is the point of a demo link.

Nothing in this file embeds a credential of any kind.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "demo"
PACKAGE_DIR = REPO_ROOT / "ringedingeding"
INFRA_DIR = Path(__file__).resolve().parent
BUILD_DIR = INFRA_DIR / "build"
DEFAULT_ZIP_PATH = BUILD_DIR / "calle-demo-ringedingeding.zip"

FUNCTION_NAME = "calle-demo-ringedingeding"
ROLE_NAME = "calle-demo-ringedingeding-role"
HANDLER = "demo.lambda_entry.handler"
DEFAULT_REGION = "eu-central-1"

# mangum has no third-party dependencies of its own; fastapi pulls in starlette,
# pydantic, pydantic-core, anyio, sniffio, idna, typing-extensions and
# annotated-types transitively. Matches the `lambda` extra in pyproject.toml —
# deliberately no uvicorn (Mangum replaces it) and no database driver (SQLite
# is stdlib).
PACKAGE_DEPENDENCIES = [
    "mangum>=0.17",
    "fastapi>=0.110",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
]

# Same limits AWS documents for zip-based Lambda deployment.
DIRECT_UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024
UNZIPPED_LIMIT_BYTES = 250 * 1024 * 1024

PLATFORM_TAGS = {
    "x86_64": "manylinux2014_x86_64",
    "arm64": "manylinux2014_aarch64",
}


class DeployError(RuntimeError):
    """Raised for problems this script can explain better than a bare traceback."""


# --------------------------------------------------------------------------- package


def cmd_package(args: argparse.Namespace) -> None:
    if args.arch not in PLATFORM_TAGS:
        raise DeployError(f"--arch must be one of {sorted(PLATFORM_TAGS)}, got {args.arch!r}")

    output_path = Path(args.output) if args.output else DEFAULT_ZIP_PATH
    build_dir = BUILD_DIR / "demo_package"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    platform_tag = PLATFORM_TAGS[args.arch]
    print(
        f"Downloading Lambda-compatible wheels ({platform_tag}, "
        f"python {args.python_version}) for: {', '.join(PACKAGE_DEPENDENCIES)}"
    )
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--platform",
        platform_tag,
        "--target",
        str(build_dir),
        "--implementation",
        "cp",
        "--python-version",
        args.python_version,
        "--only-binary=:all:",
        "--no-compile",
        *PACKAGE_DEPENDENCIES,
    ]
    result = subprocess.run(pip_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployError(
            "pip install for Lambda-target wheels failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "pip: ok")

    print(f"Copying {PACKAGE_DIR} -> {build_dir / 'ringedingeding'}")
    _copy_source_tree(PACKAGE_DIR, build_dir / "ringedingeding")

    print(f"Copying {DEMO_DIR} -> {build_dir / 'demo'}")
    _copy_source_tree(DEMO_DIR, build_dir / "demo")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    _zip_directory(build_dir, output_path)

    size = output_path.stat().st_size
    print(f"Wrote {output_path} ({size / 1024 / 1024:.1f} MiB)")
    if size > UNZIPPED_LIMIT_BYTES:
        raise DeployError(
            f"package is {size} bytes, over Lambda's 250 MiB unzipped limit -- "
            "trim dependencies or split into a layer"
        )
    if size > DIRECT_UPLOAD_LIMIT_BYTES:
        print(
            "WARNING: package exceeds the 50 MiB direct-upload limit. `deploy` will need "
            "an S3 staging bucket for this zip; that path is not implemented in this script."
        )


def _copy_source_tree(src: Path, dst: Path) -> None:
    """Copy ``src`` into ``dst``, skipping ``__pycache__`` and ``.pyc`` files.

    Bytecode compiled on a different architecture/Python build than the Lambda
    execution environment can be incompatible — same AWS guidance roshambo's
    identical helper follows.
    """
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in ("__pycache__", ".pytest_cache", ".ruff_cache"):
            continue
        if item.is_dir():
            _copy_source_tree(item, dst / item.name)
        elif item.suffix != ".pyc":
            shutil.copy2(item, dst / item.name)


def _zip_directory(root: Path, output_path: Path) -> None:
    """Zip the contents of ``root`` at the archive root (Lambda requires this layout)."""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            zf.write(path, path.relative_to(root))


# ------------------------------------------------------------------------ create-role


LOG_GROUP_POLICY_NAME = "calle-demo-ringedingeding-logs"


def cmd_create_role(args: argparse.Namespace) -> None:
    boto3 = _import_boto3()
    iam = boto3.client("iam")

    trust_policy = json.loads((INFRA_DIR / "iam_trust_policy.json").read_text(encoding="utf-8"))

    role_name = args.role_name
    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for the calle-demo-ringedingeding Lambda "
            "(least privilege: writes to its own log group only — no Bedrock, no S3, "
            "no database access, because this function has no database).",
        )
        role_arn = role["Role"]["Arn"]
        print(f"created role {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]
        print(f"role {role_arn} already exists, reusing it")

    region = args.region
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    log_group_arn = (
        f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/{args.function_name}*"
    )
    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "OwnLogGroupOnly",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": log_group_arn,
            }
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=LOG_GROUP_POLICY_NAME,
        PolicyDocument=json.dumps(inline_policy),
    )
    print(f"attached inline policy {LOG_GROUP_POLICY_NAME} scoped to {log_group_arn}")
    print(role_arn)


# ---------------------------------------------------------------------------- deploy


def cmd_deploy(args: argparse.Namespace) -> None:
    env_vars = _demo_environment()
    boto3 = _import_boto3()

    zip_path = Path(args.zip) if args.zip else DEFAULT_ZIP_PATH
    if not zip_path.is_file():
        raise DeployError(f"{zip_path} does not exist -- run `package` first")
    zip_bytes = zip_path.read_bytes()
    if len(zip_bytes) > DIRECT_UPLOAD_LIMIT_BYTES:
        raise DeployError(
            f"{zip_path} is {len(zip_bytes)} bytes, over the 50 MiB direct-upload limit. "
            "Upload it to S3 yourself and pass --s3-bucket/--s3-key (not implemented here)."
        )

    lam = boto3.client("lambda", region_name=args.region)

    if args.role_arn:
        role_arn = args.role_arn
    else:
        iam = boto3.client("iam")
        role_arn = iam.get_role(RoleName=args.role_name)["Role"]["Arn"]

    try:
        response = lam.create_function(
            FunctionName=args.function_name,
            Runtime=args.runtime,
            Role=role_arn,
            Handler=HANDLER,
            Code={"ZipFile": zip_bytes},
            Timeout=args.timeout,
            MemorySize=args.memory,
            Environment={"Variables": env_vars},
            Architectures=[args.arch],
            Description="ringedingeding public dry-run demo (CALL-E hackathon). "
            "DEMO_MODE=1, no CALLE_* credential — cannot place a real call.",
        )
        print(f"created function {response['FunctionArn']}")
    except lam.exceptions.ResourceConflictException:
        print(f"function {args.function_name} already exists, updating it")
        lam.update_function_code(FunctionName=args.function_name, ZipFile=zip_bytes)
        _wait_for_update_settled(lam, args.function_name)
        lam.update_function_configuration(
            FunctionName=args.function_name,
            Role=role_arn,
            Handler=HANDLER,
            Timeout=args.timeout,
            MemorySize=args.memory,
            Environment={"Variables": env_vars},
        )
        _wait_for_update_settled(lam, args.function_name)
        print(f"updated function code and configuration for {args.function_name}")
    except lam.exceptions.InvalidParameterValueException as exc:
        if "role" in str(exc).lower() and not args.no_retry:
            print("role not yet assumable by Lambda (IAM propagation delay) -- retrying in 8s")
            time.sleep(8)
            args.no_retry = True
            cmd_deploy(args)
            return
        raise DeployError(str(exc)) from exc

    try:
        lam.put_function_concurrency(
            FunctionName=args.function_name,
            ReservedConcurrentExecutions=args.reserved_concurrency,
        )
        print(
            f"set reserved concurrency to {args.reserved_concurrency} "
            "(see module docstring, 'Cost guard' and 'Why a short timeout')"
        )
    except lam.exceptions.InvalidParameterValueException as exc:
        # AWS reserves a minimum of 10 unreserved concurrent executions across
        # the whole account. A low-usage account's own limit can make ANY
        # nonzero reservation here impossible without a support increase.
        print(
            f"WARNING: could not set reserved concurrency ({exc}). The account-wide "
            "Lambda ConcurrentExecutions limit still caps this function, just without "
            "a per-function reservation."
        )
    print(f"region: {args.region}")


def _wait_for_update_settled(lam: Any, function_name: str, *, attempts: int = 10) -> None:
    """Lambda serializes config/code updates; a second update while the first is
    `InProgress` is rejected."""
    for _ in range(attempts):
        state = lam.get_function_configuration(FunctionName=function_name)
        if state.get("LastUpdateStatus") != "InProgress":
            return
        time.sleep(2)


def _demo_environment() -> dict[str, str]:
    """The Lambda's entire environment. Exactly one variable, always.

    This is the deployment-side half of the live-path hardening described in
    the module docstring: no ``CALLE_*`` variable is read from the deploying
    shell or forwarded here, by construction — there is no code path in this
    function that could leak one in. ``DEMO_MODE=1`` is what
    ``CalleTransport.__init__`` checks before anything else.
    """
    return {"DEMO_MODE": "1"}


# -------------------------------------------------------------------------- enable-url


def cmd_enable_url(args: argparse.Namespace) -> None:
    boto3 = _import_boto3()
    lam = boto3.client("lambda", region_name=args.region)

    try:
        response = lam.create_function_url_config(
            FunctionName=args.function_name,
            AuthType="NONE",
        )
        function_url = response["FunctionUrl"]
        print(f"created Function URL: {function_url}")
    except lam.exceptions.ResourceConflictException:
        response = lam.get_function_url_config(FunctionName=args.function_name)
        function_url = response["FunctionUrl"]
        print(f"Function URL already exists: {function_url}")

    # AuthType=NONE alone still returns 403 to anonymous callers. Since
    # October 2025 AWS requires BOTH lambda:InvokeFunctionUrl AND
    # lambda:InvokeFunction on a new function URL — a URL with only the first
    # (the pre-October-2025 shape) returns a 403 with no other symptom.
    try:
        lam.add_permission(
            FunctionName=args.function_name,
            StatementId="FunctionURLAllowPublicAccess",
            Action="lambda:InvokeFunctionUrl",
            Principal="*",
            FunctionUrlAuthType="NONE",
        )
        print("added public invoke permission (FunctionURLAllowPublicAccess)")
    except lam.exceptions.ResourceConflictException:
        print("public invoke permission (InvokeFunctionUrl) already present")
    try:
        lam.add_permission(
            FunctionName=args.function_name,
            StatementId="FunctionURLInvokeAllowPublicAccess",
            Action="lambda:InvokeFunction",
            Principal="*",
            InvokedViaFunctionUrl=True,
        )
        print("added public invoke permission (FunctionURLInvokeAllowPublicAccess)")
    except lam.exceptions.ResourceConflictException:
        print("public invoke permission (InvokeFunction) already present")

    print(function_url)


# -------------------------------------------------------------------------- teardown


def cmd_teardown(args: argparse.Namespace) -> None:
    boto3 = _import_boto3()
    lam = boto3.client("lambda", region_name=args.region)
    iam = boto3.client("iam")
    logs = boto3.client("logs", region_name=args.region)

    try:
        lam.delete_function_url_config(FunctionName=args.function_name)
        print(f"deleted Function URL config for {args.function_name}")
    except lam.exceptions.ResourceNotFoundException:
        print(f"Function URL config for {args.function_name} already gone")

    try:
        lam.delete_function(FunctionName=args.function_name)
        print(f"deleted function {args.function_name}")
    except lam.exceptions.ResourceNotFoundException:
        print(f"function {args.function_name} already gone")

    if not args.keep_role:
        with contextlib.suppress(iam.exceptions.NoSuchEntityException):
            iam.delete_role_policy(RoleName=args.role_name, PolicyName=LOG_GROUP_POLICY_NAME)
        try:
            iam.delete_role(RoleName=args.role_name)
            print(f"deleted role {args.role_name}")
        except iam.exceptions.NoSuchEntityException:
            print(f"role {args.role_name} already gone")

    if not args.keep_logs:
        log_group = f"/aws/lambda/{args.function_name}"
        try:
            logs.delete_log_group(logGroupName=log_group)
            print(f"deleted log group {log_group}")
        except logs.exceptions.ResourceNotFoundException:
            print(f"log group {log_group} already gone")

    print(
        "teardown is best-effort, not a transactional stack deletion -- verify in the "
        "AWS console that no calle-demo-ringedingeding resources remain billable"
    )


# ----------------------------------------------------------------------------- shared


def _import_boto3() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise DeployError(
            "this subcommand needs boto3. Install with: pip install boto3"
        ) from exc
    return boto3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package, deploy, and tear down the calle-demo-ringedingeding "
        "Lambda Function URL."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_package = sub.add_parser("package", help="build the deployment zip")
    p_package.add_argument("--output", help=f"zip output path (default: {DEFAULT_ZIP_PATH})")
    p_package.add_argument("--python-version", default="3.12")
    p_package.add_argument("--arch", default="x86_64", choices=sorted(PLATFORM_TAGS))
    p_package.set_defaults(func=cmd_package)

    p_role = sub.add_parser("create-role", help="create/update the least-privilege execution role")
    p_role.add_argument("--role-name", default=ROLE_NAME)
    p_role.add_argument("--function-name", default=FUNCTION_NAME)
    p_role.add_argument("--region", default=DEFAULT_REGION)
    p_role.set_defaults(func=cmd_create_role)

    p_deploy = sub.add_parser("deploy", help="create/update the Lambda function")
    p_deploy.add_argument("--zip", help=f"path to the packaged zip (default: {DEFAULT_ZIP_PATH})")
    p_deploy.add_argument("--function-name", default=FUNCTION_NAME)
    p_deploy.add_argument("--role-name", default=ROLE_NAME, help="looked up if --role-arn is unset")
    p_deploy.add_argument("--role-arn", help="skip the IAM lookup, use this role ARN directly")
    p_deploy.add_argument("--region", default=DEFAULT_REGION)
    p_deploy.add_argument("--runtime", default="python3.12")
    p_deploy.add_argument("--arch", default="x86_64", choices=sorted(PLATFORM_TAGS))
    p_deploy.add_argument("--memory", type=int, default=512)
    p_deploy.add_argument("--timeout", type=int, default=15)
    p_deploy.add_argument("--reserved-concurrency", type=int, default=1)
    p_deploy.add_argument("--no-retry", action="store_true", help=argparse.SUPPRESS)
    p_deploy.set_defaults(func=cmd_deploy)

    p_url = sub.add_parser("enable-url", help="create the public Function URL")
    p_url.add_argument("--function-name", default=FUNCTION_NAME)
    p_url.add_argument("--region", default=DEFAULT_REGION)
    p_url.set_defaults(func=cmd_enable_url)

    p_teardown = sub.add_parser("teardown", help="best-effort delete of function/role/logs")
    p_teardown.add_argument("--function-name", default=FUNCTION_NAME)
    p_teardown.add_argument("--role-name", default=ROLE_NAME)
    p_teardown.add_argument("--region", default=DEFAULT_REGION)
    p_teardown.add_argument("--keep-role", action="store_true")
    p_teardown.add_argument("--keep-logs", action="store_true")
    p_teardown.set_defaults(func=cmd_teardown)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except DeployError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # boto3 ClientError etc: fail clearly, not with a raw traceback
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
