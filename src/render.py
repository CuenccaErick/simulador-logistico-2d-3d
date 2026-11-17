"""
Renderizador: convierte el escenario (espacio de mundo) en píxeles del framebuffer
(espacio de pantalla) usando exclusivamente los algoritmos de rasterización propios.

No depende de Tkinter, por lo que puede usarse sin interfaz (pruebas, exportar imagen).
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .framebuffer import Framebuffer
from .geometria import aristas_delaunay, delaunay, voronoi_aristas
from .modelo import Escenario
from .rasterizacion import (bresenham_linea, dda_linea, punto_medio_circulo,
                            relleno_circulo)
from .transformaciones import Camara, redondear

# Paleta (lienzo oscuro, píxeles "iluminados")
COLOR_FONDO = "#0d1117"
COLOR_REJILLA = "#161b22"
COLOR_REJILLA_MAYOR = "#21262d"
COLOR_EJE_X = "#8b2f3c"
COLOR_EJE_Y = "#2f6f8b"
COLOR_COBERTURA = "#58a6ff"
COLOR_ALMACEN = "#f0b429"
COLOR_DESTINO_OK = "#3fb950"
COLOR_DESTINO_NO = "#f85149"
COLOR_VEHICULO = "#ffffff"
COLOR_DIFERENCIA = "#ff00ff"
COLOR_PREVIEW = "#8b949e"
COLOR_DELAUNAY = "#6e7681"
COLOR_VORONOI = "#e3b341"


@dataclass
class OpcionesRender:
    algoritmo: str = "bresenham"          # "bresenham" | "dda"
    rejilla: bool = True
    paso_rejilla: int = 20                # unidades de mundo
    rellenar_cobertura: bool = True
    mostrar_diferencias: bool = False     # píxeles donde DDA y Bresenham difieren
    delaunay: bool = False                # triangulación de almacenes + destinos
    voronoi: bool = False                 # zonas de servicio de cada almacén
    progreso_vehiculos: float = -1.0      # 0..1, negativo = sin vehículos
    preview: Tuple[int, int, int, int] = None  # ruta en construcción (mundo)


@dataclass
class Etiqueta:
    x: int
    y: int
    texto: str
    color: str


@dataclass
class ResultadoRender:
    pixeles: int = 0
    ms: float = 0.0
    pixeles_por_ruta: Dict[str, int] = field(default_factory=dict)
    etiquetas: List[Etiqueta] = field(default_factory=list)
    diferencias: int = 0


def _linea(alg: str):
    return bresenham_linea if alg == "bresenham" else dda_linea


def _limites_mundo(cam: Camara):
    """Caja envolvente, en mundo, de lo que se ve en pantalla (considerando la rotación)."""
    esquinas = [cam.pantalla_a_mundo(0, 0), cam.pantalla_a_mundo(cam.ancho, 0),
                cam.pantalla_a_mundo(0, cam.alto), cam.pantalla_a_mundo(cam.ancho, cam.alto)]
    xs = [p[0] for p in esquinas]
    ys = [p[1] for p in esquinas]
    return min(xs), max(xs), min(ys), max(ys)


def dibujar_rejilla(fb: Framebuffer, cam: Camara, paso: int):
    xmin, xmax, ymin, ymax = _limites_mundo(cam)
    paso = max(5, paso)
    k0, k1 = math.floor(xmin / paso), math.ceil(xmax / paso)
    for k in range(k0, k1 + 1):
        x = k * paso
        a = cam.mundo_a_pantalla(x, ymin)
        b = cam.mundo_a_pantalla(x, ymax)
        color = COLOR_EJE_Y if x == 0 else (COLOR_REJILLA_MAYOR if k % 5 == 0 else COLOR_REJILLA)
        fb.pixeles(bresenham_linea(*a, *b), color)
    k0, k1 = math.floor(ymin / paso), math.ceil(ymax / paso)
    for k in range(k0, k1 + 1):
        y = k * paso
        a = cam.mundo_a_pantalla(xmin, y)
        b = cam.mundo_a_pantalla(xmax, y)
        color = COLOR_EJE_X if y == 0 else (COLOR_REJILLA_MAYOR if k % 5 == 0 else COLOR_REJILLA)
        fb.pixeles(bresenham_linea(*a, *b), color)


def _flecha(fb, cam, ruta, linea, color):
    """Punta de flecha en el destino: dos segmentos a ±150° del rumbo (ya rotado por la vista)."""
    sx, sy = cam.mundo_a_pantalla(ruta.x1, ruta.y1)
    ang = math.radians(ruta.rumbo_grados) + cam.theta
    largo = 5
    for d in (math.radians(150), math.radians(-150)):
        ex = sx + redondear(largo * math.cos(ang + d))
        ey = sy - redondear(largo * math.sin(ang + d))
        fb.pixeles(linea(sx, sy, ex, ey), color)


def _marcador_cuadrado(fb, sx, sy, m, color):
    esq = [(sx - m, sy - m), (sx + m, sy - m), (sx + m, sy + m), (sx - m, sy + m)]
    for i in range(4):
        fb.pixeles(bresenham_linea(*esq[i], *esq[(i + 1) % 4]), color)
    for yy in range(sy - 1, sy + 2):
        for xx in range(sx - 1, sx + 2):
            fb.pixel(xx, yy, color)


def _marcador_rombo(fb, sx, sy, m, color):
    v = [(sx, sy - m), (sx + m, sy), (sx, sy + m), (sx - m, sy)]
    for i in range(4):
        fb.pixeles(bresenham_linea(*v[i], *v[(i + 1) % 4]), color)
    fb.pixel(sx, sy, color)


def renderizar(fb: Framebuffer, cam: Camara, esc: Escenario,
               op: OpcionesRender) -> ResultadoRender:
    t0 = time.perf_counter()
    res = ResultadoRender()
    fb.limpiar()
    linea = _linea(op.algoritmo)

    # 1) Rejilla y ejes cartesianos
    if op.rejilla:
        dibujar_rejilla(fb, cam, op.paso_rejilla)

    # 2) Áreas de cobertura (Punto Medio)
    for a in esc.almacenes:
        cx, cy = cam.mundo_a_pantalla(a.x, a.y)
        r = cam.escalar_radio(a.radio_cobertura)
        if op.rellenar_cobertura:
            fb.mezclar(relleno_circulo(cx, cy, r), COLOR_COBERTURA, 0.12)
        fb.pixeles(punto_medio_circulo(cx, cy, r), COLOR_COBERTURA)

    # 2b) Voronoi de los almacenes (zonas de servicio) y Delaunay de todos los puntos
    if op.voronoi and len(esc.almacenes) >= 2:
        xmin, xmax, ymin, ymax = _limites_mundo(cam)
        sitios = [(a.x, a.y) for a in esc.almacenes]
        for (p0, p1) in voronoi_aristas(sitios, (xmin, ymin, xmax, ymax)):
            a = cam.mundo_a_pantalla(*p0)
            b = cam.mundo_a_pantalla(*p1)
            pts = bresenham_linea(*a, *b)
            fb.pixeles([q for i, q in enumerate(pts) if i % 4 != 3], COLOR_VORONOI)  # discontinua
    if op.delaunay:
        puntos = [(a.x, a.y) for a in esc.almacenes] + [(d.x, d.y) for d in esc.destinos]
        for i, j in aristas_delaunay(delaunay(puntos)):
            a = cam.mundo_a_pantalla(*puntos[i])
            b = cam.mundo_a_pantalla(*puntos[j])
            fb.pixeles(bresenham_linea(*a, *b)[::2], COLOR_DELAUNAY)               # punteada

    # 3) Rutas (Bresenham o DDA)
    trayectorias = []
    for ruta in esc.rutas:
        p0 = cam.mundo_a_pantalla(ruta.x0, ruta.y0)
        p1 = cam.mundo_a_pantalla(ruta.x1, ruta.y1)
        pts = linea(*p0, *p1)
        fb.pixeles(pts, ruta.color)
        _flecha(fb, cam, ruta, linea, ruta.color)
        res.pixeles_por_ruta[ruta.nombre] = len(pts)
        trayectorias.append(pts)
        if op.mostrar_diferencias:
            otra = dda_linea if op.algoritmo == "bresenham" else bresenham_linea
            dif = set(otra(*p0, *p1)) - set(pts)
            fb.pixeles(dif, COLOR_DIFERENCIA)
            res.diferencias += len(dif)

    if op.preview:
        x0, y0, x1, y1 = op.preview
        p0 = cam.mundo_a_pantalla(x0, y0)
        p1 = cam.mundo_a_pantalla(x1, y1)
        pts = linea(*p0, *p1)
        fb.pixeles(pts[::2], COLOR_PREVIEW)   # línea punteada

    # 4) Almacenes y destinos (marcadores vectoriales trazados con Bresenham)
    cubiertos = set(esc.destinos_cubiertos())
    for a in esc.almacenes:
        sx, sy = cam.mundo_a_pantalla(a.x, a.y)
        _marcador_cuadrado(fb, sx, sy, 3, COLOR_ALMACEN)
        res.etiquetas.append(Etiqueta(sx, sy - 6, a.nombre, COLOR_ALMACEN))
    for d in esc.destinos:
        sx, sy = cam.mundo_a_pantalla(d.x, d.y)
        col = COLOR_DESTINO_OK if d.nombre in cubiertos else COLOR_DESTINO_NO
        _marcador_rombo(fb, sx, sy, 3, col)
        res.etiquetas.append(Etiqueta(sx, sy - 6, d.nombre, col))

    # 5) Vehículos: avanzan píxel a píxel sobre la trayectoria rasterizada
    if op.progreso_vehiculos >= 0:
        for pts in trayectorias:
            if not pts:
                continue
            i = min(len(pts) - 1, int(op.progreso_vehiculos * (len(pts) - 1)))
            vx, vy = pts[i]
            for yy in range(vy - 1, vy + 2):
                for xx in range(vx - 1, vx + 2):
                    fb.pixel(xx, yy, COLOR_VEHICULO)

    res.pixeles = fb.pixeles_dibujados
    res.ms = (time.perf_counter() - t0) * 1000
    return res
