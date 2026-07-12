"""クラウドホスティング環境の判定"""

from __future__ import annotations

import os


def is_cloud_hosted() -> bool:
    """Streamlit Cloud / GitHub Actions など PC 外で動いているか"""
    return bool(
        os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"
        or os.environ.get("STREAMLIT_SHARING_MODE")
        or os.environ.get("GITHUB_ACTIONS")
        or os.environ.get("RENDER")
        or os.environ.get("RAILWAY_ENVIRONMENT")
    )
