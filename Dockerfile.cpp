# --- STAGE 1: Build ---
FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04 AS builder

# Install build dependencies and cleanup in one layer
RUN apt-get update && apt-get install -y \
    cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev \
    autoconf automake libtool linux-libc-dev gfortran pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Clone vcpkg from a stable release tag to avoid transient master breakages
RUN git clone --depth=1 -b 2026.01.16 https://github.com/microsoft/vcpkg.git /opt/vcpkg \
    && /opt/vcpkg/bootstrap-vcpkg.sh

WORKDIR /build
COPY vcpkg.json ./

# Install dependencies and clean up vcpkg metadata immediately to save space
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux"; \
    else TRIPLET="x64-linux"; fi && \
    /opt/vcpkg/vcpkg install --triplet $TRIPLET && \
    rm -rf /opt/vcpkg/buildtrees /opt/vcpkg/downloads

# Copy source and build
COPY . .
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
COPY --from=builder /build/vcpkg_installed/ /app/vcpkg_installed/

# Ensure the app can find the vcpkg libraries at runtime
ENV LD_LIBRARY_PATH=/app/vcpkg_installed/arm64-linux/lib:/app/vcpkg_installed/x64-linux/lib:$LD_LIBRARY_PATH

CMD ["./trading_bot_cpp"]
