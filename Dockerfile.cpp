# --- STAGE 1: Build ---
FROM ubuntu:22.04 AS builder

# Install build dependencies with retry logic for transient mirror/network failures
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && \
      apt-get install -y --no-install-recommends --fix-missing \
        ca-certificates curl cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev \
        autoconf automake libtool libltdl-dev linux-libc-dev gfortran pkg-config gperf autoconf-archive python3-venv python3-dev \
        unzip zip \
        libx11-dev libxext-dev libxrender-dev libxcb1-dev libxau-dev libxdmcp-dev libxft-dev \
        libdbus-1-dev libglib2.0-dev libxi-dev libxtst-dev \
        libxrandr-dev libxinerama-dev libxcursor-dev libxdamage-dev libxcomposite-dev \
        libatk1.0-dev libatk-bridge2.0-dev libpango1.0-dev libgdk-pixbuf2.0-dev libxkbcommon-dev \
      && break; \
      echo "apt install attempt ${i} failed, retrying in 15s..."; \
      sleep 15; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Clone vcpkg from a stable release tag to avoid transient master breakages
RUN git clone --depth=1 -b 2026.01.16 https://github.com/microsoft/vcpkg.git /opt/vcpkg \
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

WORKDIR /build

# Copy manifest + custom triplets first so dependency cache keys include
# ONNX static-registration policy.
COPY vcpkg.json .
COPY vcpkg-triplets ./vcpkg-triplets

# Install dependencies with retry logic to handle transient network issues.
# libtorch/vcpkg can exceed 90 minutes on both arches, so keep the per-attempt
# ceiling generous enough for a clean build instead of timing out mid-install.
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux-onnxstaticoff"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux-onnxstaticoff"; \
    else TRIPLET="x64-linux-onnxstaticoff"; fi && \
    export VCPKG_DISABLE_METRICS=1 && \
    SUCCESS=0 && \
    for i in 1 2 3; do \
    timeout 120m /opt/vcpkg/vcpkg install --overlay-triplets=/build/vcpkg-triplets --triplet $TRIPLET && SUCCESS=1 && break || \
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
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc)

# --- STAGE 2: Runtime ---
# Use a plain Ubuntu runtime image so CI does not depend on MCR availability.
FROM ubuntu:22.04 AS runtime

WORKDIR /app

# Runtime dependency for ONNX/OpenBLAS stack used by trading_bot_cpp
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && \
      apt-get install -y --no-install-recommends --fix-missing libgfortran5 \
      && break; \
      echo "runtime apt install attempt ${i} failed, retrying in 15s..."; \
      sleep 15; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Copy the compiled binary from the builder stage
COPY --from=builder /build/build/trading_bot_cpp .
# Copy only the necessary vcpkg-installed libraries
COPY --from=builder /build/build/vcpkg_installed/ /app/vcpkg_installed/

# Strip symbols from the shipped binary and trim vcpkg to runtime-only assets.
# The builder stage still needs headers and static libs, but the final image
# only needs shared libraries and their runtime data.
RUN set -eux; \
    strip --strip-unneeded /app/trading_bot_cpp 2>/dev/null || true; \
    find /app/vcpkg_installed -type f -name '*.so*' -exec sh -c 'strip --strip-unneeded "$1" >/dev/null 2>&1 || true' sh {} \;

RUN set -eux; \
    for dir in include pkgconfig cmake debug doc man; do \
      find /app/vcpkg_installed -type d -name "$dir" -prune -exec rm -rf '{}' +; \
    done; \
    for pattern in '*.a' '*.la' '*.o' '*.pc' '*.cmake'; do \
      find /app/vcpkg_installed -type f -name "$pattern" -delete; \
    done; \
    find /app/vcpkg_installed -type f -name 'libonnxruntime_providers_shared.so' -delete

# Ensure the app can find the vcpkg libraries at runtime
ENV LD_LIBRARY_PATH=/app/vcpkg_installed/arm64-linux-onnxstaticoff/lib:/app/vcpkg_installed/x64-linux-onnxstaticoff/lib

CMD ["./trading_bot_cpp"]
