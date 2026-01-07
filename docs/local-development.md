# Local Kafka Development

This project provides a two-tier local Kafka development environment.

## Prerequisites

### Tier 1 (Daily Development)
- Docker
- Docker Compose

### Tier 2 (Integration Testing)
- Docker
- [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Tier 1: Daily Development (docker-compose)                     │
│  - Single Kafka node with KRaft                                 │
│  - Fast startup (~10 seconds)                                   │
│  - Use for: writing/testing application code                    │
│  - Bootstrap: localhost:9092                                    │
├─────────────────────────────────────────────────────────────────┤
│  Tier 2: Integration Testing (Kind + Strimzi)                   │
│  - 3-node Kafka cluster with KRaft                              │
│  - Full Kubernetes environment                                  │
│  - Use for: testing K8s manifests, CI/CD, pre-commit            │
│  - Bootstrap: localhost:30092 (NodePort)                        │
│              localhost:9092 (with port-forward)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Tier 1: Daily Development

```bash
# Start Kafka
make dev-up

# Your application connects to:
# bootstrap.servers=localhost:9092

# View status
make dev-status

# View logs
make dev-logs

# Stop Kafka
make dev-down
```

### Tier 1: With Kafka UI

```bash
# Start Kafka with web UI
make dev-ui

# Kafka: localhost:9092
# UI:    http://localhost:8080

# Stop everything
make dev-down
```

### Tier 2: Integration Testing

```bash
# Create full K8s + Kafka environment (takes 3-5 minutes)
make k8s-up

# Check status
make k8s-status

# Option A: Use NodePort (no extra terminal needed)
# bootstrap.servers=localhost:30092

# Option B: Use port-forward (runs in foreground)
make k8s-port-forward
# bootstrap.servers=localhost:9092

# View Strimzi operator logs
make k8s-logs

# Destroy everything
make k8s-down
```

## Configuration Details

### Tier 1: Kafka Settings

| Setting | Value |
|---------|-------|
| Image | apache/kafka:latest |
| Mode | KRaft (no ZooKeeper) |
| Replication Factor | 1 (single node) |
| Auto Create Topics | Enabled |
| Data Persistence | Ephemeral (lost on container restart) |

### Tier 2: Kafka Settings

| Setting | Value |
|---------|-------|
| Strimzi Version | 0.49.0 |
| Kafka Version | 4.1.1 |
| Mode | KRaft (no ZooKeeper) |
| Nodes | 3 (dual-role: controller + broker) |
| Replication Factor | 3 |
| Min ISR | 2 |
| Auto Create Topics | Enabled |
| Storage | Ephemeral (lost on cluster delete) |

## Connecting Your Application

### Environment Variables

```bash
# Tier 1
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Tier 2 (NodePort)
export KAFKA_BOOTSTRAP_SERVERS=localhost:30092

# Tier 2 (port-forward)
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### Python (confluent-kafka)

```python
from confluent_kafka import Producer, Consumer

config = {
    'bootstrap.servers': 'localhost:9092',
}

producer = Producer(config)
producer.produce('my-topic', key='key', value='value')
producer.flush()
```

### Go (segmentio/kafka-go)

```go
package main

import (
    "context"
    "github.com/segmentio/kafka-go"
)

func main() {
    writer := &kafka.Writer{
        Addr:  kafka.TCP("localhost:9092"),
        Topic: "my-topic",
    }
    defer writer.Close()

    writer.WriteMessages(context.Background(),
        kafka.Message{Key: []byte("key"), Value: []byte("value")},
    )
}
```

### Node.js (kafkajs)

```javascript
const { Kafka } = require('kafkajs');

const kafka = new Kafka({
  clientId: 'my-app',
  brokers: ['localhost:9092'],
});

const producer = kafka.producer();
await producer.connect();
await producer.send({
  topic: 'my-topic',
  messages: [{ key: 'key', value: 'value' }],
});
```

## Working with Topics

### Tier 1 (docker-compose)

```bash
# List topics
docker exec kafka-dev /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Create topic
docker exec kafka-dev /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic --partitions 3 --replication-factor 1

# Describe topic
docker exec kafka-dev /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic my-topic

# Produce messages (interactive)
docker exec -it kafka-dev /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic my-topic

# Consume messages
docker exec -it kafka-dev /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic my-topic --from-beginning
```

### Tier 2 (Kind + Strimzi)

```bash
# List topics
kubectl exec -it integration-cluster-dual-role-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Create topic
kubectl exec -it integration-cluster-dual-role-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic my-topic --partitions 3 --replication-factor 3

# Or use Strimzi KafkaTopic CRD
kubectl apply -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: my-topic
  namespace: kafka
  labels:
    strimzi.io/cluster: integration-cluster
spec:
  partitions: 3
  replicas: 3
  config:
    min.insync.replicas: "2"
EOF
```

## Troubleshooting

### Tier 1 Issues

**Kafka won't start:**
```bash
# Check logs
docker compose -f deploy/docker/docker-compose.yml logs kafka

# Reset everything
make dev-down
make dev-up
```

**Port 9092 already in use:**
```bash
# Find what's using the port
lsof -i :9092

# Kill the process or change the port in docker-compose.yml
```

### Tier 2 Issues

**Kind cluster won't create:**
```bash
# Check Docker is running
docker info

# Delete and recreate
kind delete cluster --name kafka-integration
make k8s-up
```

**Kafka pods stuck in Pending:**
```bash
# Check events
kubectl describe pod -n kafka -l strimzi.io/cluster=integration-cluster

# Check node resources
kubectl describe nodes
```

**Strimzi operator not starting:**
```bash
# Check operator logs
kubectl logs -n kafka deployment/strimzi-cluster-operator

# Check Helm release
helm list -n kafka
```

## File Structure

```
deploy/
├── docker/
│   └── docker-compose.yml    # Tier 1: Daily development
└── k8s/
    ├── kind-config.yaml      # Tier 2: Kind cluster config
    └── strimzi/
        └── kafka-kraft.yaml  # Tier 2: Kafka + KafkaNodePool CRs
docs/
└── local-development.md      # This file
```

## Make Targets Reference

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make dev-up` | Start Tier 1 Kafka |
| `make dev-down` | Stop Tier 1 Kafka |
| `make dev-status` | Show Tier 1 container status |
| `make dev-ui` | Start Tier 1 with Kafka UI |
| `make dev-logs` | Tail Tier 1 Kafka logs |
| `make k8s-up` | Create full Tier 2 environment |
| `make k8s-down` | Destroy Tier 2 Kind cluster |
| `make k8s-status` | Show Tier 2 pod status |
| `make k8s-logs` | Tail Strimzi operator logs |
| `make k8s-port-forward` | Forward Kafka to localhost:9092 |
