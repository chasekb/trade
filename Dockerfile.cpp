# --- STAGE 1: Build ---
FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04 AS builder

# Install build dependencies and cleanup in one layer
RUN apt-get update && apt-get install -y \
    cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev \
    autoconf automake libtool linux-libc-dev gfortran pkg-config gperf autoconf-archive python3-venv \
    libx11-dev libxext-dev libxrender-dev libxcb1-dev libxau-dev libxdmcp-dev libxft-dev \
    libdbus-1-dev libglib2.0-dev libxi-dev libxtst-dev \
    libxrandr-dev libxinerama-dev libxcursor-dev libxdamage-dev libxcomposite-dev \
    libatk1.0-dev libatk-bridge2.0-dev libpango1.0-dev libgdk-pixbuf2.0-dev libxkbcommon-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone vcpkg from a stable release tag to avoid transient master breakages
RUN git clone --depth=1 -b 2026.01.16 https://github.com/microsoft/vcpkg.git /opt/vcpkg \
    && /opt/vcpkg/bootstrap-vcpkg.sh

WORKDIR /build

# Copy manifest first so vcpkg install can be cached separately
COPY vcpkg.json .

# Install dependencies with retry logic to handle transient network issues
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux"; \
    else TRIPLET="x64-linux"; fi && \
    SUCCESS=0 && \
    for i in 1 2 3; do \
    /opt/vcpkg/vcpkg install --triplet $TRIPLET && SUCCESS=1 && break || \
    (echo "vcpkg install attempt $i failed, retrying in 10s..." && sleep 10); \
    done && \
    if [ $SUCCESS -eq 0 ]; then echo "vcpkg install failed" && exit 1; fi && \
    rm -rf /opt/vcpkg/buildtrees /opt/vcpkg/downloads

# Copy the rest of the source after dependencies for better Docker layer caching
COPY . .

# Build the application
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux"; \
    else TRIPLET="x64-linux"; fi && \
    cmake -S . -B build \
    -DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake \
    -DVCPKG_TARGET_TRIPLET=$TRIPLET \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc)

# --- STAGE 2: Runtime ---
FROM ubuntu:22.04

# Install only runtime essentials
RUN apt-get update && apt-get install -y \
    libssl3 libuuid1 libc-ares2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the compiled binary from the builder stage
COPY --from=builder /build/build/trading_bot_cpp .
# Copy only the necessary vcpkg-installed libraries
COPY --from=builder /build/build/vcpkg_installed/ /app/vcpkg_installed/

# Ensure the app can find the vcpkg libraries at runtime
ENV LD_LIBRARY_PATH=/app/vcpkg_installed/arm64-linux/lib:/app/vcpkg_installed/x64-linux/lib:$LD_LIBRARY_PATH

CMD ["./trading_bot_cpp"]
