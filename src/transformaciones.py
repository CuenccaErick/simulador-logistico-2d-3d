"""
Transformaciones geométricas 2D y mapeo al espacio de pantalla.

Pipeline de visualización (de mundo a píxel):

    P_mundo (x, y)  ──rotación θ──▶  P_rot  ──traslación (tx, ty)──▶  P_vista
                     ──mapeo al cuarto cuadrante──▶  P_pantalla (sx, sy)

Espacio de mundo:   euclidiano, origen al centro, Y crece hacia ARRIBA.
Espacio pantalla:   cuarto cuadrante, origen (0,0) arriba-izquierda, Y crece hacia ABAJO,
                    solo coordenadas enteras positivas son visibles.
"""

import math
from typing import Tuple


# ---------------------------------------------------------------- Matrices 3x3
# Se usan coordenadas homogéneas [x, y, 1] para poder componer traslación y
# rotación como productos de matrices.

def matriz_traslacion(tx: float, ty: float):
    return [[1, 0, tx],
            [0, 1, ty],
            [0, 0, 1]]


def matriz_rotacion(theta_rad: float):
    c, s = math.cos(theta_rad), math.sin(theta_rad)
    return [[c, -s, 0],
            [s,  c, 0],
            [0,  0, 1]]


def multiplicar(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def aplicar(m, x: float, y: float) -> Tuple[float, float]:
    return (m[0][0] * x + m[0][1] * y + m[0][2],
            m[1][0] * x + m[1][1] * y + m[1][2])


# ------------------------------------------------- Formas directas (sin matriz)

def trasladar(x: int, y: int, tx: int, ty: int) -> Tuple[int, int]:
    """Traslación 'sumando los componentes': x' = x + tx, y' = y + ty."""
    return x + tx, y + ty


def rotar(x: float, y: float, theta_rad: float) -> Tuple[float, float]:
    """Rotación paramétrica alrededor del origen:
        x' = x·cosθ − y·senθ
        y' = x·senθ + y·cosθ
    """
    c, s = math.cos(theta_rad), math.sin(theta_rad)
    return x * c - y * s, x * s + y * c


def redondear(v: float) -> int:
    """Redondeo simétrico al entero más cercano (los píxeles son enteros)."""
    return int(math.floor(v + 0.5))


# ------------------------------------------------------------------ Cámara

class Camara:
    """
    Mantiene el estado de la vista: traslación (paneo), rotación y escala,
    y realiza el mapeo mundo ↔ pantalla.
    """

    def __init__(self, ancho: int, alto: int):
        self.ancho = ancho          # ancho del framebuffer en píxeles lógicos
        self.alto = alto
        self.tx = 0                 # traslación acumulada (enteros)
        self.ty = 0
        self.angulo_grados = 0.0    # rotación de la vista
        self.zoom = 1.0             # unidades de mundo → píxeles

    # -- controles
    def panear(self, dx: int, dy: int):
        self.tx, self.ty = trasladar(self.tx, self.ty, dx, dy)

    def rotar_vista(self, grados: float):
        self.angulo_grados = (self.angulo_grados + grados) % 360

    def reiniciar(self):
        self.tx = self.ty = 0
        self.angulo_grados = 0.0
        self.zoom = 1.0

    @property
    def theta(self) -> float:
        return math.radians(self.angulo_grados)

    def matriz_vista(self):
        """M = T(tx, ty) · R(θ) · S(zoom) — compuesta en coordenadas homogéneas."""
        s = [[self.zoom, 0, 0], [0, self.zoom, 0], [0, 0, 1]]
        return multiplicar(matriz_traslacion(self.tx, self.ty),
                           multiplicar(matriz_rotacion(self.theta), s))

    # -- mapeo
    def mundo_a_pantalla(self, x: float, y: float) -> Tuple[int, int]:
        """
        1) escala y rotación paramétrica,  2) traslación,
        3) mapeo al cuarto cuadrante:
               sx = ancho/2 + x'
               sy = alto/2  − y'     (se invierte Y)
        """
        xr, yr = rotar(x * self.zoom, y * self.zoom, self.theta)
        xv, yv = xr + self.tx, yr + self.ty
        sx = self.ancho // 2 + redondear(xv)
        sy = self.alto // 2 - redondear(yv)
        return sx, sy

    def pantalla_a_mundo(self, sx: float, sy: float) -> Tuple[float, float]:
        """Transformación inversa (útil para el cursor y para validar el isomorfismo)."""
        xv = sx - self.ancho // 2
        yv = self.alto // 2 - sy
        xr, yr = xv - self.tx, yv - self.ty
        x, y = rotar(xr, yr, -self.theta)
        return x / self.zoom, y / self.zoom

    def escalar_radio(self, r: float) -> int:
        return max(1, redondear(r * self.zoom))
