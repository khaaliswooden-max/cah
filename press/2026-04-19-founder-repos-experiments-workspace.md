# Founder-repo experiments workspace (alexwg + karpathy) added as pinned submodules

**VISIONBLOX LLC × ZUUP INNOVATION LAB — FOR IMMEDIATE RELEASE**
April 19, 2026

The CAH Transformation Engine repository now includes an `experiments/` workspace that mounts every public repository from GitHub users **alexwg** (1) and **karpathy** (63) as shallow, SHA-pinned Git submodules — giving the project a reproducible, version-pinned research adjacency without inflating the superproject.

## Operational Impact

- Not directly operator-facing. No CAH workflow, pipeline step, or CAHSP scoring behavior is affected by this release.
- Delivery teams running the core pipeline can ignore `experiments/` entirely; nothing under that path is imported by the optimizer, scoring, or data-acquisition modules.

## Strategic Significance

- **Research adjacency made reproducible.** Instead of bookmarking external repos or copying code, the engine has a first-class, versioned neighborhood of foundational ML and systems repositories to draw from — aligned with the VISIONBLOX × ZUUP thesis that rural-healthcare optimization benefits from frontier AI patterns.
- **Provenance-by-default.** Every referenced repo is pinned by commit SHA, so any experiment published out of this workspace can be reproduced months later without drift.
- **Investor signal.** Demonstrates that the engine is being built with explicit awareness of the broader AI / research ecosystem rather than in isolation.

## Technical Details

- **Driver:** `scripts/add_founder_submodules.sh` — idempotent, skips already-added paths, tolerates individual clone failures.
- **Layout:** `experiments/<owner>/<repo>` (e.g., `experiments/karpathy/nanochat`, `experiments/alexwg/cpython`).
- **Clone discipline:** `git clone --depth=1`, pinned by commit SHA. Full history for any single submodule is recoverable on demand via `git fetch --unshallow` inside that submodule directory.
- **Ingestion scope:** 1 public repo from `github.com/alexwg`, 63 from `github.com/karpathy`, enumerated in `.gitmodules`.
- **Superproject footprint:** unchanged — submodule pointers only; the superproject is not carrying blob history.

### Quick start

```bash
# Initialize the workspace locally (shallow by default)
git submodule update --init --recursive

# Re-run the ingestion script (safe to re-run)
bash scripts/add_founder_submodules.sh
```

## References

- PR: [#5](https://github.com/khaaliswooden-max/cah/pull/5) — `claude/add-founder-repos-G8xjC`
- Key commit: `4258d80` (`feat(experiments): add karpathy + alexwg repos as submodules`)
- Related files: `scripts/add_founder_submodules.sh`, `.gitmodules`, `experiments/`

---

**About VISIONBLOX × ZUUP.** The CAH Transformation Engine is a joint effort of VISIONBLOX LLC and ZUUP INNOVATION LAB to bring dual-objective optimization — a 5% operating-margin uplift alongside MBQIP/CAHSP quality benchmarks — to the 1,377 Critical Access Hospitals that make up the backbone of U.S. rural healthcare. Phase 1 empirical validation targets Washington (39 CAHs) and Montana (50 CAHs), leveraging WSHA and MHA benchmark networks. **Contact:** Aldrich K. Wooden — kwooden@visionblox.com
