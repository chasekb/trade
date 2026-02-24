FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04

# Install build dependencies
RUN apt-get update && apt-get install -y cmake g++ make git libc-ares-dev uuid-dev bison flex libssl-dev autoconf automake libtool linux-libc-dev && rm -rf /var/lib/apt/lists/*

# Clone and setup vcpkg
RUN git clone https://github.com/microsoft/vcpkg.git /opt/vcpkg \
    && /opt/vcpkg/bootstrap-vcpkg.sh \
    && ln -s /opt/vcpkg/vcpkg /usr/local/bin/vcpkg

# Provide the project code
WORKDIR /app
COPY vcpkg.json CMakeLists.txt ./

# Build dependencies separately to leverage Docker cache
# We use the toolchain file to trigger manifest mode
RUN cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake -DCMAKE_BUILD_TYPE=Release || true

# Copy the rest of the source
COPY src/cpp_backend src/cpp_backend

# Final build
RUN cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake -DCMAKE_BUILD_TYPE=Release
RUN cmake --build build -j$(nproc)

CMD ["./build/trading_bot_cpp"]
