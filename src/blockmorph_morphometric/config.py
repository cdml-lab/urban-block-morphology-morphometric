"""Set and city configurations (YAML).

A *set* configuration (configs/sets/global.yaml, universal.yaml) names the
member cities in pooling order, the sampling-unit rule and the Track A
model settings. A *city* configuration (configs/cities/<id>.yaml) holds the
analysis CRS, the boundary recipe, the study-area clip, the building and
height sources and the street rule of one city.

Input files of a city are looked up in `<data_dir>/<city id>/` unless an
absolute path is given.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml
from blockmorph.params import Params

from .refine import RefineParams

SET_NAMES = ("three_cities", "thirteen_cities")
# names of the two sets in the study's private pipeline (its folders and decision record), used only to
# read that pipeline's outputs (reproduce.py); also accepted as aliases
STUDY_SET = {"three_cities": "GLOBAL", "thirteen_cities": "UNIVERSAL"}
ALIASES = {v.lower(): k for k, v in STUDY_SET.items()}


def set_name(name) -> str:
    """three_cities | thirteen_cities (also accepts GLOBAL / UNIVERSAL)."""
    n = str(name).strip().lower()
    return ALIASES.get(n, n)


def _range(v, default):
    if v is None:
        return tuple(default)
    if isinstance(v, dict):
        return tuple(range(int(v["from"]), int(v["to"]) + 1))
    return tuple(int(x) for x in v)


@dataclass
class ModelSettings:
    """Track A model settings of one set (study values in the YAML files)."""
    pca_components: int = 5
    pca_whiten: bool = True
    k_range_city: tuple = tuple(range(5, 16))
    k_range_pooled: tuple = tuple(range(5, 16))
    min_type_size: int = 12
    kmeans_n_init: int = 10
    random_state: int = 42
    stability_reps: int = 20

    @classmethod
    def from_dict(cls, d: dict | None) -> "ModelSettings":
        d = dict(d or {})
        m = cls()
        for k in ("pca_components", "min_type_size", "kmeans_n_init", "random_state",
                  "stability_reps"):
            if k in d:
                setattr(m, k, int(d[k]))
        if "pca_whiten" in d:
            m.pca_whiten = bool(d["pca_whiten"])
        m.k_range_city = _range(d.get("k_range_city"), m.k_range_city)
        m.k_range_pooled = _range(d.get("k_range_pooled"), m.k_range_pooled)
        return m

    def params(self, model: str = "city", base: Params | None = None) -> Params:
        """Core `Params` for a city model (`model="city"`) or the pooled
        model (`model="pooled"`). Everything else keeps the core defaults."""
        if model not in ("city", "pooled"):
            raise ValueError("model: city | pooled")
        return replace(base or Params(),
                       pca_components=self.pca_components, pca_whiten=self.pca_whiten,
                       k_range=self.k_range_city if model == "city" else self.k_range_pooled,
                       min_type_size=self.min_type_size, kmeans_n_init=self.kmeans_n_init,
                       random_state=self.random_state, stability_reps=self.stability_reps)


@dataclass
class CityConfig:
    id: str
    name: str
    crs: str
    sets: tuple
    boundary: dict
    study_area: dict
    buildings: dict
    heights: dict
    streets: dict
    credit: str = ""
    study: dict = field(default_factory=dict)        # recorded facts of the study run
    path: Path | None = None

    @classmethod
    def load(cls, path) -> "CityConfig":
        path = Path(path)
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(id=str(d["id"]), name=d["name"], crs=str(d["crs"]),
                   sets=tuple(set_name(s) for s in d.get("sets", ())), boundary=d.get("boundary", {}),
                   study_area=d.get("study_area", {}), buildings=d.get("buildings", {}),
                   heights=d.get("heights", {"policy": "none"}),
                   streets=d.get("streets", {"source": "osm"}),
                   credit=d.get("credit", ""), study=d.get("study", {}), path=path)

    # ------------------------------------------------------------ parameters
    @property
    def min_building_area_m2(self) -> float:
        return float(self.buildings.get("min_area_m2", 25.0))

    @property
    def max_height_m(self) -> float:
        return float(self.buildings.get("max_height_m", 260.0))

    @property
    def cut_all_roads(self) -> bool:
        return bool(self.streets.get("cut_all_roads", False))

    def params(self, base: Params | None = None) -> Params:
        """Core `Params` with this city's building filters."""
        return replace(base or Params(), min_building_area_m2=self.min_building_area_m2,
                       max_height_m=self.max_height_m)

    def file(self, rel, data_dir) -> str | None:
        """Absolute path of an input file of this city (None/'osm' pass through)."""
        if rel in (None, "", "osm"):
            return rel
        p = Path(rel)
        if p.is_absolute():
            return str(p)
        return str((Path(data_dir) / self.id / p).resolve())


@dataclass
class SetConfig:
    name: str
    title: str
    cities: list
    city_configs: dict
    model: ModelSettings
    refine: RefineParams | None
    descriptors: str = "morphometric46"
    data_dir: Path | None = None
    output_dir: Path | None = None
    path: Path | None = None

    @classmethod
    def load(cls, path, data_dir=None, output_dir=None) -> "SetConfig":
        path = Path(path)
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        name = set_name(d["set"])
        if name not in SET_NAMES:
            raise ValueError(f"set: one of {SET_NAMES}")
        if d.get("descriptors", "morphometric46") != "morphometric46":
            raise ValueError("the international sets use descriptors: morphometric46 only")
        base = path.parent
        cdir = (base / d.get("cities_dir", "../cities")).resolve()
        cities = [str(c) for c in d["cities"]]
        cc = {c: CityConfig.load(cdir / f"{c}.yaml") for c in cities}
        for c, cfg in cc.items():
            if name not in cfg.sets:
                raise ValueError(f"city {c} is not declared a member of set {name}")
        u = d.get("units", {}) or {}
        refine = RefineParams.from_dict(u.get("refinement_params")) \
            if u.get("refinement", False) else None
        dd = Path(data_dir) if data_dir else (base / d.get("data_dir", "../../data")).resolve()
        od = Path(output_dir) if output_dir else \
            (base / d.get("output_dir", f"../../outputs/{name}")).resolve()
        return cls(name=name, title=d.get("title", name), cities=cities, city_configs=cc,
                   model=ModelSettings.from_dict(d.get("model")), refine=refine,
                   data_dir=dd, output_dir=od, path=path)


def default_config_dir() -> Path:
    """configs/ of a source checkout (editable install)."""
    return Path(__file__).resolve().parents[2] / "configs"


def load_set(name_or_path, **kw) -> SetConfig:
    """`load_set("three_cities")`, `load_set("thirteen_cities")` or a path to a set YAML."""
    p = Path(str(name_or_path))
    if not p.suffix:
        p = default_config_dir() / "sets" / f"{set_name(name_or_path)}.yaml"
    return SetConfig.load(p, **kw)
