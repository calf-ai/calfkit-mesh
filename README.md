# 🐮 Calfkit Mesh  [![calfkit sdk](https://img.shields.io/badge/built%20with-🐮%20agents-6f42c1)](https://github.com/calf-ai/calfkit-sdk) [![PyPI](https://img.shields.io/pypi/v/calfkit-mesh)](https://pypi.org/project/calfkit-mesh/) [![License](https://img.shields.io/pypi/l/calfkit-mesh)](https://github.com/calf-ai/calfkit-mesh/blob/main/LICENSE)

Local Kafka infrastructure for event-driven and distributed AI agent development using [Calfkit SDK](https://github.com/calf-ai/calfkit-sdk).

Provides two-tier Kafka environments using KRaft:

| Tier | Use Case | Startup | Command |
|------|----------|---------|---------|
| **Tier 1** | Daily development | ~10 seconds | `make dev-up` |
| **Tier 2** | Integration testing | 3-5 minutes | `make k8s-up` |

## Quick Start

### Start up the broker (using Docker)

```bash
# Start Kafka for local development
make dev-up

# Kafka available at localhost:9092

# Stop
make dev-down
```

## Kafka UI (optional)

```bash
# Start Kafka UI (connects to existing broker at localhost:9092)
make ui

# UI available at http://localhost:8080

# Stop
make ui-down
```

## `calfkit-mesh` pip package

For a zero-dependency local broker, this repo also publishes the
**`calfkit-mesh`** Python package. It bundles a static, memory-only build of the
[Tansu](https://github.com/tansu-io/tansu) broker (Apache Kafka-compatible)
inside platform wheels, so `calfkit`'s `ck dev` can spawn a broker without
Docker, JVM, or any network install:

```bash
pip install calfkit-mesh
```

This is the upstream of calfkit's opt-in `[mesh]` extra. The package exposes a
single locator, `calfkit_mesh.resolve_broker_bin()`, which returns the path to a
usable `tansu` executable using this resolution order:

1. **`$CALF_TANSU_BIN`** — if set, it is used verbatim (and must point at an
   executable file, or resolution fails). Use this to point `ck dev` at your own
   `tansu` build.
2. **The wheel-bundled binary** — materialized once to a stable cache path
   (`~/.calfkit/bin/tansu-<version>`) and made executable.
3. **`tansu` on your `PATH`**.

Wheels are built for Linux (`x86_64`, `aarch64`; published under both `manylinux`
and `musllinux` tags), macOS (`arm64`, `x86_64`), and Windows (`x86_64`).

## License

Apache 2.0 - see [LICENSE](LICENSE).

The Tansu binary bundled in calfkit-mesh wheels is also Apache 2.0; see
[NOTICE](NOTICE) for attribution.
