import multiprocessing
from config import Config

# Worker Processes
workers = Config.WORKER_COUNT
max_requests = 500
max_requests_jitter = 200
timeout = 90
