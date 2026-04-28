# Procfile
# Railway reads this to know how to start each service type.
# The "web" process is the public-facing Streamlit app.
# The "worker" process is the scheduler (run via Railway Cron separately).

web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
worker: python scheduler.py --now
