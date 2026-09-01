# CI artifact promotion

The CI pipeline has two different trust levels.

Pull requests and all normal test jobs receive only read access to repository
contents. They build and scan an image locally but cannot request a GitHub OIDC
token or authenticate to AWS.

After a successful push to `main`, the build job exports the exact image that
passed Trivy. A separate publishing job downloads that image, assumes the
dedicated CI publishing role through GitHub OIDC, and pushes the immutable
`sha-<full-commit>` tag to ECR. It records the ECR registry digest and canonical
`repository@sha256:...` URI for CD. CD must consume that digest and must never
rebuild the image.

## AWS trust bootstrap

The global Terraform stack creates:

- the account-level GitHub Actions OIDC provider;
- a CI publishing role restricted to one exact GitHub OIDC subject;
- an inline policy restricted to publishing and verifying images in the
  application ECR repository.

Copy `terraform/global/terraform.tfvars.example` to an uncommitted tfvars file
and replace the placeholder with the exact subject emitted for this repository.
Do not use wildcards. GitHub repositories using immutable OIDC subject claims
must use the owner and repository ID form documented in the example.

If the AWS account already has the GitHub Actions OIDC provider, import it into
the global state rather than attempting to create a duplicate.

After reviewing and applying the global Terraform plan, configure these GitHub
repository variables from the Terraform outputs and AWS account details:

- `AWS_CI_PUBLISH_ROLE_ARN`
- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `AWS_ECR_REPOSITORY_NAME`

These are identifiers, not application secrets. Do not give the CI publishing
role ECS, IAM administration, Terraform deployment, database, or Secrets
Manager permissions.

## Dependency lock updates

The `.in` files contain direct dependency intent. The generated `.txt` files
pin the entire transitive graph and include artifact hashes. Runtime Docker
builds and CI use `--require-hashes`.

Regenerate all three locks in a controlled Python 3.12 environment with
`pip-tools==7.5.2`, then verify `requirements-dev.txt` resolves under both
Python 3.11 and Python 3.12 before committing an update. The shared
`numpy<2.5` constraint is required while Python 3.11 remains supported.
