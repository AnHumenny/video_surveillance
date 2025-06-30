from celery import Celery

def make_celery():
    celery = Celery(
        __name__,
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0",
        include=["tasks"],
    )
    return celery

celery = make_celery()