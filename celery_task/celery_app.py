from celery import Celery
from celery.schedules import crontab
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_celery():
    """Factory function to create and configure a Celery application instance."""

    celery = Celery(
        'celery_task',
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0",
        include=["celery_task.tasks"],
    )
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Europe/Moscow',
        enable_utc=True,
        worker_hijack_root_logger=False,
    )
    celery.conf.update(
        beat_schedule={
            'weekly-recordings-cleanup': {
                'task': 'celery_task.tasks.cleanup_weekly',
                'schedule': crontab(hour=0, minute=0, day_of_week=0),
            },
        },
    )
    return celery

celery = make_celery()
