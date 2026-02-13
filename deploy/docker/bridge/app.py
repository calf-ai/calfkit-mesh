from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from faststream.kafka.fastapi import KafkaRouter
import os

router = KafkaRouter(os.getenv("KAFKA_BOOTSTRAP_SERVERS", "local-broker:29092"))

app = FastAPI(title="Kafka HTTP Bridge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.post("/publish/{topic}")
async def publish(topic: str, message: dict):
    await router.broker.publish(message, topic)
    return {"status": "ok", "topic": topic}


@app.get("/health")
async def health():
    return {"status": "healthy"}
