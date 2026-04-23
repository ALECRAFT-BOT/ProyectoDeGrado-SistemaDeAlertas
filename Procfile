# Procfile – SAT El Tarra
# Railway.app y Render.com usan este archivo para iniciar la app
# gunicorn sirve Flask en producción con soporte multi-proceso

web: gunicorn src.app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 30
worker: python src/scheduler.py
