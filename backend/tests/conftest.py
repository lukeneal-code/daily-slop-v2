import os
import tempfile

os.environ.setdefault("ENV", "local")
os.environ.setdefault("FAKE_LLM", "true")
os.environ.setdefault("ADMIN_DEV_TOKEN", "")
# Default to a user-writable temp dir so unit tests don't try to mkdir /var/slop.
os.environ.setdefault(
    "IMAGES_LOCAL_DIR", os.path.join(tempfile.gettempdir(), "slop-test-images")
)
os.environ.setdefault("IMAGES_PUBLIC_BASE_URL", "http://test/images")

from app.config import get_settings  # noqa: E402

# Drop any settings instance cached at import time so the env above takes effect.
get_settings.cache_clear()
