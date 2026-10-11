"""Version and deployment information returned by GET /info."""

import platform

from app.common.settings import BaseServiceSettings
from app.common.telemetry import is_telemetry_enabled


def build_info(settings: BaseServiceSettings) -> dict:
    return {
        "service": settings.otel_service_name,
        "version": settings.app_version,
        "git_sha": settings.git_sha,
        "build_time": settings.build_time,
        "environment": settings.environment,
        "region": settings.deployment_region,
        "python": platform.python_version(),
        "telemetry_enabled": is_telemetry_enabled(),
        "faults_enabled": settings.faults_enabled,
    }
