release: python backend/manage.py migrate
web: gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
