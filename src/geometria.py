"""
Geometría computacional del simulador (implementaciones propias, solo biblioteca estándar):

- Triangulación de Delaunay por el algoritmo incremental de Bowyer–Watson.
- Diagrama de Voronoi como dual de Delaunay (circuncentros de triángulos vecinos).
- Recorte de segmentos contra un rectángulo con Liang–Barsky.

Uso en el proyecto:
  * Delaunay sobre almacenes + destinos = red de "carreteras candidatas" (une cada punto
    con sus vecinos naturales, sin cruces).
  * Voronoi sobre los almacenes = zonas de servicio: cada punto del mapa pertenece al
    almacén más cercano.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

Punto = Tuple[float, float]
Triangulo = Tuple[int, int, int]
Segmento = Tuple[Punto, Punto]


# ------------------------------------------------------------------ utilidades

def orientacion(a: Punto, b: Punto, c: Punto) -> float:
    """> 0 si a→b→c gira a la izquierda (antihorario), < 0 a la derecha, 0 colineales."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def circuncentro(a: Punto, b: Punto, c: Punto) -> Optional[Punto]:
    """Centro de la circunferencia que pasa por a, b y c (None si son colineales)."""
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    a2 = a[0] ** 2 + a[1] ** 2
    b2 = b[0] ** 2 + b[1] ** 2
    c2 = c[0] ** 2 + c[1] ** 2
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    return ux, uy


def en_circuncirculo(p: Punto, a: Punto, b: Punto, c: Punto) -> bool:
    """
    Prueba del círculo circunscrito con el determinante clásico:

        | ax-px  ay-py  (ax-px)²+(ay-py)² |
        | bx-px  by-py  (bx-px)²+(by-py)² |  > 0   ⇔  p está dentro (si a,b,c es antihorario)
        | cx-px  cy-py  (cx-px)²+(cy-py)² |
    """
    if orientacion(a, b, c) < 0:
        b, c = c, b
    adx, ady = a[0] - p[0], a[1] - p[1]
    bdx, bdy = b[0] - p[0], b[1] - p[1]
    cdx, cdy = c[0] - p[0], c[1] - p[1]
    det = ((adx * adx + ady * ady) * (bdx * cdy - cdx * bdy)
           - (bdx * bdx + bdy * bdy) * (adx * cdy - cdx * ady)
           + (cdx * cdx + cdy * cdy) * (adx * bdy - bdx * ady))
    return det > 1e-9


# ------------------------------------------------------------------ Delaunay

def delaunay(puntos: Sequence[Punto]) -> List[Triangulo]:
    """
    Bowyer–Watson:
      1. Se crea un "súper-triángulo" que contiene todos los puntos.
      2. Se inserta cada punto: los triángulos cuyo círculo circunscrito lo contiene
         ya no son válidos (forman una "cavidad" poligonal).
      3. Se borran y se re-triangula la cavidad uniendo su contorno con el punto nuevo.
      4. Al final se descartan los triángulos que usan vértices del súper-triángulo.
    Devuelve triángulos como índices (i, j, k) sobre `puntos`, en sentido antihorario.
    Complejidad: O(n²) en el peor caso (suficiente para decenas o cientos de puntos).
    """
    n = len(puntos)
    if n < 3:
        return []
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    # El súper-triángulo debe ser MUY grande: si es chico, sus vértices caen dentro del
    # círculo de algún triángulo delgado de la orilla y ese triángulo se pierde
    # (las pruebas lo detectaron con un factor de 20; con 10⁴ pasan 3 000 casos aleatorios).
    d = max(maxx - minx, maxy - miny, 1.0) * 10000
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    pts = list(puntos) + [(cx - d, cy - d), (cx + d, cy - d), (cx, cy + d)]
    triangulos = [(n, n + 1, n + 2)]

    for i in range(n):
        p = pts[i]
        malos = [t for t in triangulos if en_circuncirculo(p, pts[t[0]], pts[t[1]], pts[t[2]])]
        # Contorno de la cavidad = aristas que pertenecen a un solo triángulo "malo"
        conteo: Dict[Tuple[int, int], int] = {}
        for t in malos:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                k = (min(a, b), max(a, b))
                conteo[k] = conteo.get(k, 0) + 1
        malos_set = set(malos)
        triangulos = [t for t in triangulos if t not in malos_set]
        for t in malos:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                if conteo[(min(a, b), max(a, b))] == 1:
                    nuevo = (a, b, i)
                    if orientacion(pts[a], pts[b], pts[i]) < 0:
                        nuevo = (b, a, i)
                    triangulos.append(nuevo)

    return [t for t in triangulos if max(t) < n and abs(orientacion(*(pts[k] for k in t))) > 1e-12]


def aristas_delaunay(triangulos: List[Triangulo]) -> List[Tuple[int, int]]:
    """Aristas únicas (i < j) de la triangulación."""
    s = set()
    for t in triangulos:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            s.add((min(a, b), max(a, b)))
    return sorted(s)


# ------------------------------------------------------------------ recorte

def recortar_liang_barsky(p0: Punto, p1: Punto, caja) -> Optional[Segmento]:
    """
    Recorte paramétrico de Liang–Barsky. El segmento es P(t) = p0 + t·(p1 − p0), t∈[0,1].
    Para cada borde se calcula pₖ y qₖ; se ajustan t_entrada y t_salida.
    caja = (xmin, ymin, xmax, ymax). Devuelve el tramo visible o None.
    """
    xmin, ymin, xmax, ymax = caja
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - xmin), (dx, xmax - p0[0]), (-dy, p0[1] - ymin), (dy, ymax - p0[1])):
        if abs(p) < 1e-15:
            if q < 0:
                return None          # paralelo y fuera
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    return ((p0[0] + t0 * dx, p0[1] + t0 * dy), (p0[0] + t1 * dx, p0[1] + t1 * dy))


# ------------------------------------------------------------------ Voronoi

def voronoi_aristas(sitios: Sequence[Punto], caja) -> List[Segmento]:
    """
    Diagrama de Voronoi como dual de Delaunay:
      * Cada triángulo de Delaunay aporta un vértice de Voronoi: su circuncentro.
      * Si dos triángulos comparten una arista, sus circuncentros se unen (arista finita).
      * Si una arista está en la envolvente convexa (un solo triángulo), sale un rayo
        desde el circuncentro, perpendicular a la arista y hacia afuera.
    Todo se recorta a `caja` con Liang–Barsky.
    """
    n = len(sitios)
    xmin, ymin, xmax, ymax = caja
    lejos = 4 * max(xmax - xmin, ymax - ymin)
    if n < 2:
        return []
    tris = delaunay(sitios)
    segmentos: List[Segmento] = []

    if not tris:
        # Puntos colineales (o solo 2): las celdas están separadas por mediatrices paralelas
        orden = sorted(range(n), key=lambda i: (sitios[i][0], sitios[i][1]))
        for a, b in zip(orden, orden[1:]):
            (ax, ay), (bx, by) = sitios[a], sitios[b]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx, dy = -(by - ay), bx - ax
            L = math.hypot(dx, dy) or 1
            dx, dy = dx / L * lejos, dy / L * lejos
            s = recortar_liang_barsky((mx - dx, my - dy), (mx + dx, my + dy), caja)
            if s:
                segmentos.append(s)
        return segmentos

    centros = [circuncentro(*(sitios[k] for k in t)) for t in tris]
    arista_a_tris: Dict[Tuple[int, int], List[int]] = {}
    for ti, t in enumerate(tris):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            arista_a_tris.setdefault((min(a, b), max(a, b)), []).append(ti)

    for (a, b), ts in arista_a_tris.items():
        if len(ts) == 2:
            c0, c1 = centros[ts[0]], centros[ts[1]]
            if c0 and c1:
                s = recortar_liang_barsky(c0, c1, caja)
                if s:
                    segmentos.append(s)
        else:
            t = tris[ts[0]]
            c = centros[ts[0]]
            if c is None:
                continue
            otro = [k for k in t if k not in (a, b)][0]
            (ax, ay), (bx, by), (ox, oy) = sitios[a], sitios[b], sitios[otro]
            # normal a la arista que apunta lejos del tercer vértice
            nx, ny = -(by - ay), bx - ax
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if nx * (ox - mx) + ny * (oy - my) > 0:
                nx, ny = -nx, -ny
            L = math.hypot(nx, ny) or 1
            fin = (c[0] + nx / L * lejos, c[1] + ny / L * lejos)
            s = recortar_liang_barsky(c, fin, caja)
            if s:
                segmentos.append(s)
    return segmentos


def sitio_mas_cercano(x: float, y: float, sitios: Sequence[Punto]) -> int:
    """Definición directa de Voronoi: índice del sitio más cercano a (x, y)."""
    mejor, dmin = -1, float("inf")
    for i, (sx, sy) in enumerate(sitios):
        d = (x - sx) ** 2 + (y - sy) ** 2
        if d < dmin:
            mejor, dmin = i, d
    return mejor
