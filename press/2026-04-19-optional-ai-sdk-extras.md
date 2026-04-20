# Optional `ai` dependency extra adds OpenAI, Anthropic, tiktoken, and MCP support

**VISIONBLOX LLC × ZUUP INNOVATION LAB — FOR IMMEDIATE RELEASE**
April 19, 2026

The CAH Transformation Engine now exposes an optional `ai` dependency extra that installs the major LLM SDKs — **OpenAI**, **Anthropic**, **tiktoken**, and **MCP (Model Context Protocol)** — as an opt-in group. LLM-powered features become available without taxing the baseline deployment footprint.

## Operational Impact

- **CAH administrators and operators** running the core pipeline see no change: default installs remain CUDA/torch-free and resolve cleanly in constrained environments.
- Only teams building on the engine's LLM-assisted surfaces (e.g., extensions to the auto-citation engine, agent tooling, or narrative reporting) need to install the extras.

## Strategic Significance

- **Clean separation of concerns.** The baseline optimizer install remains lightweight and reproducible; LLM features are opt-in and explicit.
- **Positions the engine for agentic extensions.** Ships the MCP SDK alongside the LLM SDKs, signaling that agent-based workflows are part of the roadmap rather than an afterthought.
- **Lowers adoption friction.** A partner evaluating the engine in an air-gapped or cost-constrained environment doesn't have to carry the weight of LLM dependencies to run the optimizer.

## Technical Details

- **`pyproject.toml`** adds `[project.optional-dependencies.ai]`:
  ```toml
  ai = [
      "openai>=1.50.0",
      "anthropic>=0.40.0",
      "tiktoken>=0.8.0",
      "mcp>=1.0.0",
  ]
  ```
- **`requirements-ai.txt`** mirrors the extra for `pip -r` workflows; it includes `-r requirements.txt` so a single install gets both the core and the AI dependencies.
- **Install paths:**
  ```bash
  # Via PEP 621 extras
  pip install -e .[ai]

  # Via requirements file
  pip install -r requirements-ai.txt
  ```
- **Rationale documented in the commit message:** "Kept out of the core install so CUDA/torch-less environments still resolve cleanly."

## References

- PR: [#6](https://github.com/khaaliswooden-max/cah/pull/6) — `claude/clone-openai-repos-cNtXb`
- Key commit: `bab0929` (`feat(deps): add optional 'ai' extra for LLM SDKs`)
- Related files: `pyproject.toml`, `requirements-ai.txt`

---

**About VISIONBLOX × ZUUP.** The CAH Transformation Engine is a joint effort of VISIONBLOX LLC and ZUUP INNOVATION LAB to bring dual-objective optimization — a 5% operating-margin uplift alongside MBQIP/CAHSP quality benchmarks — to the 1,377 Critical Access Hospitals that make up the backbone of U.S. rural healthcare. Phase 1 empirical validation targets Washington (39 CAHs) and Montana (50 CAHs), leveraging WSHA and MHA benchmark networks. **Contact:** Aldrich K. Wooden — kwooden@visionblox.com
