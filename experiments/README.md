# experiments/

Third-party repositories pulled in as git submodules for local experimentation.
These are **not** part of the cah production codebase, are not exercised by
cah CI, and carry their own upstream licenses.

## Layout

```
experiments/
├── alexwg/    # github.com/alexwg (Alexander Wissner-Gross)
└── karpathy/  # github.com/karpathy (Andrej Karpathy)
```

## Usage

Clone cah with submodules:

```bash
git clone --recursive <cah-url>
# or for an existing clone:
git submodule update --init --recursive
```

Update every submodule to its upstream HEAD:

```bash
git submodule update --remote
```

Deepen a shallow submodule (submodules are cloned with `--depth=1`):

```bash
cd experiments/karpathy/nanoGPT
git fetch --unshallow
```

## Adding more

The ingestion is driven by `scripts/add_founder_submodules.sh`, which is
idempotent — edit the repo lists at the top of the script and re-run.

## Licensing

Each submodule retains its upstream license. Nothing under `experiments/` is
relicensed by cah's repo-level LICENSE.
