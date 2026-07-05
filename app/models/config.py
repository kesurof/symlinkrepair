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


class AppConfig(BaseModel):
    radarr: RadarrConfig = RadarrConfig()
    sonarr: SonarrConfig = SonarrConfig()
    discord: DiscordConfig = DiscordConfig()
    defaults: DefaultsConfig = DefaultsConfig()
    browse_roots: list[str] = ["/mnt", "/data"]
