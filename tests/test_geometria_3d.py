"""
Pruebas de la parte nueva: Delaunay, Voronoi, Liang–Barsky, fractales, matrices 3D y terreno.

Ejecutar desde la raíz:   python -m unittest -v
(Las pruebas que usan numpy se omiten si numpy no está instalado.)
"""

import math
import random
import unittest

from src.geometria import (aristas_delaunay, circuncentro, delaunay, en_circuncirculo,
                           orientacion, recortar_liang_barsky, sitio_mas_cercano, voronoi_aristas)

try:
    import numpy as np
    HAY_NUMPY = True
except ImportError:
    HAY_NUMPY = False

random.seed(2026)


def envolvente_convexa(puntos):
    """Cadena monótona de Andrew (solo para verificar Delaunay)."""
    p = sorted(set(puntos))
    if len(p) < 3:
        return p
    inf, sup = [], []
    for q in p:
        while len(inf) >= 2 and orientacion(inf[-2], inf[-1], q) <= 0:
            inf.pop()
        inf.append(q)
    for q in reversed(p):
        while len(sup) >= 2 and orientacion(sup[-2], sup[-1], q) <= 0:
            sup.pop()
        sup.append(q)
    return inf[:-1] + sup[:-1]


def area(poligono):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poligono, poligono[1:] + poligono[:1]))) / 2


def nube(n):
    return [(random.uniform(-150, 150), random.uniform(-100, 100)) for _ in range(n)]


class TestDelaunay(unittest.TestCase):
    def test_circulo_vacio(self):
        """Propiedad que define a Delaunay: ningún punto cae dentro del círculo circunscrito."""
        for _ in range(20):
            pts = nube(40)
            for t in delaunay(pts):
                a, b, c = (pts[k] for k in t)
                for i, p in enumerate(pts):
                    if i not in t:
                        self.assertFalse(en_circuncirculo(p, a, b, c))

    def test_cubre_la_envolvente_convexa(self):
        """La suma de áreas de los triángulos es el área de la envolvente convexa."""
        for _ in range(20):
            pts = nube(50)
            suma = sum(abs(orientacion(*(pts[k] for k in t))) / 2 for t in delaunay(pts))
            self.assertAlmostEqual(suma, area(envolvente_convexa(pts)), delta=1e-6 * suma)

    def test_formula_de_euler(self):
        """Con h puntos en la envolvente: triángulos = 2n − 2 − h  y  aristas = 3n − 3 − h."""
        for _ in range(20):
            pts = nube(35)
            tris = delaunay(pts)
            h = len(envolvente_convexa(pts))
            self.assertEqual(len(tris), 2 * len(pts) - 2 - h)
            self.assertEqual(len(aristas_delaunay(tris)), 3 * len(pts) - 3 - h)

    def test_orientacion_antihoraria(self):
        pts = nube(30)
        for t in delaunay(pts):
            self.assertGreater(orientacion(*(pts[k] for k in t)), 0)

    def test_casos_degenerados(self):
        self.assertEqual(delaunay([(0, 0), (1, 1)]), [])
        self.assertEqual(delaunay([(0, 0), (1, 1), (2, 2), (3, 3)]), [])   # colineales
        self.assertEqual(len(delaunay([(0, 0), (4, 0), (0, 3)])), 1)


class TestVoronoi(unittest.TestCase):
    CAJA = (-200, -200, 200, 200)

    def test_vertices_equidistantes(self):
        """Cada circuncentro (vértice de Voronoi) está a la misma distancia de los 3 sitios."""
        pts = nube(20)
        for t in delaunay(pts):
            c = circuncentro(*(pts[k] for k in t))
            d = [math.dist(c, pts[k]) for k in t]
            self.assertAlmostEqual(d[0], d[1], places=6)
            self.assertAlmostEqual(d[0], d[2], places=6)

    def test_aristas_separan_a_los_dos_mas_cercanos(self):
        """Sobre cualquier punto de una arista de Voronoi, los 2 sitios más cercanos empatan."""
        for _ in range(10):
            sitios = nube(8)
            for (a, b) in voronoi_aristas(sitios, self.CAJA):
                for t in (0.25, 0.5, 0.75):
                    p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    d = sorted(math.dist(p, s) for s in sitios)
                    self.assertAlmostEqual(d[0], d[1], delta=1e-6 * max(1, d[0]))

    def test_aristas_dentro_de_la_caja(self):
        for (a, b) in voronoi_aristas(nube(10), self.CAJA):
            for p in (a, b):
                self.assertTrue(-200 - 1e-9 <= p[0] <= 200 + 1e-9 and -200 - 1e-9 <= p[1] <= 200 + 1e-9)

    def test_dos_sitios_mediatriz(self):
        (a, b), = voronoi_aristas([(0, 0), (10, 0)], self.CAJA)
        self.assertAlmostEqual(a[0], 5)
        self.assertAlmostEqual(b[0], 5)

    def test_sitio_mas_cercano(self):
        self.assertEqual(sitio_mas_cercano(9, 1, [(0, 0), (10, 0), (5, 9)]), 1)


class TestLiangBarsky(unittest.TestCase):
    CAJA = (0, 0, 10, 10)

    def test_dentro_sin_cambios(self):
        self.assertEqual(recortar_liang_barsky((1, 1), (9, 5), self.CAJA), ((1, 1), (9, 5)))

    def test_fuera(self):
        self.assertIsNone(recortar_liang_barsky((-5, -5), (-1, 20), self.CAJA))
        self.assertIsNone(recortar_liang_barsky((11, 0), (11, 10), self.CAJA))

    def test_cruza(self):
        (a, b) = recortar_liang_barsky((-10, 5), (20, 5), self.CAJA)
        self.assertAlmostEqual(a[0], 0)
        self.assertAlmostEqual(b[0], 10)
        (a, b) = recortar_liang_barsky((-5, -5), (15, 15), self.CAJA)
        self.assertAlmostEqual(a[0], 0)
        self.assertAlmostEqual(b[1], 10)


@unittest.skipUnless(HAY_NUMPY, "requiere numpy")
class TestFractales(unittest.TestCase):
    def test_diamond_square(self):
        from src.fractales import diamond_square
        h = diamond_square(6, 0.55, 1)
        self.assertEqual(h.shape, (65, 65))
        self.assertAlmostEqual(float(h.min()), 0.0)
        self.assertAlmostEqual(float(h.max()), 1.0)
        self.assertTrue(np.array_equal(h, diamond_square(6, 0.55, 1)))      # misma semilla
        self.assertFalse(np.array_equal(h, diamond_square(6, 0.55, 2)))     # otra semilla

    def test_rugosidad_controla_el_detalle(self):
        """Más rugosidad = más variación entre vecinos (más 'arrugado')."""
        from src.fractales import diamond_square
        liso = np.abs(np.diff(diamond_square(7, 0.25, 5), axis=1)).mean()
        rugoso = np.abs(np.diff(diamond_square(7, 0.85, 5), axis=1)).mean()
        self.assertGreater(rugoso, liso)


@unittest.skipUnless(HAY_NUMPY, "requiere numpy")
class TestMatrices3D(unittest.TestCase):
    def test_perspectiva_cerca_y_lejos(self):
        from src.matrices3d import perspectiva
        P = perspectiva(60, 16 / 9, 1.0, 100.0)
        for z, esperado in ((-1.0, -1.0), (-100.0, 1.0)):
            c = P @ np.array([0, 0, z, 1.0])
            self.assertAlmostEqual(c[2] / c[3], esperado)

    def test_perspectiva_reduce_lo_lejano(self):
        from src.matrices3d import perspectiva
        P = perspectiva(60, 1, 1, 100)
        cerca = P @ np.array([1, 0, -5, 1.0])
        lejos = P @ np.array([1, 0, -50, 1.0])
        self.assertGreater(cerca[0] / cerca[3], lejos[0] / lejos[3])

    def test_mirar_a(self):
        from src.matrices3d import mirar_a
        V = mirar_a((10, 20, 30), (0, 0, 0))
        self.assertTrue(np.allclose(V @ np.array([10, 20, 30, 1.0]), [0, 0, 0, 1]))   # ojo → origen
        p = V @ np.array([0, 0, 0, 1.0])                                            # objetivo → −Z
        self.assertAlmostEqual(p[0], 0)
        self.assertAlmostEqual(p[1], 0)
        self.assertLess(p[2], 0)
        R = V[:3, :3]
        self.assertTrue(np.allclose(R @ R.T, np.eye(3)))                            # ortonormal

    def test_rotaciones(self):
        from src.matrices3d import rot_y
        p = rot_y(math.pi / 2) @ np.array([1, 0, 0, 1.0])
        self.assertTrue(np.allclose(p, [0, 0, -1, 1]))


@unittest.skipUnless(HAY_NUMPY, "requiere numpy")
class TestMundoAleatorio(unittest.TestCase):
    def test_misma_semilla_mismo_mundo(self):
        from src.mundo3d import nuevo_mundo
        a, b = nuevo_mundo(123), nuevo_mundo(123)
        self.assertEqual(a.ciudades, b.ciudades)
        self.assertEqual(a.edificios, b.edificios)
        self.assertNotEqual(a.ciudades, nuevo_mundo(124).ciudades)

    def test_ciudades_separadas_y_carreteras_de_delaunay(self):
        from src.mundo3d import nuevo_mundo
        for s in range(20):
            m = nuevo_mundo(s)
            self.assertGreaterEqual(len(m.ciudades), 5)
            for i, a in enumerate(m.ciudades):
                for b in m.ciudades[i + 1:]:
                    self.assertGreater(math.dist(a, b), 45)
            self.assertEqual(m.carreteras, aristas_delaunay(delaunay(m.ciudades)))

    def test_dijkstra_es_el_camino_mas_corto(self):
        """Se compara Dijkstra contra probar TODOS los caminos posibles (fuerza bruta)."""
        from src.mundo3d import nuevo_mundo, ruta_mas_corta
        for s in range(10):
            m = nuevo_mundo(s)
            vecinos = {i: set() for i in range(len(m.ciudades))}
            for a, b in m.carreteras:
                vecinos[a].add(b)
                vecinos[b].add(a)

            def mejor(u, destino, visitados):
                if u == destino:
                    return 0.0
                return min((m.largo(u, v) + mejor(v, destino, visitados | {v})
                            for v in vecinos[u] if v not in visitados), default=math.inf)

            for origen in range(len(m.ciudades)):
                for destino in range(len(m.ciudades)):
                    if origen != destino:
                        camino = ruta_mas_corta(m, origen, destino)
                        largo = sum(m.largo(a, b) for a, b in zip(camino, camino[1:]))
                        self.assertEqual(camino[0], origen)
                        self.assertEqual(camino[-1], destino)
                        self.assertAlmostEqual(largo, mejor(origen, destino, {origen}))

    def test_guion_bowyer_watson(self):
        """Un paso por ciudad a partir de la tercera; los círculos (amarillos) solo duran un paso."""
        from src.mundo3d import guion_delaunay, nuevo_mundo
        m = nuevo_mundo(42)
        lineas, fin = guion_delaunay(m, inicio=3.0, paso=0.5)
        self.assertAlmostEqual(fin, 3.0 + 0.5 * (len(m.ciudades) - 2))
        v = lineas.reshape(-1, 8)
        amarillas = v[v[:, 5] < 0.5]
        self.assertTrue(len(amarillas) > 0)
        self.assertTrue(np.allclose(amarillas[:, 7] - amarillas[:, 6], 0.5))

    def test_edificios_en_su_ciudad(self):
        from src.mundo3d import nuevo_mundo
        m = nuevo_mundo(5)
        for x, z, *_, ciudad in m.edificios:
            self.assertLessEqual(math.dist((x, z), m.ciudades[ciudad]), 2 * 7 * math.sqrt(2) + 1e-9)


if __name__ == "__main__":
    unittest.main()
