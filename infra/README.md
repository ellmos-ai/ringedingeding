# Deploying the public dry-run demo

`deploy_demo_lambda.py` packages, deploys, and tears down `calle-demo-ringedingeding` —
an AWS Lambda Function URL running the same web interface `python -m ringedingeding --web`
runs locally, behind the `demo/lambda_entry.py` Mangum adapter. See that script's own
module docstring for the full detail (live-path hardening, why the timeout is short, cost
guard) — this file is only the quickstart.

## What it is, and is not

It is a read-mostly showcase: a Lambda cold start seeds one example project from the
`team-retro` fixture (English, four participants, scripted answers — see
`ringedingeding/fixtures/team-retro.json`) so a judge sees something operable the moment
the page loads, using the exact offline replay path the `demo` CLI command already uses.

It is **not** capable of placing a real call. `DEMO_MODE=1` is set in the Lambda's own
environment and no `CALLE_API_KEY` is ever configured there — the code-level guard in
`ringedingeding/transports/calle.py::CalleTransport.__init__` checks `DEMO_MODE` before
anything else and refuses unconditionally. Proven in `tests/test_live_guard.py`.

It is **ephemeral**: state resets whenever AWS recycles the execution environment. This is
a demo link, not a hosted product.

## Prerequisites

* An AWS profile with the permissions in
  `.../.HACKATHONS/2026-call-e/AWS-DEMO-SETUP.md`'s policy JSON (Lambda + IAM, scoped to
  `calle-demo-*` resources only), configured as `[calle-demo-deploy]` in
  `~/.aws/credentials` (or export `AWS_PROFILE=calle-demo-deploy` before running these
  commands).
* `pip install boto3` in whatever environment runs this script (not a runtime dependency
  of the deployed function itself — see `PACKAGE_DEPENDENCIES` in the script).

## Quickstart

```bash
export AWS_PROFILE=calle-demo-deploy   # or --profile via AWS_PROFILE in your shell config

python infra/deploy_demo_lambda.py package
python infra/deploy_demo_lambda.py create-role
python infra/deploy_demo_lambda.py deploy
python infra/deploy_demo_lambda.py enable-url
```

`enable-url` prints the public Function URL — that is what goes into the README's
"Live demo" line and the DevPost submission.

## Tearing it down

```bash
python infra/deploy_demo_lambda.py teardown
```

Best-effort, not a transactional stack deletion (matches the roshambo precedent this
script follows) — verify in the AWS console afterward that nothing `calle-demo-*` is
still billable.
