"""
Generador de un mundo pequeño y aleatorio: mini ciudades unidas por carreteras.

Cada semilla produce un mundo distinto:
  1. Un terreno pequeño con lomas suaves (fractal Diamond–Square, sin agua).
  2. Entre 5 y 8 mini ciudades en lugares al azar.
  3. Carreteras = aristas de la triangulación de Delaunay de las ciudades.
  4. Zonas = diagrama de Voronoi (a qué ciudad queda más cerca cada punto del terreno).
  5. Cada ciudad es un grupo de cajas (edificios) de alturas y colores al azar.
  6. Rutas aleatorias: se eligen dos ciudades y Dijkstra encuentra el camino más corto.

Coordenadas: X y Z en el piso, Y es la altura.
"""

import heapq
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from .fractales import diamond_square
from .geometria import aristas_delaunay, circuncentro, delaunay, sitio_mas_cercano

TAM = 240.0                                    # el terreno mide 240 × 240
COLORES_EDIFICIOS = ["#e8e2d5", "#d6c7a8", "#c9d6e3", "#f0c987", "#e7a988", "#b7c9a8", "#d9b3c9"]
COLORES_ZONA = ["#4f8cff", "#ff8a3d", "#b072ff", "#ff5fa2", "#2bb7a8", "#e8c33a", "#8a5a3c", "#ff4d4d"]
NOMBRES_ZONA = ["azul", "naranja", "morada", "rosa", "turquesa", "amarilla", "café", "roja"]


def color(hexa: str) -> Tuple[float, float, float]:
    return tuple(int(hexa[k:k + 2], 16) / 255 for k in (1, 3, 5))


@dataclass
class Mundo:
    semilla: int
    alturas: np.ndarray
    ciudades: List[Tuple[float, float]] = field(default_factory=list)
    carreteras: List[Tuple[int, int]] = field(default_factory=list)
    edificios: List[Tuple[float, float, float, float, float, int, int]] = field(default_factory=list)
    # (x, z, ancho, fondo, alto, índice de color, ciudad)

    def altura(self, x: float, z: float) -> float:
        """Altura del terreno en (x, z) por interpolación bilineal."""
        n = self.alturas.shape[0] - 1
        fx = min(max((x / TAM + 0.5) * n, 0), n - 1e-6)
        fz = min(max((z / TAM + 0.5) * n, 0), n - 1e-6)
        j, i = int(fx), int(fz)
        tx, tz = fx - j, fz - i
        h = self.alturas
        return float((h[i, j] * (1 - tx) + h[i, j + 1] * tx) * (1 - tz) +
                     (h[i + 1, j] * (1 - tx) + h[i + 1, j + 1] * tx) * tz)

    def largo(self, a: int, b: int) -> float:
        return math.dist(self.ciudades[a], self.ciudades[b])


def nuevo_mundo(semilla: int) -> Mundo:
    rnd = random.Random(semilla)

    # 1) lomas suaves: el mismo fractal, pero con poca altura (de 0 a 7 unidades)
    alturas = diamond_square(5, rugosidad=0.4, semilla=semilla) * 7
    m = Mundo(semilla, alturas)

    # 2) ciudades separadas al menos 45 unidades
    objetivo = rnd.randint(5, 8)
    for _ in range(600):
        if len(m.ciudades) == objetivo:
            break
        p = (rnd.uniform(-95, 95), rnd.uniform(-95, 95))
        if all(math.dist(p, c) > 45 for c in m.ciudades):
            m.ciudades.append(p)

    # 3) carreteras = triangulación de Delaunay (red sin cruces que une ciudades vecinas)
    m.carreteras = aristas_delaunay(delaunay(m.ciudades))
    if not m.carreteras:                                   # 2 ciudades o todas alineadas
        orden = sorted(range(len(m.ciudades)), key=lambda i: m.ciudades[i])
        m.carreteras = [(min(a, b), max(a, b)) for a, b in zip(orden, orden[1:])]

    # 5) mini ciudades: edificios en una cuadrícula de 5 × 5 lotes alrededor del centro
    for k, (cx, cz) in enumerate(m.ciudades):
        for gx in range(-2, 3):
            for gz in range(-2, 3):
                if (gx, gz) == (0, 0) or rnd.random() < 0.45:
                    continue                               # plaza central y lotes vacíos
                x, z = cx + gx * 7, cz + gz * 7
                centro = 1 - (abs(gx) + abs(gz)) / 4        # más altos hacia el centro
                alto = rnd.uniform(3, 6) + centro * rnd.uniform(4, 14)
                m.edificios.append((x, z, rnd.uniform(4, 5.5), rnd.uniform(4, 5.5), alto,
                                    rnd.randrange(len(COLORES_EDIFICIOS)), k))
    return m


# ----------------------------------------------------------------- Dijkstra

def ruta_mas_corta(m: Mundo, origen: int, destino: int) -> List[int]:
    """
    Dijkstra sobre la red de carreteras: siempre se expande la ciudad con menor
    distancia acumulada (cola de prioridad). Devuelve la lista de ciudades del camino.
    """
    vecinos: Dict[int, List[int]] = {i: [] for i in range(len(m.ciudades))}
    for a, b in m.carreteras:
        vecinos[a].append(b)
        vecinos[b].append(a)
    dist = {origen: 0.0}
    previo = {}
    cola = [(0.0, origen)]
    while cola:
        d, u = heapq.heappop(cola)
        if u == destino:
            break
        if d > dist.get(u, math.inf):
            continue
        for v in vecinos[u]:
            nd = d + m.largo(u, v)
            if nd < dist.get(v, math.inf):
                dist[v], previo[v] = nd, u
                heapq.heappush(cola, (nd, v))
    if destino not in dist:
        return []
    camino = [destino]
    while camino[-1] != origen:
        camino.append(previo[camino[-1]])
    return camino[::-1]


def viaje_aleatorio(m: Mundo, rnd: random.Random) -> List[int]:
    """Elige dos ciudades distintas al azar y devuelve el camino más corto entre ellas."""
    a, b = rnd.sample(range(len(m.ciudades)), 2)
    return ruta_mas_corta(m, a, b)


# ----------------------------------------------------------------- mallas para la GPU
# Formato de vértice: x, y, z,  nx, ny, nz,  r, g, b,  extra     (10 números)

def malla_terreno(m: Mundo) -> np.ndarray:
    """Triángulos de color plano; 'extra' = ciudad más cercana (para pintar las zonas de Voronoi)."""
    pasto = (color("#8cc66b"), color("#7fbb60"))
    n = m.alturas.shape[0]
    xs = np.linspace(-TAM / 2, TAM / 2, n)
    datos = []
    for i in range(n - 1):
        for j in range(n - 1):
            p = [(xs[j], m.alturas[i, j], xs[i]), (xs[j + 1], m.alturas[i, j + 1], xs[i]),
                 (xs[j], m.alturas[i + 1, j], xs[i + 1]), (xs[j + 1], m.alturas[i + 1, j + 1], xs[i + 1])]
            for tri in ((p[0], p[2], p[1]), (p[1], p[2], p[3])):
                a, b, c = (np.array(v) for v in tri)
                normal = np.cross(b - a, c - a)
                normal /= np.linalg.norm(normal)
                cx, cz = (a[0] + b[0] + c[0]) / 3, (a[2] + b[2] + c[2]) / 3
                zona = sitio_mas_cercano(cx, cz, m.ciudades)
                col = pasto[(i + j) % 2]
                for v in (a, b, c):
                    datos.extend([*v, *normal, *col, zona])
    return np.array(datos, dtype="f4")


def cinta(m: Mundo, puntos: List[Tuple[float, float]], ancho: float, elevar: float, col):
    """Cinta que sigue el terreno a lo largo de una polilínea; 'extra' = distancia recorrida."""
    datos, recorrido = [], 0.0
    for (x0, z0), (x1, z1) in zip(puntos, puntos[1:]):
        largo = math.hypot(x1 - x0, z1 - z0)
        if largo < 1e-6:
            continue
        nx, nz = -(z1 - z0) / largo * ancho / 2, (x1 - x0) / largo * ancho / 2
        pasos = max(1, int(largo / 4))
        for s in range(pasos):
            ta, tb = s / pasos, (s + 1) / pasos
            xa, za = x0 + (x1 - x0) * ta, z0 + (z1 - z0) * ta
            xb, zb = x0 + (x1 - x0) * tb, z0 + (z1 - z0) * tb
            ya, yb = m.altura(xa, za) + elevar, m.altura(xb, zb) + elevar
            va, vb = recorrido + largo * ta, recorrido + largo * tb
            q = [(xa - nx, ya, za - nz, va), (xa + nx, ya, za + nz, va),
                 (xb - nx, yb, zb - nz, vb), (xb + nx, yb, zb + nz, vb)]
            for k in (0, 2, 1, 1, 2, 3):
                x, y, z, v = q[k]
                datos.extend([x, y, z, 0, 1, 0, *col, v])
        recorrido += largo
    return np.array(datos, dtype="f4"), recorrido


def malla_carreteras(m: Mundo) -> np.ndarray:
    """Todas las carreteras; 'extra' = distancia desde la primera ciudad (para que crezcan)."""
    partes = [cinta(m, [m.ciudades[a], m.ciudades[b]], 4.5, 0.4, color("#5b5f66"))[0]
              for a, b in m.carreteras]
    return np.concatenate(partes) if partes else np.zeros(0, "f4")


# ----------------------------------------------------------------- algoritmos animados
# Líneas: x, y, z,  r, g, b,  aparece, desaparece      (8 números por vértice)

def _linea(m, a, b, elevar, col, aparece, desaparece, datos):
    largo = math.dist(a, b)
    pasos = max(1, int(largo / 4))
    previo = None
    for s in range(pasos + 1):
        x, z = a[0] + (b[0] - a[0]) * s / pasos, a[1] + (b[1] - a[1]) * s / pasos
        p = (x, m.altura(x, z) + elevar, z)
        if previo:
            datos.extend([*previo, *col, aparece, desaparece, *p, *col, aparece, desaparece])
        previo = p


def _circulo(m, centro, radio, elevar, col, aparece, desaparece, datos, lados=48):
    pts = [(centro[0] + radio * math.cos(2 * math.pi * k / lados),
            centro[1] + radio * math.sin(2 * math.pi * k / lados)) for k in range(lados + 1)]
    for a, b in zip(pts, pts[1:]):
        _linea(m, a, b, elevar, col, aparece, desaparece, datos)


def guion_delaunay(m: Mundo, inicio: float, paso: float = 0.8):
    """
    Bowyer–Watson paso a paso: en el paso k se ve la triangulación de las primeras k ciudades,
    y en amarillo el CÍRCULO VACÍO de cada triángulo nuevo (ninguna otra ciudad cae dentro).
    La triangulación final se queda un momento y luego la reemplazan las carreteras.
    Devuelve (líneas, tiempo en que termina).
    """
    blanco, amarillo = (1.0, 1.0, 1.0), (1.0, 0.85, 0.2)
    datos, t, anteriores = [], inicio, set()
    n = len(m.ciudades)
    for k in range(3, n + 1):
        tris = delaunay(m.ciudades[:k])
        fin = t + paso
        for tri in tris:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                _linea(m, m.ciudades[a], m.ciudades[b], 1.2, blanco, t, fin + (2.0 if k == n else 0), datos)
            if tri not in anteriores:                 # triángulo nuevo → mostrar su círculo vacío
                c = circuncentro(*(m.ciudades[i] for i in tri))
                if c:
                    r = math.dist(c, m.ciudades[tri[0]])
                    if r < 200:
                        _circulo(m, c, r, 1.6, amarillo, t, fin, datos)
        anteriores = set(tris)
        t = fin
    return np.array(datos, dtype="f4").reshape(-1) if datos else np.zeros(0, "f4"), t
