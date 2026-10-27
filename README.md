# ai-engineering_r_d
Court Judgment Data Extraction (LLM → JSON)

This repository provides a modular pipeline for extracting structured data from Polish court judgments (PDF format) into JSON conforming to a Pydantic schema. It evaluates and compares different LLM models, prompt versions, and sampling parameters against a manually labeled golden set, measuring field-level accuracy, correctness rates, latency (p50/p95), and cost per 1,000 documents.

Quick Start

Prerequisites

Python 3.11+

Installation & Execution

python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # Add your OPENROUTER_API_KEY
python main.py                                        # Or run via: make run


Executing python main.py runs the default experiment defined in experiments/default.json (testing remote and local models × prompt versions v1 and v2 × two temperature settings) against the golden set. Upon completion, it prints a comparison table and saves it to results/comparison.md. Configurations that cannot be executed due to missing API keys, Ollama services, or PyTorch dependencies are skipped with a warning.

To run a quick test on 2 files: make quick (equivalent to python main.py experiment --file quick).

Data Structure

data/
├── *.pdf             Source documents (txt files also supported)
└── goldenset/
    └── <name>.json   Ground truth JSON for data/<name>.pdf (structured as {"document": {...}})


The golden set maps directly to files located in data/goldenset/, matched by filename (e.g., ruling7.json corresponds to ruling7.pdf).

Supported Models

Each model and sampling setup is defined as a configuration file in configs/, implementing a unified interface via BaseLLM.generate:

Provider

Description

Requirements

openrouter

Remote model via API with structured output support (json_schema; falls back automatically to json_object if unsupported)

OPENROUTER_API_KEY configured in .env

ollama

Local model via Ollama (includes structured output support)

Running service (ollama serve) and model pulled (ollama pull qwen3:4b)

local

Local model via Hugging Face transformers (defaults to Qwen3-0.6B)

pip install torch transformers accelerate

Configuration Parameters

Key configuration parameters include: temperature, top_p, top_k, max_tokens, timeout_s, max_retries, enable_thinking, structured_output, num_ctx, and extra_body (refer to src/llm/config.py).

To add a new variant: duplicate an existing config file in configs/, adjust the parameters, and reference it inside an experiment file in experiments/.

To select a remote model, update model_name in your configs/openrouter_*.json file (check available slugs on Openrouter Models; ensure the chosen model supports structured_outputs if required).

CLI Commands

python main.py                                            # Run default experiment and generate table
python main.py experiment --file with_ollama              # Run a specific experiment from experiments/*.json
python main.py experiment --only-provider openrouter      # Run experiments restricted to remote models
python main.py run --config openrouter_t0 --prompt v2     # Execute a single pipeline run
python main.py run --config openrouter_t0 --scope all     # Process all documents in data/, ignoring golden set scope
python main.py run ... --limit 3 --skip-existing --rules  # Process 3 files; resume incomplete runs; apply regex rules for docket numbers and dates
python main.py compare                                    # Generate summary table from existing results
python main.py evaluate --run openrouter_t0__v2           # Generate detailed evaluation report for a single run (_report.txt)
python main.py errors --run openrouter_t0__v2 --top 10    # List top errors for debugging (_errors.md)
make test                                                 # Run test suite (offline, no keys required)


Pre-configured experiments in experiments/: default, with_ollama, quick, rules_ablation (evaluates performance with and without regex rule injections). Interrupted runs can be resumed by passing the --skip-existing flag.

Architecture & Workflow

Extraction (src/extraction/extractor.py): Extracts text from the beginning of the PDF (up to 8,000 characters), combines it with a prompt from prompts/, queries the model, and validates the output against the Pydantic schema (src/extraction/schemas.py).

Error Recovery: If validation fails, the pipeline makes a single correction attempt by feeding the model's previous output and validation error back into a follow-up prompt. If it fails again, the status is marked as failed (the batch run continues uninterrupted). Network timeouts and retries are managed by the client configuration.

Logging: Every output result (results/<run_name>/<document>.json) logs the model name, provider, prompt version, sampling parameters, attempt count, latency, token usage, and cost. Run metadata is stored in _run_meta.json.

Evaluation (src/evaluation/): Critical fields (document_type, language, decision_date, docket_number) are evaluated via exact matching after normalization. Other fields are assessed using string similarity (threshold: 0.8). A failed status counts as an error for all fields.

Metrics Reference

Metric

Definition

Format Valid

Percentage of documents with status ok: response passed schema validation and content inspection (non-empty, free of prompt boilerplate templates) within at most 1 correction attempt. Does not measure value accuracy.

Without Correction

Percentage of documents successfully validated on the first attempt without requiring correction prompts.

Filled Fields

Average percentage of populated core fields (9 main fields); figures in parentheses indicate documents containing boilerplate templates instead of actual values.

Critical Fields OK

Percentage of golden set documents where all critical fields are evaluated as correct.

Avg JSON Score

Average score across all fields and golden set documents.

Latency (p50 / p95)

Percentiles of processing time per document (summed across attempts), calculated via linear interpolation.

Cost / 1000 Docs

Average cost per document multiplied by 1,000, based on OpenRouter usage reporting (0 for local models).

Statistics & Logs Directory

After every run (including those interrupted via Ctrl+C), results are saved under results/<run_name>/:

File

Contents

_run_summary.txt

Human-readable summary: execution time, counts for ok / failed / skipped / unprocessed files, token usage, cost, slowest files, and error lists with reasons.

_run_meta.json

Machine-readable JSON summary containing execution duration and individual file statuses (per_file).

_report.txt

Detailed golden set accuracy report (automatically generated post-run).

<document>.json

Individual extraction result along with model metadata, prompt version, sampling parameters, attempts, latency, tokens, and cost.

Post-experiment aggregates are written to results/_experiment_<name>.txt (detailing executed runs, durations, and skipped configurations with reasons such as missing API keys) and results/comparison.md (comparative summary table).

Manual reporting commands:

python main.py compare

python main.py evaluate --run <run_name>

python main.py errors --run <run_name>

Testing

Running make test (or python -m pytest -q) tests the codebase logic rather than model quality. It utilizes mock models and local test servers simulating OpenRouter and Ollama APIs, meaning it operates entirely offline without external keys or real data. Note that this does not replace full experimentation; model accuracy metrics are measured via python main.py and python main.py compare.

Prompt Engineering

Files: prompts/v1.py (baseline), prompts/v2.py (includes field rules, nested schemas, and few-shot examples). Historical notes and rationale for changes are tracked in prompts/CHANGELOG.md.

Adding a Version: Create a new file prompts/v3.py defining variables SYSTEM_PROMPT, RULING_EXTRACTION_TEMPLATE (optionally SUMMARY), and add a corresponding changelog entry.

Constraint: Never include documents or excerpts from the golden set inside prompts to prevent data leakage during evaluation.

Repository Structure

main.py                 CLI entry point
configs/                Model and sampling configurations
experiments/            Experiment definitions (configurations × prompts × rules)
prompts/                Prompt versions and CHANGELOG.md
data/                   Source documents and golden set data
results/                Run outputs, comparison tables (.md/.csv)
examples/               Simulated sample reports (not actual model outputs)
src/
├── llm/                API clients (openrouter, ollama, local) and shared interface
├── extraction/         Extractor, Pydantic schema, JSON Schema, regex rules
├── pipeline/           File aggregation, batch runner, experiment engine
├── evaluation/         Evaluator, metrics, comparison table generator, error analysis
└── cli.py              Command Line Interface parser and handlers
tests/                  Pytest test suites


Notes & Best Practices

API Keys: Keep sensitive keys in .env (excluded from version control via .gitignore; only .env.example is committed).

Ollama Context Window: Default context windows can be insufficient for lengthy legal documents; configurations explicitly set num_ctx: 8192.

Golden Set Scope: The golden set contains only flat fields. Nested fields (participants, related_case, operative_part) are extracted by models but excluded from automated evaluation scoring.

Sample Size Considerations: With a small golden set (e.g., 10 documents), a single document accounts for 10 percentage points of variance; variations within this range should be interpreted as statistical noise.
