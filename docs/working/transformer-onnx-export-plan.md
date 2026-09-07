# Transformer ONNX Export Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the transformer training flow export a valid ONNX artifact reliably, without alternating between `aten::view` and `aten::reshape` failures.

**Architecture:** Keep the training model intact, but move the ONNX export path into a dedicated export surface that can be validated in isolation. The export surface should build the transformer, freeze inference-only parameters, and use the most compatible ONNX export API available in the installed libtorch headers. The plan deliberately separates export compatibility from model behavior so we can make one change at a time and prove the exporter produces a non-empty ONNX file before re-enabling the full compose flow.

**Tech Stack:** C++20, libtorch / TorchScript ONNX export APIs, CMake, podman-compose, GitHub Actions.

---

### Task 1: Extract a dedicated transformer export entry point

**Files:**
- Create: `include/ml/TransformerOnnxExport.hpp`
- Create: `src/ml/TransformerOnnxExport.cpp`
- Modify: `src/ml/ModelTrainer.cpp`
- Modify: `CMakeLists.txt`

- [ ] **Step 1: Add a focused export API**

Create a small header that declares one function:

```cpp
#pragma once

#include <filesystem>

namespace trade::ml {
void export_transformer_to_onnx(const std::filesystem::path &output_path,
                                int64_t input_features);
}
```

- [ ] **Step 2: Move the current export body out of `ModelTrainer.cpp`**

Relocate the existing export logic from the anonymous helper in `src/ml/ModelTrainer.cpp` into `src/ml/TransformerOnnxExport.cpp` so the exporter can be tested without running the full training pipeline.

- [ ] **Step 3: Wire the new export module into the build**

Add `src/ml/TransformerOnnxExport.cpp` to the `trading_bot_cpp` source list in `CMakeLists.txt`, and include `include/ml/TransformerOnnxExport.hpp` from `src/ml/ModelTrainer.cpp`.

- [ ] **Step 4: Verify compilation surface**

Run the smallest non-runtime check available for the export translation unit, for example:

```bash
cmake -S . -B build
```

Expected: configure succeeds at least through the point where the project can see the new header and source file wiring.

---

### Task 2: Replace the legacy tracer path with a module-first export path

**Files:**
- Modify: `src/ml/TransformerOnnxExport.cpp`
- Modify: `src/ml/TransformerModel.cpp`

- [ ] **Step 1: Keep the transformer inference graph in one place**

Preserve the `StockTransformer` implementation, but stop depending on a lambda-captured trace of `model->forward(...)` as the export boundary.

- [ ] **Step 2: Build the export from a dedicated inference module**

Use a dedicated module or export wrapper for ONNX generation so the exporter sees a stable `torch::nn::Module` boundary rather than an ad hoc lambda graph. The wrapper should:

```cpp
// Conceptual shape only:
// - construct StockTransformer
// - call eval()
// - freeze parameters for inference export
// - run the export API directly on the module boundary
```

- [ ] **Step 3: Prefer the newest ONNX API exposed by local headers**

Inspect the installed libtorch headers and choose the export API that is actually available in this environment. If a direct `torch::onnx` C++ export path is present, use it. If not, keep the TorchScript route but export from the module boundary instead of from a custom lambda trace.

- [ ] **Step 4: Keep export-only tensor constants out of the autograd graph**

Retain the current parameter-freezing behavior before export so the exporter does not try to inline tensors that still require gradients.

- [ ] **Step 5: Re-run the exporter on a fixed dummy input**

Use the existing `(1, 60, input_features)` sample input as the export smoke input and ensure the exporter finishes without throwing.

---

### Task 3: Add a real ONNX export smoke test

**Files:**
- Create: `src/tests/test_transformer_onnx_export.cpp`
- Modify: `CMakeLists.txt`

- [ ] **Step 1: Add a tiny smoke executable**

Create a test that calls `trade::ml::export_transformer_to_onnx(...)` with a temporary output path and a known positive feature count.

```cpp
int main() {
  std::filesystem::path out = std::filesystem::temp_directory_path() / "transformer_smoke.onnx";
  trade::ml::export_transformer_to_onnx(out, 10);
  if (!std::filesystem::exists(out) || std::filesystem::file_size(out) == 0) {
    return 1;
  }
  std::filesystem::remove(out);
  return 0;
}
```

- [ ] **Step 2: Wire the smoke test into CMake**

Add a `test_transformer_onnx_export` executable that links the minimal set of sources needed to exercise the exporter.

- [ ] **Step 3: Keep the test focused**

Do not make the smoke test depend on the whole app stack. It should validate only that ONNX export returns a non-empty artifact.

- [ ] **Step 4: Run the smoke test in the most authoritative environment available**

Prefer the containerized backend path or the repo's standard CI run over local-only assumptions.

---

### Task 4: Verify the full compose flow and remote CI

**Files:**
- No code changes expected unless the smoke test exposes a second export issue.

- [ ] **Step 1: Rebuild the backend image**

Run the compose path that triggered the failure:

```bash
TAG=dev podman-compose up --no-build
```

Expected: the backend completes model training and ONNX export without the previous `view`/`reshape` error.

- [ ] **Step 2: Check service health**

Confirm backend logs show the training progressing past export and that frontend/backend healthchecks stay healthy.

- [ ] **Step 3: Push the fix and verify GitHub Actions**

After the compose smoke passes, commit the change, push `dev`, and confirm the `Docker Build Validation` workflow completes successfully on GitHub Actions.

- [ ] **Step 4: Capture residual risk**

If export still fails, record the exact failing operator and decide whether it is:

```text
1. a model-op compatibility issue,
2. a TorchScript exporter limitation, or
3. an API mismatch in the installed libtorch build.
```

---

### Recommended Approach

Use the isolated export helper in Task 1, backed by the smoke test in Task 3, while keeping the model forward path ONNX-friendly. The cleanest fix is to eliminate the unsupported explicit `view`/`reshape` pattern from the transformer blocks, export from a dedicated helper, and then prove success with a concrete pass/fail artifact instead of bouncing between unsupported shape ops.

### What Would Count As Done

- `export_transformer_to_onnx(...)` completes without throwing.
- The exported `.onnx` file exists and is non-empty.
- `TAG=dev podman-compose up --no-build` reaches healthy backend startup.
- The pushed branch passes the remote `Docker Build Validation` GitHub Actions workflow.
