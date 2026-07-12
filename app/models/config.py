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


class RecheckerConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 5


class AllDebridInstanceConfig(BaseModel):
    name: str = ""
    api_key: str = ""
    enabled: bool = False
    library_roots: list[str] = []
    target_prefixes: list[str] = []
    min_age_hours: int = 24
    rate_limit: float = 0.2


class AllDebridConfig(BaseModel):
    instances: list[AllDebridInstanceConfig] = []
    auto_enabled: bool = False
    schedule_time: str = "03:00"


class AppConfig(BaseModel):
    radarr: RadarrConfig = RadarrConfig()
    sonarr: SonarrConfig = SonarrConfig()
    alldebrid: AllDebridConfig = AllDebridConfig()
    discord: DiscordConfig = DiscordConfig()
    defaults: DefaultsConfig = DefaultsConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    verifier: VerifierConfig = VerifierConfig()
    retryer: RetryerConfig = RetryerConfig()
    rechecker: RecheckerConfig = RecheckerConfig()
    browse_roots: list[str] = ["/home", "/mnt", "/data"]
