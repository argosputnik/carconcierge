# gunicorn.conf.py
bind = "0.0.0.0:10000"  # Use the port Render expects
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"

