# Calf-Broker Local Development Makefile
# Two-tier Kafka development environment

# Configuration
DOCKER_COMPOSE_FILE := deploy/docker/docker-compose.yml
KIND_CONFIG_FILE := deploy/k8s/kind-config.yaml
KAFKA_MANIFEST_FILE := deploy/k8s/strimzi/kafka-kraft.yaml
KIND_CLUSTER_NAME := kafka-integration
KAFKA_NAMESPACE := kafka
STRIMZI_VERSION := 0.49.0

.PHONY: help dev-up dev-down dev-status dev-ui dev-logs \
        k8s-up k8s-down k8s-kind-create k8s-status k8s-logs k8s-port-forward \
        k8s-strimzi-install k8s-kafka-deploy k8s-kafka-delete

# =============================================================================
# HELP
# =============================================================================

help:
	@echo "Calf-Broker Local Kafka Development"
	@echo ""
	@echo "TIER 1 - Daily Development (docker-compose):"
	@echo "  make dev-up        Start Kafka (localhost:9092)"
	@echo "  make dev-down      Stop and remove Kafka"
	@echo "  make dev-status    Show container status"
	@echo "  make dev-ui        Start Kafka with UI (localhost:8080)"
	@echo "  make dev-logs      Tail Kafka logs"
	@echo ""
	@echo "TIER 2 - Integration Testing (Kind + Strimzi):"
	@echo "  make k8s-up        Create full K8s + Kafka environment"
	@echo "  make k8s-down      Destroy Kind cluster"
	@echo "  make k8s-status    Show pod status"
	@echo "  make k8s-logs      Tail Strimzi operator logs"
	@echo "  make k8s-port-forward  Forward Kafka to localhost:9092"
	@echo ""

# =============================================================================
# TIER 1: Daily Development (docker-compose)
# =============================================================================

dev-up:
	@echo "Starting Tier 1: Kafka development environment..."
	docker compose -f $(DOCKER_COMPOSE_FILE) up -d
	@echo ""
	@echo "Waiting for Kafka to be ready..."
	@until docker exec kafka-dev /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do \
		sleep 2; \
		echo "  Waiting for Kafka..."; \
	done
	@echo ""
	@echo "Kafka is ready at localhost:9092"

dev-down:
	@echo "Stopping Tier 1: Kafka development environment..."
	docker compose -f $(DOCKER_COMPOSE_FILE) down -v

dev-status:
	docker compose -f $(DOCKER_COMPOSE_FILE) ps

dev-ui:
	@echo "Starting Tier 1: Kafka with UI..."
	docker compose -f $(DOCKER_COMPOSE_FILE) --profile ui up -d
	@echo ""
	@echo "Waiting for Kafka to be ready..."
	@until docker exec kafka-dev /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do \
		sleep 2; \
		echo "  Waiting for Kafka..."; \
	done
	@echo ""
	@echo "Kafka is ready at localhost:9092"
	@echo "Kafka UI is ready at http://localhost:8080"

dev-logs:
	docker compose -f $(DOCKER_COMPOSE_FILE) logs -f kafka

# =============================================================================
# TIER 2: Integration Testing (Kind + Strimzi)
# =============================================================================

k8s-up: k8s-kind-create k8s-strimzi-install k8s-kafka-deploy
	@echo ""
	@echo "=============================================="
	@echo "Tier 2: Integration environment is ready!"
	@echo "=============================================="
	@echo ""
	@echo "Kafka bootstrap (in-cluster): integration-cluster-kafka-bootstrap.kafka.svc:9092"
	@echo "Kafka bootstrap (NodePort):   localhost:30092"
	@echo ""
	@echo "Or run: make k8s-port-forward"
	@echo "Then use: localhost:9092"
	@echo ""

k8s-down:
	@echo "Destroying Tier 2: Kind cluster..."
	kind delete cluster --name $(KIND_CLUSTER_NAME) || true

k8s-kind-create:
	@echo "Creating Kind cluster..."
	@if kind get clusters 2>/dev/null | grep -qx $(KIND_CLUSTER_NAME); then \
		echo "Cluster $(KIND_CLUSTER_NAME) already exists"; \
	else \
		kind create cluster --config $(KIND_CONFIG_FILE); \
	fi
	@kubectl cluster-info --context kind-$(KIND_CLUSTER_NAME)

k8s-strimzi-install:
	@echo "Installing Strimzi operator via Helm..."
	@helm repo add strimzi https://strimzi.io/charts/ 2>/dev/null || true
	@helm repo update
	@kubectl create namespace $(KAFKA_NAMESPACE) 2>/dev/null || true
	helm upgrade --install strimzi-operator strimzi/strimzi-kafka-operator \
		--namespace $(KAFKA_NAMESPACE) \
		--version $(STRIMZI_VERSION) \
		--wait --timeout 5m
	@echo ""
	@echo "Waiting for Strimzi CRDs to be established..."
	@kubectl wait --for=condition=Established crd/kafkas.kafka.strimzi.io --timeout=60s
	@kubectl wait --for=condition=Established crd/kafkanodepools.kafka.strimzi.io --timeout=60s
	@echo "Strimzi operator is ready"

k8s-kafka-deploy:
	@echo "Deploying Kafka cluster (KRaft mode)..."
	kubectl apply -f $(KAFKA_MANIFEST_FILE)
	@echo ""
	@echo "Waiting for Kafka cluster to be ready (this may take 3-5 minutes)..."
	@kubectl wait kafka/integration-cluster \
		--for=condition=Ready \
		--timeout=600s \
		-n $(KAFKA_NAMESPACE)
	@echo "Kafka cluster is ready"

k8s-kafka-delete:
	@echo "Deleting Kafka cluster..."
	kubectl delete -f $(KAFKA_MANIFEST_FILE) || true

k8s-status:
	@echo "=== Strimzi Operator ==="
	@kubectl get pods -n $(KAFKA_NAMESPACE) -l name=strimzi-cluster-operator
	@echo ""
	@echo "=== Kafka Cluster ==="
	@kubectl get kafka -n $(KAFKA_NAMESPACE)
	@echo ""
	@echo "=== Kafka Node Pools ==="
	@kubectl get kafkanodepool -n $(KAFKA_NAMESPACE)
	@echo ""
	@echo "=== All Pods ==="
	@kubectl get pods -n $(KAFKA_NAMESPACE)

k8s-logs:
	kubectl logs -f deployment/strimzi-cluster-operator -n $(KAFKA_NAMESPACE)

k8s-port-forward:
	@echo "Forwarding Kafka to localhost:9092..."
	@echo "Press Ctrl+C to stop"
	kubectl port-forward svc/integration-cluster-kafka-bootstrap -n $(KAFKA_NAMESPACE) 9092:9092
