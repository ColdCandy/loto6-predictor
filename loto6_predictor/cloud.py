"""クラウドホスティング環境の判定"""

from __future__ import annotations

import os
from pathlib import Path


def is_cloud_hosted() -> bool:
    """Streamlit Cloud / GitHub Actions など PC 外で動いているか"""
    env_flags = (
        os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud",
        os.environ.get("STREAMLIT_SERVER_ENVIRONMENT") == "cloud",
        os.environ.get("STREAMLIT_SHARING_MODE") == "streamlit-cloud",
        bool(os.environ.get("STREAMLIT_SHARING_MODE")),
        os.environ.get("GITHUB_ACTIONS") == "true",
        bool(os.environ.get("RENDER")),
        bool(os.environ.get("RAILWAY_ENVIRONMENT")),
        os.environ.get("IS_STREAMLIT_CLOUD") == "true",
    )
    if any(env_flags):
        return True

    cwd = Path.cwd().as_posix()
    script = Path(__file__).resolve().as_posix()
    if "/mount/src/" in cwd or "/mount/src/" in script:
        return True

    return False
