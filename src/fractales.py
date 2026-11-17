"""
Fractal Diamond–Square (desplazamiento del punto medio en 2D) para las lomas del terreno 3D.
"""

import numpy as np


# ------------------------------------------------------------ Diamond–Square

def diamond_square(n: int, rugosidad: float = 0.55, semilla: int = 7) -> np.ndarray:
    """
    Genera un mapa de alturas de (2ⁿ + 1) × (2ⁿ + 1).

    Cada iteración divide los cuadrados a la mitad:
      * Paso DIAMANTE: el centro de cada cuadrado = promedio de sus 4 esquinas + ruido.
      * Paso CUADRADO: el punto medio de cada lado = promedio de sus 4 vecinos en rombo + ruido.
      * La amplitud del ruido se multiplica por 2^(−H) en cada nivel, con H = 2·(1 − rugosidad):
        rugosidad baja → el ruido se apaga rápido (colinas suaves);
        rugosidad alta → los detalles finos conservan fuerza (terreno escarpado).
        Cada escala repite el mismo proceso que la anterior: el terreno es AUTOSIMILAR (fractal).
    Devuelve valores normalizados a [0, 1].
    """
    rng = np.random.default_rng(semilla)
    tam = 2 ** n + 1
    h = np.zeros((tam, tam), dtype=np.float64)
    h[0, 0], h[0, -1], h[-1, 0], h[-1, -1] = rng.uniform(-1, 1, 4)
    paso = tam - 1
    amplitud = 1.0
    factor = 2.0 ** (-2 * (1 - rugosidad))    # rugosidad 0.5 → amplitud a la mitad por nivel

    while paso > 1:
        mitad = paso // 2
        # --- diamante: centros de los cuadrados
        esquinas = (h[0:-1:paso, 0:-1:paso] + h[paso::paso, 0:-1:paso] +
                    h[0:-1:paso, paso::paso] + h[paso::paso, paso::paso]) / 4
        h[mitad::paso, mitad::paso] = esquinas + rng.uniform(-amplitud, amplitud, esquinas.shape)

        # --- cuadrado: puntos medios de las aristas (vecinos en forma de rombo)
        for y in range(0, tam, mitad):
            x0 = mitad if (y // mitad) % 2 == 0 else 0
            xs = np.arange(x0, tam, paso)
            if xs.size == 0:
                continue
            suma = np.zeros(xs.size)
            cuenta = np.zeros(xs.size)
            for dy, dx in ((-mitad, 0), (mitad, 0), (0, -mitad), (0, mitad)):
                yy, xx = y + dy, xs + dx
                if 0 <= yy < tam:
                    ok = (xx >= 0) & (xx < tam)
                    suma[ok] += h[yy, xx[ok]]
                    cuenta[ok] += 1
            h[y, xs] = suma / cuenta + rng.uniform(-amplitud, amplitud, xs.size)

        paso = mitad
        amplitud *= factor

    h -= h.min()
    h /= h.max() or 1
    return h
