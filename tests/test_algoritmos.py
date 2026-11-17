"""
Validación matemática del simulador (Semanas 9–10 del cronograma).

Ejecutar desde la raíz del proyecto:   python -m unittest -v
"""

import math
import os
import random
import tempfile
import unittest

from src.framebuffer import Framebuffer
from src.modelo import Almacen, Destino, Escenario, Ruta
from src.rasterizacion import (bresenham_linea, dda_linea, punto_medio_circulo,
                               relleno_circulo)
from src.render import OpcionesRender, renderizar
from src.transformaciones import (Camara, aplicar, matriz_rotacion, matriz_traslacion,
                                  multiplicar, rotar, trasladar)

random.seed(2026)


def es_conexa_8(puntos):
    """Cada píxel consecutivo debe ser vecino-8 del anterior (sin huecos)."""
    return all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1 for a, b in zip(puntos, puntos[1:]))


class TestBresenham(unittest.TestCase):
    def test_extremos_incluidos(self):
        for _ in range(500):
            x0, y0, x1, y1 = (random.randint(-200, 200) for _ in range(4))
            pts = bresenham_linea(x0, y0, x1, y1)
            self.assertEqual(pts[0], (x0, y0))
            self.assertEqual(pts[-1], (x1, y1))

    def test_numero_de_pixeles(self):
        """Una línea rasterizada tiene exactamente max(|dx|,|dy|)+1 píxeles."""
        for _ in range(500):
            x0, y0, x1, y1 = (random.randint(-200, 200) for _ in range(4))
            pts = bresenham_linea(x0, y0, x1, y1)
            self.assertEqual(len(pts), max(abs(x1 - x0), abs(y1 - y0)) + 1)

    def test_conectividad_8_octantes(self):
        for _ in range(500):
            pts = bresenham_linea(*(random.randint(-150, 150) for _ in range(4)))
            self.assertTrue(es_conexa_8(pts))

    def test_solo_enteros(self):
        for p in bresenham_linea(3, 7, 91, -40):
            self.assertIsInstance(p[0], int)
            self.assertIsInstance(p[1], int)

    def test_error_maximo_medio_pixel(self):
        """Ningún píxel se aleja más de 0.5 (en el eje menor) de la recta ideal."""
        for _ in range(300):
            x0, y0, x1, y1 = (random.randint(-150, 150) for _ in range(4))
            if (x0, y0) == (x1, y1):
                continue
            for (x, y) in bresenham_linea(x0, y0, x1, y1):
                if abs(x1 - x0) >= abs(y1 - y0):
                    y_ideal = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                    self.assertLessEqual(abs(y - y_ideal), 0.5 + 1e-9)
                else:
                    x_ideal = x0 + (x1 - x0) * (y - y0) / (y1 - y0)
                    self.assertLessEqual(abs(x - x_ideal), 0.5 + 1e-9)

    def test_casos_especiales(self):
        self.assertEqual(bresenham_linea(5, 5, 5, 5), [(5, 5)])
        self.assertEqual(bresenham_linea(0, 0, 4, 0), [(i, 0) for i in range(5)])
        self.assertEqual(bresenham_linea(0, 0, 0, -3), [(0, -i) for i in range(4)])
        self.assertEqual(bresenham_linea(0, 0, 3, 3), [(i, i) for i in range(4)])

    def test_ejemplo_de_clase(self):
        """Ejemplo clásico (Hearn & Baker): de (20,10) a (30,18)."""
        esperado = [(20, 10), (21, 11), (22, 12), (23, 12), (24, 13), (25, 14),
                    (26, 15), (27, 16), (28, 16), (29, 17), (30, 18)]
        self.assertEqual(bresenham_linea(20, 10, 30, 18), esperado)


class TestDDA(unittest.TestCase):
    def test_extremos_y_longitud(self):
        for _ in range(300):
            x0, y0, x1, y1 = (random.randint(-150, 150) for _ in range(4))
            pts = dda_linea(x0, y0, x1, y1)
            self.assertEqual(pts[0], (x0, y0))
            self.assertEqual(pts[-1], (x1, y1))
            self.assertEqual(len(pts), max(abs(x1 - x0), abs(y1 - y0)) + 1)
            self.assertTrue(es_conexa_8(pts))

    def test_dda_y_bresenham_casi_coinciden(self):
        """Ambos producen la misma cantidad de píxeles y difieren a lo más en empates de redondeo."""
        total = difer = 0
        for _ in range(300):
            c = [random.randint(-150, 150) for _ in range(4)]
            a, b = set(dda_linea(*c)), set(bresenham_linea(*c))
            total += len(b)
            difer += len(a - b)
        self.assertLess(difer / total, 0.10)


class TestPuntoMedio(unittest.TestCase):
    def test_puntos_sobre_la_circunferencia(self):
        """Todo píxel cumple |√(x²+y²) − r| < 1 (error de rasterización acotado)."""
        for r in range(1, 120):
            for (x, y) in punto_medio_circulo(0, 0, r):
                self.assertLess(abs(math.hypot(x, y) - r), 1.0)

    def test_simetria_de_ocho_octantes(self):
        for r in (5, 17, 40, 99):
            pts = set(punto_medio_circulo(0, 0, r))
            for (x, y) in pts:
                for s in [(-x, y), (x, -y), (-x, -y), (y, x), (-y, x), (y, -x), (-y, -x)]:
                    self.assertIn(s, pts)

    def test_puntos_cardinales(self):
        r = 25
        pts = set(punto_medio_circulo(10, -4, r))
        for p in [(10 + r, -4), (10 - r, -4), (10, -4 + r), (10, -4 - r)]:
            self.assertIn(p, pts)

    def test_sin_duplicados(self):
        pts = punto_medio_circulo(0, 0, 30)
        self.assertEqual(len(pts), len(set(pts)))

    def test_relleno_dentro_del_radio(self):
        r = 30
        area = relleno_circulo(0, 0, r)
        self.assertEqual(len(area), len(set(area)))
        for (x, y) in area:
            self.assertLess(math.hypot(x, y), r + 1)
        # el área aproximada se parece a π r²
        self.assertAlmostEqual(len(area) / (math.pi * r * r), 1.0, delta=0.08)


class TestTransformaciones(unittest.TestCase):
    def test_traslacion_suma_componentes(self):
        self.assertEqual(trasladar(3, -4, 10, 20), (13, 16))

    def test_rotacion_90(self):
        x, y = rotar(1, 0, math.pi / 2)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 1)

    def test_rotacion_conserva_distancia(self):
        for _ in range(200):
            x, y = random.uniform(-100, 100), random.uniform(-100, 100)
            t = random.uniform(-math.pi, math.pi)
            self.assertAlmostEqual(math.hypot(*rotar(x, y, t)), math.hypot(x, y))

    def test_matrices_homogeneas_equivalen_a_formulas(self):
        m = multiplicar(matriz_traslacion(15, -7), matriz_rotacion(math.radians(30)))
        x, y = aplicar(m, 4, 9)
        xr, yr = rotar(4, 9, math.radians(30))
        self.assertAlmostEqual(x, xr + 15)
        self.assertAlmostEqual(y, yr - 7)

    def test_mapeo_cuarto_cuadrante(self):
        cam = Camara(320, 200)
        self.assertEqual(cam.mundo_a_pantalla(0, 0), (160, 100))      # origen al centro
        self.assertEqual(cam.mundo_a_pantalla(10, 0), (170, 100))     # +X a la derecha
        self.assertEqual(cam.mundo_a_pantalla(0, 10), (160, 90))      # +Y hacia ARRIBA
        self.assertEqual(cam.mundo_a_pantalla(-160, 100), (0, 0))     # esquina sup. izq.

    def test_isomorfismo_ida_y_vuelta(self):
        """mundo → pantalla → mundo recupera el punto (error < 1 píxel por redondeo)."""
        cam = Camara(320, 214)
        for _ in range(300):
            cam.tx, cam.ty = random.randint(-80, 80), random.randint(-80, 80)
            cam.angulo_grados = random.uniform(-180, 180)
            cam.zoom = random.choice([0.5, 1, 2])
            x, y = random.randint(-150, 150), random.randint(-150, 150)
            sx, sy = cam.mundo_a_pantalla(x, y)
            xr, yr = cam.pantalla_a_mundo(sx, sy)
            self.assertLess(math.hypot(xr - x, yr - y), 1.0 / cam.zoom)

    def test_matriz_vista_coincide_con_pipeline(self):
        cam = Camara(300, 200)
        cam.tx, cam.ty, cam.angulo_grados, cam.zoom = 12, -30, 47, 1.5
        m = cam.matriz_vista()
        for (x, y) in [(0, 0), (10, 5), (-40, 33)]:
            xv, yv = aplicar(m, x, y)
            esperado = (150 + int(math.floor(xv + 0.5)), 100 - int(math.floor(yv + 0.5)))
            self.assertEqual(cam.mundo_a_pantalla(x, y), esperado)


class TestModeloYRender(unittest.TestCase):
    def escenario(self):
        return Escenario(
            almacenes=[Almacen("A", 0, 0, 30)],
            destinos=[Destino("dentro", 10, 10), Destino("fuera", 50, 0)],
            rutas=[Ruta("R1", 0, 0, 30, 40)])

    def test_distancia_y_cobertura(self):
        e = self.escenario()
        self.assertEqual(e.rutas[0].distancia, 50.0)
        self.assertEqual(e.destinos_cubiertos(), ["dentro"])

    def test_json_ida_y_vuelta(self):
        e = self.escenario()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "esc.json")
            e.guardar(p)
            self.assertEqual(Escenario.cargar(p).a_dict(), e.a_dict())

    def test_render_sin_interfaz(self):
        fb = Framebuffer(200, 150)
        cam = Camara(200, 150)
        res = renderizar(fb, cam, self.escenario(), OpcionesRender())
        self.assertGreater(res.pixeles, 0)
        self.assertEqual(res.pixeles_por_ruta["R1"], 41)  # max(30,40)+1
        # el píxel del destino final de la ruta quedó iluminado con el color de la ruta
        sx, sy = cam.mundo_a_pantalla(30, 40)
        self.assertEqual(fb.buf[sy][sx], "#39d353")

    def test_render_capas_delaunay_voronoi(self):
        esc = self.escenario()
        esc.almacenes.append(Almacen("B", 60, 20, 25))
        fb, cam = Framebuffer(200, 150), Camara(200, 150)
        base = renderizar(fb, cam, esc, OpcionesRender()).pixeles
        con = renderizar(fb, cam, esc, OpcionesRender(delaunay=True, voronoi=True)).pixeles
        self.assertGreater(con, base)
        # la mediatriz entre A(0,0) y B(60,20) pasa por el punto medio (30,10)
        sx, sy = cam.mundo_a_pantalla(30, 10)
        cerca = [fb.buf[y][x] for y in range(sy - 1, sy + 2) for x in range(sx - 1, sx + 2)]
        self.assertIn("#e3b341", cerca)

    def test_recorte_fuera_de_pantalla(self):
        fb = Framebuffer(50, 50)
        fb.pixeles(bresenham_linea(-100, -100, 200, 200), "#ffffff")
        self.assertEqual(fb.pixeles_dibujados, 50)   # solo la diagonal visible


if __name__ == "__main__":
    unittest.main()
