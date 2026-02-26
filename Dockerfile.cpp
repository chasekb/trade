FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04

# Install build dependencies
RUN apt-get update && apt-get install -y cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev autoconf automake libtool linux-libc-dev && rm -rf /var/lib/apt/lists/*

# Clone and setup vcpkg
RUN git clone https://github.com/microsoft/vcpkg.git /opt/vcpkg \
    && /opt/vcpkg/bootstrap-vcpkg.sh \
    && ln -s /opt/vcpkg/vcpkg /usr/local/bin/vcpkg

# Provide the project code
WORKDIR /app

# Copy ONLY vcpkg.json first to cache dependencies
COPY vcpkg.json ./

# Install dependencies using vcpkg manifest mode
# This layer will be cached unless vcpkg.json changes
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux"; \
    else TRIPLET="x64-linux"; fi && \
    vcpkg install --triplet $TRIPLET

# Copy the rest of the source
# (.dockerignore ensures we don't overwrite vcpkg_installed)
COPY . .

# Final build
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TRIPLET="x64-linux"; \
    elif [ "$ARCH" = "aarch64" ]; then TRIPLET="arm64-linux"; \
    else TRIPLET="x64-linux"; fi && \
    echo "Listing all xtensor headers:" && \
    find /app/vcpkg_installed/ -path "*/include/xtensor/*.hpp" && \
    cmake -S . -B build \
    -DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake \
    -DVCPKG_TARGET_TRIPLET=$TRIPLET \
    -DVCPKG_INSTALLED_DIR=/app/vcpkg_installed \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc)

CMD ["./build/trading_bot_cpp"]
