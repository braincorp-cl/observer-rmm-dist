SECRET_KEY = "check-deploy-test-only-not-production"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/observer_check.db",
    }
}
ALLOWED_HOSTS = ["api.example.com"]
MESH_USERNAME = "testpipeline"
MESH_SITE = "https://mesh.example.com"
MESH_TOKEN_KEY = "aabbccddee" * 20
CORS_ORIGIN_WHITELIST = ["https://rmm.example.com"]
ADMIN_URL = "abc123456/"
