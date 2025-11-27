from celery import Celery

def make_celery():
    celery = Celery(
        __name__,
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0",
        include=["celery_task.tasks"],
    )
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        worker_hijack_root_logger=False,
    )
    return celery

celery = make_celery()
