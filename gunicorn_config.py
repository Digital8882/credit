# gunicorn_config.py
workers = 1

# The timeout in seconds for requests
timeout = 120

# Number of worker connections
worker_connections = 1000

# Log level
loglevel = 'debug'

# Enable or disable the use of the HTTP Keep-Alive feature
keepalive = 2

# The maximum number of requests a worker will process before restarting
max_requests = 1000

# Random jitter added to max_requests to prevent all workers from restarting at the same time
max_requests_jitter = 100
