"""
Algoritmos de rasterización de primitivas 2D.

Todos los algoritmos reciben coordenadas ENTERAS en espacio de pantalla
(cuarto cuadrante: origen en la esquina superior izquierda, Y crece hacia abajo)
y devuelven la lista de píxeles (x, y) que deben iluminarse.

- dda_linea:            Analizador Diferencial Digital (usa punto flotante, como referencia).
- bresenham_linea:      Algoritmo de Bresenham (solo sumas/restas de enteros).
- punto_medio_circulo:  Algoritmo del Punto Medio para circunferencias (solo enteros).
- relleno_circulo:      Relleno por tramos horizontales usando los puntos del Punto Medio.
"""

from typing import List, Tuple

Pixel = Tuple[int, int]


def dda_linea(x0: int, y0: int, x1: int, y1: int) -> List[Pixel]:
    """DDA: avanza 'pasos' veces sumando incrementos fraccionarios y redondea."""
    dx = x1 - x0
    dy = y1 - y0
    pasos = max(abs(dx), abs(dy))
    if pasos == 0:
        return [(x0, y0)]
    x_inc = dx / pasos
    y_inc = dy / pasos
    x, y = float(x0), float(y0)
    puntos = []
    for _ in range(pasos + 1):
        # floor(v + 0.5): redondeo "hacia arriba" en .5, igual en ambos sentidos
        puntos.append((int(x + 0.5) if x >= 0 else -int(-x + 0.5),
                       int(y + 0.5) if y >= 0 else -int(-y + 0.5)))
        x += x_inc
        y += y_inc
    return puntos


def bresenham_linea(x0: int, y0: int, x1: int, y1: int) -> List[Pixel]:
    """
    Bresenham generalizado para los 8 octantes.

    Se usa la forma con un único término de error e = dx - dy:
      - Si 2e > -dy  → se avanza en X  (e -= dy)
      - Si 2e <  dx  → se avanza en Y  (e += dx)
    Todas las operaciones son sumas, restas y un desplazamiento (×2) de enteros.
    """
    puntos = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        puntos.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = err << 1  # 2 * err sin multiplicación
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return puntos


def _ocho_simetricos(xc: int, yc: int, x: int, y: int) -> List[Pixel]:
    """Refleja un punto del segundo octante en los 8 octantes del círculo."""
    return [
        (xc + x, yc + y), (xc - x, yc + y),
        (xc + x, yc - y), (xc - x, yc - y),
        (xc + y, yc + x), (xc - y, yc + x),
        (xc + y, yc - x), (xc - y, yc - x),
    ]


def punto_medio_circulo(xc: int, yc: int, r: int) -> List[Pixel]:
    """
    Algoritmo del Punto Medio para circunferencias.

    Se calcula solo un octante (de x=0 hasta x=y) y se refleja en los otros 7.
    Parámetro de decisión inicial p0 = 1 - r.
      - p < 0  → el punto medio está dentro: siguiente píxel (x+1, y),   p += 2x + 3
      - p >= 0 → el punto medio está fuera:  siguiente píxel (x+1, y-1), p += 2(x - y) + 5
    """
    if r <= 0:
        return [(xc, yc)]
    puntos = []
    vistos = set()
    x, y = 0, r
    p = 1 - r
    while x <= y:
        for px in _ocho_simetricos(xc, yc, x, y):
            if px not in vistos:
                vistos.add(px)
                puntos.append(px)
        if p < 0:
            p += (x << 1) + 3
        else:
            p += ((x - y) << 1) + 5
            y -= 1
        x += 1
    return puntos


def relleno_circulo(xc: int, yc: int, r: int) -> List[Pixel]:
    """
    Relleno del área de cobertura: por cada fila 'y' se toma el ancho máximo
    que produjo el Punto Medio y se ilumina el tramo horizontal completo.
    """
    if r <= 0:
        return [(xc, yc)]
    ancho_por_fila = {}
    for (px, py) in punto_medio_circulo(xc, yc, r):
        dx = abs(px - xc)
        if dx > ancho_por_fila.get(py, -1):
            ancho_por_fila[py] = dx
    puntos = []
    for py, dx in ancho_por_fila.items():
        for px in range(xc - dx, xc + dx + 1):
            puntos.append((px, py))
    return puntos
