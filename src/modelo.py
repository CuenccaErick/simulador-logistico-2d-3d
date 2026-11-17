"""
Modelo de datos del escenario logístico (independiente de la interfaz).
Las coordenadas de todas las entidades están en el ESPACIO DE MUNDO (euclidiano).
"""

import json
import math
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Almacen:
    nombre: str
    x: int
    y: int
    radio_cobertura: int = 40   # en unidades de mundo


@dataclass
class Destino:
    nombre: str
    x: int
    y: int


@dataclass
class Ruta:
    nombre: str
    x0: int
    y0: int
    x1: int
    y1: int
    color: str = "#39d353"

    @property
    def distancia(self) -> float:
        """Distancia euclidiana  d = √((x1−x0)² + (y1−y0)²)."""
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def rumbo_grados(self) -> float:
        """Ángulo de la ruta respecto al eje +X (sentido antihorario)."""
        return math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0)) % 360


@dataclass
class Escenario:
    almacenes: List[Almacen] = field(default_factory=list)
    destinos: List[Destino] = field(default_factory=list)
    rutas: List[Ruta] = field(default_factory=list)

    def destinos_cubiertos(self):
        """Destinos que caen dentro de al menos un radio de cobertura (x²+y² ≤ r²)."""
        cubiertos = []
        for d in self.destinos:
            for a in self.almacenes:
                if (d.x - a.x) ** 2 + (d.y - a.y) ** 2 <= a.radio_cobertura ** 2:
                    cubiertos.append(d.nombre)
                    break
        return cubiertos

    def limpiar(self):
        self.almacenes.clear()
        self.destinos.clear()
        self.rutas.clear()

    # ------------------------------------------------ persistencia JSON
    def a_dict(self):
        return {"almacenes": [asdict(a) for a in self.almacenes],
                "destinos": [asdict(d) for d in self.destinos],
                "rutas": [asdict(r) for r in self.rutas]}

    def guardar(self, ruta_archivo: str):
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def desde_dict(cls, d):
        return cls(almacenes=[Almacen(**a) for a in d.get("almacenes", [])],
                   destinos=[Destino(**x) for x in d.get("destinos", [])],
                   rutas=[Ruta(**r) for r in d.get("rutas", [])])

    @classmethod
    def cargar(cls, ruta_archivo: str):
        with open(ruta_archivo, encoding="utf-8") as f:
            return cls.desde_dict(json.load(f))
