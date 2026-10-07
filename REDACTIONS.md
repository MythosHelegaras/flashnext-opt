# Redactions and omissions

Everything in this repo is the unedited working folder, except:

- `logs/v4/preflight.txt`: two lines of the GPU/process listing removed (an unrelated desktop app's
  process line with a per-install device ID, and an agent's temp-file path). No measurement data was in them.
- Not published: `__pycache__/`, `*.pid`, `build-backups/` (a compiled `llama-server` binary and a
  `CMakeCache.txt` with the machine's hostname), `corpus/rejected-v2/` (corpus rejected during v2).
- `corpus/full128.txt`, `corpus/full256.txt`, `corpus/p32k.txt` are not published unless noted below:
  they are preprocessed compiler output that includes NVIDIA CUDA toolkit headers, which I do not have
  the right to redistribute. `harness.py:build_corpus()` regenerates them from a llama.cpp build tree;
  `corpus/SHA256SUMS` lists the hashes of the files used in every run.
