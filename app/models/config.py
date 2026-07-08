from pydantic import BaseModel


class RadarrConfig(BaseModel):
    url: str = ""
    api_key: str = ""
    container: str = "radarr"
    library_roots: list[str] = []
    target_prefixes: list[str] = []


class SonarrConfig(BaseModel):
    url: str = ""
    api_key: str = ""
    container: str = "sonarr"
    library_roots: list[str] = []
    target_prefixes: list[str] = []


class DiscordConfig(BaseModel):
    enabled: bool = False
    webhook: str = ""


class DefaultsConfig(BaseModel):
    limit: int = 50
    rescan: bool = True
    search: bool = True
    keep_symlinks: bool = False


class SchedulerConfig(BaseModel):
    radarr_enabled: bool = False
    radarr_interval_hours: int = 3
    sonarr_enabled: bool = False
    sonarr_interval_hours: int = 3


class VerifierConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 1
    max_duration_minutes: int = 30


class RetryerConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 30
    max_daily_retries: int = 6


class AppConfig(BaseModel):
    radarr: RadarrConfig = RadarrConfig()
    sonarr: SonarrConfig = SonarrConfig()
    discord: DiscordConfig = DiscordConfig()
    defaults: DefaultsConfig = DefaultsConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    verifier: VerifierConfig = VerifierConfig()
    retryer: RetryerConfig = RetryerConfig()
    browse_roots: list[str] = ["/home", "/mnt", "/data"]
