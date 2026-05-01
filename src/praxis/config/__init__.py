"""Praxis config subsystem — public API."""

from .engagement import find_engagement, init_engagement, is_engagement
from .loader import (
    load_engagement_config,
    load_global_config,
    load_profile,
    resolve_model_config,
    save_global_config,
    save_profile,
)
from .models import (
    EngagementConfig,
    GlobalConfig,
    IntegrationConfig,
    LogLevel,
    Methodology,
    ModelConfig,
    ProfileConfig,
    Provider,
    WakeCycleConfig,
    WakeCycleMode,
)
from .profiles import (
    create_profile,
    delete_profile,
    get_active_profile_name,
    list_profiles,
)

__all__ = [
    # Models
    "EngagementConfig",
    "GlobalConfig",
    "IntegrationConfig",
    "LogLevel",
    "Methodology",
    "ModelConfig",
    "ProfileConfig",
    "Provider",
    "WakeCycleConfig",
    "WakeCycleMode",
    # Loader
    "load_engagement_config",
    "load_global_config",
    "load_profile",
    "resolve_model_config",
    "save_global_config",
    "save_profile",
    # Profiles
    "create_profile",
    "delete_profile",
    "get_active_profile_name",
    "list_profiles",
    # Engagement
    "find_engagement",
    "init_engagement",
    "is_engagement",
]
