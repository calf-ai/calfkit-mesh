# 🐮 Calfkit Broker  [![Calfkit SDK](https://img.shields.io/badge/Calfkit-SDK-blue?logo=github)](https://github.com/calf-ai/calfkit-sdk)

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

## License

Apache 2.0 - see [LICENSE](LICENSE)
