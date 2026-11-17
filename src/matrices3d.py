"""
Transformaciones 3D propias (coordenadas homogéneas 4×4, convención columna: p' = M · p).

OpenGL solo recibe las matrices ya calculadas; toda la matemática de cámara,
proyección en perspectiva y modelado de objetos está aquí.
"""

import math

import numpy as np


def identidad() -> np.ndarray:
    return np.eye(4, dtype=np.float64)


def traslacion(tx: float, ty: float, tz: float) -> np.ndarray:
    m = identidad()
    m[:3, 3] = (tx, ty, tz)
    return m


def escala(sx: float, sy: float, sz: float) -> np.ndarray:
    return np.diag([sx, sy, sz, 1.0])


def rot_x(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=np.float64)


def rot_y(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=np.float64)


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float64)


def perspectiva(fovy_grados: float, aspecto: float, cerca: float, lejos: float) -> np.ndarray:
    """
    Proyección en perspectiva (la de gluPerspective).
    Lleva el frustum a un cubo [-1, 1]³ (NDC); después OpenGL divide entre w,
    y eso es lo que hace que lo lejano se vea más pequeño.

          | f/a  0        0                0          |
          | 0    f        0                0          |      f = 1 / tan(fovy/2)
          | 0    0  (l+c)/(c−l)     2·l·c/(c−l)       |
          | 0    0       −1                0          |
    """
    f = 1.0 / math.tan(math.radians(fovy_grados) / 2)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspecto
    m[1, 1] = f
    m[2, 2] = (lejos + cerca) / (cerca - lejos)
    m[2, 3] = 2 * lejos * cerca / (cerca - lejos)
    m[3, 2] = -1.0
    return m


def mirar_a(ojo, objetivo, arriba=(0.0, 1.0, 0.0)) -> np.ndarray:
    """
    Matriz de vista (la de gluLookAt): base ortonormal de la cámara con
    producto cruz, y traslación del ojo al origen.
        f = normalizar(objetivo − ojo)   (hacia adelante)
        s = normalizar(f × arriba)       (derecha)
        u = s × f                        (arriba real)
    """
    ojo = np.asarray(ojo, dtype=np.float64)
    f = np.asarray(objetivo, dtype=np.float64) - ojo
    f /= np.linalg.norm(f)
    s = np.cross(f, arriba)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = identidad()
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = (-s @ ojo, -u @ ojo, f @ ojo)
    return m


def a_gl(m: np.ndarray) -> bytes:
    """OpenGL guarda las matrices por columnas: se transpone antes de enviarlas."""
    return np.ascontiguousarray(m.T, dtype="f4").tobytes()


def instancia(m: np.ndarray) -> np.ndarray:
    """Las 16 componentes de una matriz de modelo por columnas (para instanciado)."""
    return m.T.reshape(-1)
