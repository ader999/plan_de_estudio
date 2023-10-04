#!/usr/bin/env bash
# exit on error
set -o errexit

#poetry install
pip install -r requirements.txt

python manage.py migrate

python manage.py collectstatic --no-input

echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('overader', 'aderjasmirzeasrocha@gmail.com', '00040')" | python manage.py shell
