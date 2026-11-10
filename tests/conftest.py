import os

# API_USER / API_PASSWORD sunt citite la IMPORT in app/main.py, fara default.
# pytest incarca acest conftest inaintea modulelor de test, deci asta e cel mai
# devreme punct in care le putem seta. Fara ele, `import app.main` da KeyError.
# `setdefault`: daca mediul le are deja setate, nu le calcam.
os.environ.setdefault("API_USER", "test-user")
os.environ.setdefault("API_PASSWORD", "test-password")
