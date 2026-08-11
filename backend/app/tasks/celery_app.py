import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "jeevan_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task
def process_historical_data(data_chunk: list):
    """
    Background job to aggregate data and insert into TimescaleDB.
    """
    # Processing logic here
    print(f"Processed {len(data_chunk)} records.")
    return True
