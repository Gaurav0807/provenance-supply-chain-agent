# Provenance: supply chain data agent

Ask a question in plain English about supply chain data. The agent answers from two sources:

- **Structured data** (Athena tables): orders, shipments, inventory, factories.
- **Documents** (a Bedrock Knowledge Base): contracts, delay notices, quality reports, stock notes, SLAs.

Every answer shows its sources: the SQL that ran, or the document it came from.

The data is synthetic and the brand, "Stride Footwear", is fictional.

> **Status:** the data, RAG pipeline, agent and evals are built. Role-based access control is **not enforced yet**. Every user currently sees all data. See [Known limitations](#known-limitations).

---

## Architecture

The simple overview is on the first page of [`docs/architecture.drawio`](docs/architecture.drawio). Open it at [app.diagrams.net](https://app.diagrams.net) (File → Open). The other pages show each flow in more detail.

```
Data in S3 ──► Athena tables ───────────┐
                                        ├──► Agent (LangGraph + Claude) ──► Answer + sources
Documents in S3 ──► Knowledge Base ─────┘
                    (SNS → SQS → Lambda → Titan embeddings → OpenSearch)

CI: test ──► evals (100% required) ──► Terraform plan
CD: (main only, after CI passes and approval) ──► Terraform apply ──► upload data and documents
```

### How a question is answered

1. `agent/run.py` (or `agent/graph.py`) starts a LangGraph state graph.
2. The **agent node** sends the question, plus the ontology, to Claude on Bedrock.
3. Claude either answers, or asks for a tool:
   - `run_sql`: `agent/sql_guard.py` allows one read-only `SELECT`, then `agent/athena.py` runs it.
   - `search_documents`: `agent/rag.py` calls the Knowledge Base `retrieve` API.
4. The **tools node** adds the result to the conversation, and the agent loops (max 8 steps).
5. When Claude answers without a tool call, the graph ends and returns the answer and the trace.

The ontology (`ontology/provenance.ttl`, RDF) defines business terms and their rules. For example, "delayed" means `delivered_date > promised_date`, and "at-risk factory" means 3 or more delayed orders.

---

## Repository layout

```
agent/            The agent: graph, tools, SQL guard, document search, ontology lookup
data/             Data and document generators (synthetic, seeded, with planted facts)
evals/            Golden set builder, GEval judge, evaluation runner, SageMaker tracking
infra/            Terraform, one file per component
lambda/ingest/    Lambda that starts a Knowledge Base sync when documents arrive
ontology/         The RDF ontology
scripts/          Vector index setup, architecture diagram builder
tests/            Offline tests (no AWS needed)
.github/workflows CI (ci.yml) and CD (cd.yml)
docs/             Architecture diagram
```

---

## Prerequisites

- Python 3.11 or newer
- AWS CLI v2 and Terraform 1.6 or newer
- An AWS account with Bedrock access to the Claude models (see [Troubleshooting](#troubleshooting))
- A payment method on the AWS account that can pay for Marketplace models (see Troubleshooting)

---

## Setup (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt        # tests and lint
pip install -r requirements-evals.txt      # only if you run the evals
```

Set these in your shell. They are not committed:

| Variable | Example | Used for |
|---|---|---|
| `AWS_PROFILE` | `provenance-new` | Local AWS login |
| `AWS_REGION` | `us-east-1` | Region for all services |
| `KNOWLEDGE_BASE_ID` | `OMB4H2KROE` | Document search (from `terraform output knowledge_base_id`) |
| `LLM_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Agent model (default shown) |
| `JUDGE_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Eval judge model (default shown) |
| `EVAL_BASELINE` | `1.0` | Pass bar for the evals (default `0.7`) |

---

## Running it, in order

### 1. Create the data (once, or after changing the generator)

```bash
python -m data.generate                                                 # Parquet tables
python -m data.generate --upload provenance-data-4102a6 --profile ""    # upload to S3
```

`data/out/planted_facts.json` lists the known answers, such as the late-shipment counts and the low-stock SKUs.

### 2. Create the infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply
cd ..
```

This creates the Knowledge Base, the OpenSearch Serverless collection and its vector index, the SNS topic, SQS queues, the ingest Lambda, and the S3 notification.

The OpenSearch Serverless collection has a minimum hourly cost. Run `terraform destroy` when you stop testing.

### 3. Load the documents

```bash
python -m data.generate_docs
aws s3 sync data/documents s3://provenance-data-4102a6/documents/ --delete
```

Each upload starts the pipeline: S3 → SNS → SQS → Lambda → Knowledge Base sync. Check the sync in the console under **Bedrock → Knowledge bases → provenance-docs → Data source sync history**. Wait for **Complete**.

### 4. Ask the agent

```bash
python -m agent.run "Which factories are at risk?"                            # uses Athena
python -m agent.run "What late-delivery penalty does Surabaya Foam have?"    # uses documents
```

### 5. Run the evals

```bash
python -m evals.build_golden    # writes evals/golden_dataset.csv (39 cases)
python -m evals.run_evals       # grades each answer, logs the run to SageMaker
```

The run prints a line per case, a summary by metric and category, and whether it passed. It writes `evals/results.json`.

### Tests (no AWS needed)

```bash
ruff check agent evals tests data lambda scripts
python -m pytest tests -q
```

---

## How the evals work

- **Golden set:** `evals/make_cases.py` computes the expected answer for each question from the same generated data that is in S3. `build_golden.py` writes the cases to `evals/golden_dataset.csv`.
- **Grading:** each answer is graded by two [DeepEval](https://github.com/confident-ai/deepeval) G-Eval metrics, using Claude Haiku as the judge (`evals/judge.py`):
  - **Correctness:** the same facts, numbers and conclusion as the expected answer.
  - **Source citation:** document-based answers name their document.
- **Gate:** every metric must reach `EVAL_BASELINE`. Otherwise the run exits with code 1, and CI fails.
- **History:** each run is logged to SageMaker Experiments (`provenance-agent-evals`), with its parameters and metrics. It's also saved as the `eval-results` artifact in GitHub Actions.

---

## CI and CD

**CI** (`.github/workflows/ci.yml`), on every push and pull request:

1. `test`: ruff, pytest, secret scan.
2. `evals`: builds the golden set and runs the evals. Fails below 100%.
3. `terraform-plan`: shows infrastructure changes, after the evals pass.

**CD** (`.github/workflows/cd.yml`), only when CI succeeds on `main`, and after approval in the `production` environment:

1. `deploy-infra`: `terraform apply`, which also creates the vector index.
2. `deploy-data`: generates the documents and data, then uploads them to S3.

If any CI job fails, CD does not run.

### GitHub settings

| Type | Name | Value |
|---|---|---|
| Secret | `AWS_ROLE_ARN` | `arn:aws:iam::547619825898:role/provenance-github-deploy` |
| Variable | `KNOWLEDGE_BASE_ID` | `OMB4H2KROE` |
| Variable | `LLM_MODEL_ID` | Optional. Model for the agent in CI |
| Variable | `JUDGE_MODEL_ID` | Optional. Model for the judge in CI |
| Environment | `production` | Add a required reviewer |

GitHub logs in to AWS with OIDC, so no AWS access keys are stored. The role's trust policy allows only this repository on `main`.

---

## Security

- **Secrets:** no keys in the code. `.env` is git-ignored. Local work uses an AWS profile.
- **Access:** the GitHub role has `AdministratorAccess` for now, so it's broader than it needs to be. Narrow it before real use.
- **Data access:** the agent runs with one set of AWS credentials, so every user sees all data. Role-based access is the next step: a role per user, Lake Formation column rules on Athena, and a document filter.

---

## Costs

| Service | Cost |
|---|---|
| OpenSearch Serverless (vector index) | Hourly minimum while the collection exists. **Largest cost.** |
| Bedrock (Claude, Titan, Knowledge Base) | Per token and per request |
| Athena | Per data scanned (small here) |
| S3, SQS, SNS, Lambda | Negligible |
| SageMaker Experiments | Storage only; no compute |

To stop costs, run `terraform destroy` in `infra/` when you're not testing.

---

## Troubleshooting

| Error | Cause and fix |
|---|---|
| `AccessDeniedException ... INVALID_PAYMENT_INSTRUMENT` | The Claude models are sold through AWS Marketplace, which needs an international credit or debit card as the default payment method. UPI can't be used. |
| `ResourceNotFoundException ... use case details` | Submit the Anthropic use-case form in the Bedrock console (once per account). |
| `403 Forbidden` when creating the vector index | The OpenSearch data access policy must list your user, and the request must send the body hash. Both are set in `infra/vector_store.tf` and `scripts/create_vector_index.py`. |
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` (in CI) | The role's trust policy doesn't match the token subject. GitHub uses `repo:<owner>@<owner-id>/<repo>@<repo-id>:...`. |
| `ThrottlingException` | Too many model calls per minute. Retries are built in. Request a quota increase, or switch to a smaller model. |
| `KNOWLEDGE_BASE_ID is not set` | Export the variable in the same terminal. |

---

## Known limitations

- **No role-based access control yet.** Sensitive columns are labelled in the ontology, but nothing enforces them.
- **No public API.** The agent runs from the command line. Next step: wrap `agent.graph.ask` in an API.
- **Document citations name the file, not the page.** Knowledge Base chunks don't carry page numbers.
- **Deleted documents are not removed from the index.** The Lambda only handles uploads.
- **The evals use synthetic answers.** The golden set is built from the generated data, so it checks the pipeline, not real business accuracy.

---

## Roadmap

1. Role-based access: user roles, Lake Formation column rules on Athena, and document filters.
2. A public API (API Gateway with a container or Lambda) with login.
3. Neptune as the ontology store, once the agent runs inside AWS.
4. Deletion handling for the document index.
