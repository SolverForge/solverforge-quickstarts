# Multi-stage build for SolverForge Employee Scheduling (Rust)
#
# Build context should be the parent directory containing both:
#   - solverforge-rs/
#   - solverforge-quickstarts/
#
# Example:
#   docker build -f solverforge-quickstarts/rust/employee-scheduling/Dockerfile \
#                -t employee-scheduling-rust .

FROM rust:1.83-bookworm AS builder

WORKDIR /build

# Copy solverforge-rs workspace (local dependency)
COPY solverforge-rs/ ./solverforge-rs/

# Copy quickstarts
COPY solverforge-quickstarts/rust/employee-scheduling/ ./solverforge-quickstarts/rust/employee-scheduling/

WORKDIR /build/solverforge-quickstarts/rust/employee-scheduling

# Build release binary
RUN cargo build --release

# Runtime stage - minimal image
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/solverforge-quickstarts/rust/employee-scheduling/target/release/employee-scheduling ./employee-scheduling

# Copy static files
COPY --from=builder /build/solverforge-quickstarts/rust/employee-scheduling/static/ ./static/

# Copy solver config
COPY --from=builder /build/solverforge-quickstarts/rust/employee-scheduling/solver.toml ./solver.toml

# Expose port 7860 (HF Spaces default)
EXPOSE 7860

# Run the application
CMD ["./employee-scheduling"]
