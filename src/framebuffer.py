"""
Framebuffer: una matriz de píxeles lógicos (la "cuadrícula digital").

Es la única superficie de dibujo del programa. Los algoritmos de rasterización
devuelven listas de (x, y) y aquí se iluminan uno por uno. No se usan
primitivas de alto nivel (create_line, create_oval, etc.) para el mapa.
"""

from typing import Iterable, Tuple


class Framebuffer:
    def __init__(self, ancho: int, alto: int, fondo: str = "#0d1117"):
        self.ancho = ancho
        self.alto = alto
        self.fondo = fondo
        self.pixeles_dibujados = 0
        self.limpiar()

    def limpiar(self):
        self.buf = [[self.fondo] * self.ancho for _ in range(self.alto)]
        self.pixeles_dibujados = 0

    def en_rango(self, x: int, y: int) -> bool:
        """Recorte (scissor): solo el cuarto cuadrante visible 0≤x<ancho, 0≤y<alto."""
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def pixel(self, x: int, y: int, color: str):
        if 0 <= x < self.ancho and 0 <= y < self.alto:
            self.buf[y][x] = color
            self.pixeles_dibujados += 1

    def pixeles(self, puntos: Iterable[Tuple[int, int]], color: str):
        for (x, y) in puntos:
            self.pixel(x, y, color)

    def mezclar(self, puntos: Iterable[Tuple[int, int]], color: str, alfa: float):
        """Pinta con transparencia (para el relleno de las áreas de cobertura)."""
        cr, cg, cb = _hex_a_rgb(color)
        for (x, y) in puntos:
            if 0 <= x < self.ancho and 0 <= y < self.alto:
                br, bg, bb = _hex_a_rgb(self.buf[y][x])
                self.buf[y][x] = "#%02x%02x%02x" % (
                    int(br + (cr - br) * alfa),
                    int(bg + (cg - bg) * alfa),
                    int(bb + (cb - bb) * alfa))

    def como_cadena_tk(self) -> str:
        """Formato que entiende tkinter.PhotoImage.put: '{#c #c ...} {#c ...}'."""
        return " ".join("{" + " ".join(fila) + "}" for fila in self.buf)

    def guardar_ppm(self, ruta: str):
        """Exporta el framebuffer a imagen PPM (formato sin dependencias)."""
        with open(ruta, "wb") as f:
            f.write(b"P6 %d %d 255\n" % (self.ancho, self.alto))
            for fila in self.buf:
                f.write(bytes(v for c in fila for v in _hex_a_rgb(c)))


_cache = {}


def _hex_a_rgb(c: str):
    rgb = _cache.get(c)
    if rgb is None:
        rgb = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        _cache[c] = rgb
    return rgb
