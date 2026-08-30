# Troubleshooting

**"Missing required environment variable(s): GEMINI_API_KEY, GEMINI_MODEL"**
The app fails fast at startup rather than guessing a model name. Set both in
`.env` (see `.env.example`). `GEMINI_MODEL` must be a model ID valid for your
own API access — check the current Gemini API model list, this repository
does not assume one.

**`docker compose up` fails or hangs on `db-init`**
`db-init` runs the full ETL pipeline and needs the real Olist dataset present
in `data/raw/` on the host (see `data/raw/README.md`) — it fails immediately
with a clear `FileNotFoundError` naming the missing file if the dataset
isn't there, rather than silently producing empty data. Check
`docker compose logs db-init`.

**`docker compose up --build` fails to pull an image**
Some network environments (corporate proxies, sandboxed CI) block Docker
Hub image pulls outright — this shows as a `403 Forbidden` on the image
layer download itself, not a build error in this project's Dockerfiles. If
you see this, check your environment's outbound network/registry policy;
it isn't something in this repository to fix.

**"Could not connect to the database"**
Check `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` in `.env` match a
running PostgreSQL instance, and that the `commerce` schema has actually
been created and loaded (`python -m scripts.load_commerce`, or via
`db-init` in Docker Compose).

**Integration tests show "skipped", not "passed"**
`pytest -m integration` needs a real, reachable PostgreSQL server (checked
via `DB_HOST`/`DB_PORT`, defaulting to `localhost:5432`). A skip means no
database was reachable, not that the behaviour was verified — run
`pytest -m integration` specifically and confirm it reports passed, not
skipped, before trusting that these behaviours were actually exercised.

**Sidebar shows only "Assistant" and "Customers"**
This is intentional. The other nav labels (Revenue, Sales performance,
Products, History) were removed because they were static text with no
underlying page — a false affordance, not a missing feature you need to
work around.

**Terraform bootstrap fails with `s3:CreateBucket` `AccessDenied`**
`terraform apply` reached AWS but failed with a 403 because the IAM user did
not have `s3:CreateBucket`. Authentication was working; the user just did not
have permission to create the state bucket. `terraform state list` was empty,
so the failed apply had not created or recorded any partial resources.

The saved plan still showed only the four intended S3 resources, which ruled
out the Terraform configuration and S3-native locking as the cause. I created
a customer-managed policy scoped to the state bucket and attached it through
the `devops` IAM group. It allows Terraform to create and configure the bucket
and use the state and lock files without giving the user broad administrator or
full S3 access.

After updating IAM, a new plan showed `4 to add, 0 to change, 0 to destroy`.
The apply created all four resources, and the next plan reported `No changes`.
The lesson is that valid AWS credentials prove who the user is, but IAM policy
still decides what that user is allowed to do.
