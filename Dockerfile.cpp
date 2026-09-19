# --- STAGE 1: Build ---
FROM ubuntu:22.04 AS builder

# mono-complete (added for NuGet-based vcpkg binary caching below) pulls in
# packages that can otherwise prompt for debconf input during apt-get.
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies with retry logic for transient mirror/network failures
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && \
      apt-get install -y --no-install-recommends --fix-missing \
        ca-certificates curl cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev \
        autoconf automake libtool libltdl-dev linux-libc-dev gfortran pkg-config gperf autoconf-archive python3-venv python3-dev \
        unzip zip mono-complete \
        libx11-dev libxext-dev libxrender-dev libxcb1-dev libxau-dev libxdmcp-dev libxft-dev \
        libdbus-1-dev libglib2.0-dev libxi-dev libxtst-dev \
        libxrandr-dev libxinerama-dev libxcursor-dev libxdamage-dev libxcomposite-dev \
        libatk1.0-dev libatk-bridge2.0-dev libpango1.0-dev libgdk-pixbuf2.0-dev libxkbcommon-dev \
      && break; \
      echo "apt install attempt ${i} failed, retrying in 15s..."; \
      sleep 15; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Install a vcpkg-compatible CMake so manifest installs do not need to fetch
# their own bootstrap archive during the build.
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then CMAKE_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ]; then CMAKE_ARCH="aarch64"; \
    else CMAKE_ARCH="x86_64"; fi && \
    mkdir -p /opt/cmake && \
    curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300 \
      "https://github.com/Kitware/CMake/releases/download/v3.31.10/cmake-3.31.10-linux-${CMAKE_ARCH}.tar.gz" \
      -o /tmp/cmake-3.31.10.tar.gz && \
    tar -xzf /tmp/cmake-3.31.10.tar.gz -C /opt/cmake --strip-components=1 && \
    ln -sf /opt/cmake/bin/cmake /usr/local/bin/cmake && \
    ln -sf /opt/cmake/bin/ctest /usr/local/bin/ctest && \
    ln -sf /opt/cmake/bin/cpack /usr/local/bin/cpack

# Fetch vcpkg from the pinned upstream release tag. GitHub codeload is already
# used for other pinned source archives below and avoids intermittent Gitee
# archive URL failures observed in Actions.
RUN mkdir -p /opt/vcpkg \
    && curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300 \
      https://codeload.github.com/microsoft/vcpkg/tar.gz/refs/tags/2026.01.16 \
      | tar -xz --strip-components=1 -C /opt/vcpkg \
    && /opt/vcpkg/bootstrap-vcpkg.sh

# The pinned vcpkg sleef port disables SVE on Linux arm64, but the pinned
# libtorch build still emits references to SVE-backed Sleef_*_sve symbols from
# libtorch_cpu.so. Re-enable SVE in the sleef port before manifest install so
# arm64 builds produce the symbols libtorch expects during final link.
RUN python3 - <<'PY'
from pathlib import Path

portfile = Path('/opt/vcpkg/ports/sleef/portfile.cmake')
text = portfile.read_text()
old = '        -DSLEEF_DISABLE_SVE=ON  # arm64 build issues, officially unmaintained\n'

if old not in text:
    raise SystemExit('Expected SLEEF_DISABLE_SVE line was not found in sleef portfile')

portfile.write_text(text.replace(old, ''))
print('Patched sleef portfile to keep SVE enabled for arm64 libtorch linkage')
PY

# LMDB upstream GitLab endpoint has intermittently served an expired cert in CI.
# Patch the lmdb port to use the GitHub mirror tarball for the same LMDB_0.9.33
# tag so vcpkg installs stay deterministic and reliable in GitHub Actions.
RUN python3 - <<'PY'
from pathlib import Path

portfile = Path('/opt/vcpkg/ports/lmdb/portfile.cmake')
text = portfile.read_text()

old = '''vcpkg_from_gitlab(
    OUT_SOURCE_PATH SOURCE_PATH
    GITLAB_URL https://git.openldap.org
    REPO openldap/openldap
    REF "LMDB_${VERSION}"
    SHA512 57404b35adb5136fcdf60552c2dd2626b9753868f2707d3279725e08145cee3be0d311189b2c6ef6879f25cf09962e6b423c70c8a2e09ef1b368948e873d92b5
    HEAD_REF master
    PATCHES
        getopt-win32.diff
)'''

new = '''vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO LMDB/lmdb
    REF "LMDB_${VERSION}"
    SHA512 5c769936372cf3c9ce3a555a19506e8bd0567f2f3fc8e2b199e0404904c34ad2baac273a21b547d2049d99873ab6319baafb34bd5dd4fe3c48129e993d774f64
    HEAD_REF mdb.master
    PATCHES
        getopt-win32.diff
)'''

if old not in text:
    raise SystemExit('Expected lmdb source block was not found in lmdb portfile')

portfile.write_text(text.replace(old, new))
print('Patched lmdb portfile to fetch LMDB from GitHub mirror')
PY

# OpenBLAS's native CPU auto-detection can fail on newer x86_64 hosts where
# getarch selects a CPU name that the container's GCC does not understand.
# Force a generic x64 target so the build stays portable and avoids the
# tigerlake/native detection failure during vcpkg install.
RUN python3 - <<'PY'
from pathlib import Path

portfile = Path('/opt/vcpkg/ports/openblas/portfile.cmake')
text = portfile.read_text()
old = '''vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${OPTIONS}
        "-DCMAKE_PROJECT_INCLUDE=${CURRENT_PORT_DIR}/cmake-project-include.cmake"
        -DBUILD_TESTING=OFF
        -DBUILD_WITHOUT_LAPACK=ON
        -DNOFORTRAN=ON
    MAYBE_UNUSED_VARIABLES
        GETARCH_BINARY_DIR
)'''
new = '''if(VCPKG_TARGET_ARCHITECTURE STREQUAL "x64")
    list(APPEND OPTIONS -DTARGET=GENERIC)
endif()

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${OPTIONS}
        "-DCMAKE_PROJECT_INCLUDE=${CURRENT_PORT_DIR}/cmake-project-include.cmake"
        -DBUILD_TESTING=OFF
        -DBUILD_WITHOUT_LAPACK=ON
        -DNOFORTRAN=ON
    MAYBE_UNUSED_VARIABLES
        GETARCH_BINARY_DIR
)'''
if old not in text:
    raise SystemExit('Expected openblas configure block was not found in openblas portfile')
portfile.write_text(text.replace(old, new))
print('Patched openblas portfile to use a generic x64 target')
PY

# Use codeload.github.com for vcpkg GitHub archives. The codeload tarballs
# match the existing vcpkg SHA512s, but they are much more reliable here than
# github.com/archive downloads from rootless Podman builds.
RUN python3 - <<'PY'
from pathlib import Path

script = Path('/opt/vcpkg/scripts/cmake/vcpkg_from_github.cmake')
text = script.read_text()
old = '''    if(arg_USE_TARBALL_API)
        # This alternative endpoint has a better support for GitHub's personal
        # access tokens (for instance when there is SSO enabled within the
        # organization).
        set(download_url
            "${github_api_url}/repos/${org_name}/${repo_name}/tarball/${ref_to_use}"
        )
    else()
        set(download_url
            "${github_host}/${org_name}/${repo_name}/archive/${ref_to_use}.tar.gz"
        )
    endif()

    # Try to download the file information from github
    vcpkg_download_distfile(archive
        URLS "${download_url}"
        FILENAME "${downloaded_file_name}"
        ${headers_param}
        ${sha512_param}
        ${redownload_param}
    )
'''
new = '''    set(download_urls
        "https://codeload.github.com/${org_name}/${repo_name}/tar.gz/${ref_to_use}"
        "${github_host}/${org_name}/${repo_name}/archive/${ref_to_use}.tar.gz"
    )

    # Try to download the file information from github
    vcpkg_download_distfile(archive
        URLS ${download_urls}
        FILENAME "${downloaded_file_name}"
        ${headers_param}
        ${sha512_param}
        ${redownload_param}
    )
'''
if old not in text:
    raise SystemExit('Expected GitHub download URL block was not found in vcpkg_from_github.cmake')
script.write_text(text.replace(old, new))
print('Patched vcpkg_from_github.cmake to use codeload.github.com with github.com/archive fallback')
PY

# Seed the known-flaky cpuinfo archive into the vcpkg downloads cache so the
# manifest install can continue even if GitHub fetches are unreliable inside
# rootless Podman. The portfile is pinned to this exact commit and SHA512.
RUN mkdir -p /opt/vcpkg/downloads && \
    curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300 \
      https://codeload.github.com/pytorch/cpuinfo/tar.gz/877328f188a3c7d1fa855871a278eb48d530c4c0 \
      -o /opt/vcpkg/downloads/pytorch-cpuinfo-877328f188a3c7d1fa855871a278eb48d530c4c0.tar.gz && \
    python3 - <<'PY'
from hashlib import sha512
from pathlib import Path
expected = 'b6d5a9ce9996eee3b2f09f39115f7ae178fe4d4814cc35b049a59d04a82228e268aa52d073c307ccb56a427428622940e1c77f004c99851dfca0d3a5d803658b'
path = Path('/opt/vcpkg/downloads/pytorch-cpuinfo-877328f188a3c7d1fa855871a278eb48d530c4c0.tar.gz')
actual = sha512(path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit(f'cpuinfo archive hash mismatch: {actual} != {expected}')
print('Seeded cpuinfo archive in vcpkg downloads cache')
PY

# onnxruntime (both arches) and libtorch (amd64 only; vcpkg.json still
# builds it from source on arm64, where no official prebuilt exists) are
# fetched as official prebuilt releases instead of compiled by vcpkg. Those
# two ports previously dominated CI wall time (onnxruntime alone regularly
# took 15-20+ minutes; libtorch/OpenBLAS could exceed 90 minutes) and were
# the direct cause of the amd64 job being killed by the 6-hour GitHub-hosted
# runner limit. /opt/libtorch is always created so the runtime stage's COPY
# below never fails on arm64, where it stays an empty placeholder.
ARG ONNXRUNTIME_VERSION=1.23.2
ARG LIBTORCH_VERSION=2.7.1
# amd64 uses the CUDA-enabled LibTorch build so ModelTrainer's transformer
# training (see src/ml/ModelTrainer.cpp) runs on GPU when the deploy host has
# an NVIDIA GPU + nvidia-container-toolkit configured (a host-side, per-
# deployment concern this Dockerfile cannot provide) — and transparently
# falls back to CPU otherwise via torch::cuda::is_available(), including in
# this CI build itself, which has no GPU. cu126 is a broadly-compatible
# modern CUDA runtime; the "shared-with-deps" zip bundles its own
# cudart/cublas/cudnn runtime libraries, so no CUDA toolkit is needed in
# this build stage — only linking against the provided headers/.so files.
# arm64 has no official prebuilt (built from source via vcpkg below) and
# stays CPU-only; there is no Linux ARM CUDA or MLX target for this build.
ARG LIBTORCH_CUDA_VARIANT=cu126
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ORT_ARCH="x64"; \
    elif [ "$ARCH" = "aarch64" ]; then ORT_ARCH="aarch64"; \
    else ORT_ARCH="x64"; fi && \
    mkdir -p /opt/onnxruntime /opt/libtorch/lib && \
    curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 300 \
      "https://github.com/microsoft/onnxruntime/releases/download/v${ONNXRUNTIME_VERSION}/onnxruntime-linux-${ORT_ARCH}-${ONNXRUNTIME_VERSION}.tgz" \
      -o /tmp/onnxruntime.tgz && \
    tar -xzf /tmp/onnxruntime.tgz -C /opt/onnxruntime --strip-components=1 && \
    rm -f /tmp/onnxruntime.tgz && \
    mkdir -p /opt/onnxruntime/include-nested/onnxruntime && \
    mv /opt/onnxruntime/include/* /opt/onnxruntime/include-nested/onnxruntime/ && \
    rmdir /opt/onnxruntime/include && \
    mv /opt/onnxruntime/include-nested /opt/onnxruntime/include && \
    if [ "$ARCH" = "x86_64" ]; then \
      curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 --max-time 1800 \
        "https://download.pytorch.org/libtorch/${LIBTORCH_CUDA_VARIANT}/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2B${LIBTORCH_CUDA_VARIANT}.zip" \
        -o /tmp/libtorch.zip && \
      unzip -q /tmp/libtorch.zip -d /tmp/libtorch-extracted && \
      mv /tmp/libtorch-extracted/libtorch/* /opt/libtorch/ && \
      rm -rf /tmp/libtorch.zip /tmp/libtorch-extracted; \
    fi

WORKDIR /build

# Copy manifest + custom triplets first so dependency cache keys include
# ONNX static-registration policy.
COPY vcpkg.json .
COPY vcpkg-triplets ./vcpkg-triplets

# Install dependencies with retry logic to handle transient network issues.
# libtorch/vcpkg can exceed 90 minutes on arm64 (the only arch still
# building it from source; amd64 uses the prebuilt release above), so keep
# the per-attempt ceiling generous enough for a clean build instead of
# timing out mid-install.
#
# --x-install-root pins this to the exact directory the later cmake
# configure step also targets via -DVCPKG_INSTALLED_DIR (see below). vcpkg
# manifest installs default to <manifest-dir>/vcpkg_installed (here
# /build/vcpkg_installed), while CMake's own vcpkg toolchain integration
# defaults to <CMAKE_BINARY_DIR>/vcpkg_installed (/build/build/vcpkg_installed)
# — two different paths. Without aligning them, the cmake step's own
# implicit manifest-install check finds this step's output invisible and
# silently rebuilds the entire dependency graph from scratch a second time,
# in a fresh RUN-step shell that also does not inherit VCPKG_BINARY_SOURCES
# (export does not persist across Dockerfile RUN instructions), so that
# second rebuild gets no benefit from either this step's local build or the
# NuGet cache it just populated below.
#
# Directory alignment alone was not sufficient, though: this step also sets
# VCPKG_DEFAULT_HOST_TRIPLET=$TRIPLET via `export`, which does not persist
# to the cmake step's shell either. Confirmed directly in a real run's
# logs: with the directory aligned, the cmake step recognized only two
# leaf packages (no host-tool build dependency) as already installed and
# rebuilt everything else — including tearing down and rebuilding the
# vcpkg-cmake/vcpkg-cmake-config/etc. host-tool packages this step had
# already built under the custom overlay triplet, this time under the
# plain default host triplet instead, since the cmake step never saw
# VCPKG_DEFAULT_HOST_TRIPLET and fell back to vcpkg's own default host
# triplet detection. Since virtually every real port's build depends on
# those host tools, that one mismatch cascades into a full rebuild of the
# whole graph. (A `VCPKG_BUILD_TYPE=release` cmake variable was tried
# first and confirmed ineffective here — the overlay triplet file already
# hardcodes `VCPKG_BUILD_TYPE release`, so it was never the actual
# mismatch.) The cmake step below now passes -DVCPKG_HOST_TRIPLET=$TRIPLET
# to match.
#
# The remaining vcpkg ports (drogon, libpqxx, spdlog, xtensor/xtl/xsimd,
# hiredis, redis-plus-plus, and libtorch-from-source on arm64) are cached
# via a NuGet-backed binary cache on GitHub Packages when a GITHUB_TOKEN is
# supplied as a BuildKit secret, so an unchanged port is fetched prebuilt
# instead of recompiled on every run — this is on top of, not instead of,
# the Docker/GHA layer cache: it still helps whenever that layer cache
# misses (a vcpkg.json change, a fresh cache scope) but most ports are
# otherwise unchanged. GITHUB_REPOSITORY_OWNER/GITHUB_REPOSITORY are plain
# build args since neither is sensitive; the token is only ever read from
# the secret mount, never a build arg or ENV, so it cannot leak into a
# layer. A build without the secret (a local `docker build`, a fork PR)
# silently falls back to no binary caching rather than failing.
ARG GITHUB_REPOSITORY_OWNER=""
ARG GITHUB_REPOSITORY=""
ARG VCPKG_NUGET_READWRITE="false"
RUN --mount=type=secret,id=github_token,required=false \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux-onnxstaticoff"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux-onnxstaticoff"; \
    else TRIPLET="x64-linux-onnxstaticoff"; fi && \
    export VCPKG_DISABLE_METRICS=1 && \
    export VCPKG_DEFAULT_HOST_TRIPLET=$TRIPLET && \
    # We only ship a Release backend image, so avoid building vcpkg debug
    # packages as well; this cuts protobuf/libtorch build time and storage.
    export VCPKG_BUILD_TYPE=release && \
    if [ -s /run/secrets/github_token ] && [ -n "$GITHUB_REPOSITORY_OWNER" ]; then \
      GH_TOKEN=$(cat /run/secrets/github_token); \
      NUGET_SOURCE="https://nuget.pkg.github.com/${GITHUB_REPOSITORY_OWNER}/index.json"; \
      NUGET_EXE=$(/opt/vcpkg/vcpkg fetch nuget | tail -n 1); \
      if mono "$NUGET_EXE" sources add -Name "GitHubPackages" -Source "$NUGET_SOURCE" -UserName "$GITHUB_REPOSITORY_OWNER" -Password "$GH_TOKEN" -StorePasswordInClearText \
         && mono "$NUGET_EXE" setapikey "$GH_TOKEN" -Source "$NUGET_SOURCE"; then \
        export VCPKG_NUGET_REPOSITORY="https://github.com/${GITHUB_REPOSITORY}"; \
        if [ "$VCPKG_NUGET_READWRITE" = "true" ]; then \
          export VCPKG_BINARY_SOURCES="clear;nuget,GitHubPackages,readwrite"; \
        else \
          export VCPKG_BINARY_SOURCES="clear;nuget,GitHubPackages,read"; \
        fi; \
      else \
        echo "NuGet binary-cache credential setup failed; continuing without vcpkg binary caching" >&2; \
        export VCPKG_BINARY_SOURCES=clear; \
      fi; \
    else \
      export VCPKG_BINARY_SOURCES=clear; \
    fi && \
    # GitHub-hosted standard runners (this workflow's target, not the local
    # rootless-Podman path this cap was originally tuned for) give public
    # repos 4 vCPUs/16GB. amd64 no longer builds onnxruntime or libtorch at
    # all here (both prebuilt above), so its remaining ports are light
    # enough to parallelize fully; arm64 still builds libtorch (and its
    # protobuf build dependency) from source, so it keeps a lower cap to
    # avoid the memory pressure that motivated the original cap of 1.
    if [ "$ARCH" = "x86_64" ]; then export VCPKG_MAX_CONCURRENCY=$(nproc); \
    else export VCPKG_MAX_CONCURRENCY=2; fi && \
    SUCCESS=0 && \
    mkdir -p /build/build/vcpkg_installed && \
    for i in 1 2 3; do \
    timeout 360m /opt/vcpkg/vcpkg install --overlay-triplets=/build/vcpkg-triplets --triplet $TRIPLET --x-install-root=/build/build/vcpkg_installed && SUCCESS=1 && break || \
    (echo "vcpkg install attempt $i failed, retrying in 10s..." && sleep 10); \
    done && \
    if [ $SUCCESS -eq 0 ]; then echo "vcpkg install failed" && exit 1; fi && \
    rm -rf /opt/vcpkg/buildtrees /opt/vcpkg/downloads

# Copy the rest of the source after dependencies for better Docker layer caching
COPY . .

# Build the application
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux-onnxstaticoff"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux-onnxstaticoff"; \
    else TRIPLET="x64-linux-onnxstaticoff"; fi && \
    cmake -S . -B build \
    -DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake \
    -DVCPKG_OVERLAY_TRIPLETS=/build/vcpkg-triplets \
    -DVCPKG_TARGET_TRIPLET=$TRIPLET \
    -DVCPKG_HOST_TRIPLET=$TRIPLET \
    -DVCPKG_INSTALLED_DIR=/build/build/vcpkg_installed \
    -DCMAKE_BUILD_TYPE=Release \
    -DONNXRUNTIME_ROOT=/opt/onnxruntime \
    -DCMAKE_PREFIX_PATH=/opt/libtorch && \
    cmake --build build -j$(nproc) && \
    ctest --test-dir build --output-on-failure \
      -R "transformer_onnx_export|portfolio_accounting|simulated_trading_contract|simulated_trading_diagnosis|zero_trade_orderbook_fixture|trading_stats_calculator|position_sizing_policy|strategy_signal|strategy_expectancy_harness|execution_reconciliation|coinbase_auth|coinbase_order|coinbase_portfolio|calibration"

# --- STAGE 2: Runtime ---
# Use a plain Ubuntu runtime image so CI does not depend on MCR availability.
FROM ubuntu:22.04 AS runtime

WORKDIR /app

# Runtime dependencies for the ONNX/OpenBLAS stack used by trading_bot_cpp.
# libgomp1 provides libgomp.so.1, which the binary needs at startup.
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && \
      apt-get install -y --no-install-recommends --fix-missing libgfortran5 libgomp1 ca-certificates \
      && break; \
      echo "runtime apt install attempt ${i} failed, retrying in 15s..."; \
      sleep 15; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Copy the compiled binary from the builder stage
COPY --from=builder /build/build/trading_bot_cpp .
# Copy only the necessary vcpkg-installed libraries
COPY --from=builder /build/build/vcpkg_installed/ /app/vcpkg_installed/
# Prebuilt onnxruntime (both arches) and libtorch (amd64 only — an empty
# placeholder directory on arm64, where libtorch comes from vcpkg above)
# are shared libraries rather than the static archives vcpkg's triplet
# produces, so they need to ship alongside the binary explicitly.
COPY --from=builder /opt/onnxruntime/lib/ /opt/onnxruntime/lib/
COPY --from=builder /opt/libtorch/lib/ /opt/libtorch/lib/

# Strip symbols from the shipped binary and trim vcpkg to runtime-only assets.
# The builder stage still needs headers and static libs, but the final image
# only needs shared libraries and their runtime data.
RUN set -eux; \
    strip --strip-unneeded /app/trading_bot_cpp 2>/dev/null || true; \
    find /app/vcpkg_installed /opt/onnxruntime /opt/libtorch -type f -name '*.so*' \
      -exec sh -c 'strip --strip-unneeded "$1" >/dev/null 2>&1 || true' sh {} \;

RUN set -eux; \
    for dir in include pkgconfig cmake debug doc man; do \
      find /app/vcpkg_installed -type d -name "$dir" -prune -exec rm -rf '{}' +; \
    done; \
    for pattern in '*.a' '*.la' '*.o' '*.pc' '*.cmake'; do \
      find /app/vcpkg_installed -type f -name "$pattern" -delete; \
    done; \
    find /app/vcpkg_installed -type f -name 'libonnxruntime_providers_shared.so' -delete

# Ensure the app can find the vcpkg libraries, plus the prebuilt onnxruntime
# and (amd64 only) libtorch shared libraries, at runtime
ENV LD_LIBRARY_PATH=/app/vcpkg_installed/arm64-linux-onnxstaticoff/lib:/app/vcpkg_installed/x64-linux-onnxstaticoff/lib:/opt/onnxruntime/lib:/opt/libtorch/lib

CMD ["./trading_bot_cpp"]
