"""
Vista 3D: un mundo pequeño y aleatorio que se dibuja solo, con figuras básicas (cajas).

  Paso 1  Aparece el terreno (lomas suaves de un fractal Diamond–Square).
  Paso 2  Aparecen las ciudades (postes de color).
  Paso 3  Delaunay (Bowyer–Watson) ciudad por ciudad, con el CÍRCULO VACÍO de cada triángulo nuevo.
  Paso 4  Voronoi: el terreno se pinta con el color de la ciudad más cercana.
  Paso 5  Las aristas de Delaunay se vuelven carreteras.
  Paso 6  Crecen los edificios de cada mini ciudad.
  Paso 7  Rutas aleatorias: Dijkstra elige el camino más corto y un auto lo recorre.

Teclas: Espacio = otro mundo · A = mundos automáticos · P = captura · Esc = salir.
Ratón: arrastrar = girar · rueda = acercar.
"""

import math
import os
import random
import time

import numpy as np

try:
    import moderngl
    import pygame
except ImportError as ex:
    raise SystemExit("La vista 3D necesita numpy, moderngl y pygame-ce:\n"
                     "    pip install -r requirements.txt\n" + str(ex))

from . import matrices3d as M
from .mundo3d import (COLORES_EDIFICIOS, COLORES_ZONA, NOMBRES_ZONA, cinta, color, guion_delaunay,
                      malla_carreteras, malla_terreno, nuevo_mundo, viaje_aleatorio)

ZONAS = [color(c) for c in COLORES_ZONA]
NARANJA = color("#ff7a1a")

# ------------------------------------------------------------------ shaders
# Una sola luz para todo:  color · (0.5 + 0.55 · max(0, n·l))   (Lambert + ambiente)
LUZ = """
vec3 iluminar(vec3 c, vec3 n) {
    float difusa = max(dot(normalize(n), normalize(vec3(0.4, 1.0, 0.3))), 0.0);
    return c * (0.5 + 0.55 * difusa);
}
"""

MALLA_VS = """
#version 330
in vec3 in_pos; in vec3 in_normal; in vec3 in_color; in float in_extra;
uniform mat4 vp; uniform float crecer;
out vec3 v_normal; out vec3 v_color; out float v_extra;
void main() {
    vec3 p = vec3(in_pos.x, in_pos.y * crecer, in_pos.z);
    v_normal = in_normal; v_color = in_color; v_extra = in_extra;
    gl_Position = vp * vec4(p, 1.0);
}
"""

MALLA_FS = """
#version 330
in vec3 v_normal; in vec3 v_color; in float v_extra;
uniform int modo;               // 0 = terreno, 1 = carretera o ruta
uniform float avance;           // carreteras y rutas: hasta qué distancia ya se dibujaron
uniform float zona_mezcla;      // terreno: cuánto se pinta con el color de su zona de Voronoi
uniform vec3 zonas[8];
out vec4 color;
""" + LUZ + """
void main() {
    vec3 c = v_color;
    if (modo == 0) c = mix(c, zonas[int(v_extra + 0.5)], zona_mezcla);
    if (modo == 1 && v_extra > avance) discard;
    color = vec4(iluminar(c, v_normal), 1.0);
}
"""

CAJA_VS = """
#version 330
in vec3 in_pos; in vec3 in_normal;
in vec4 m0; in vec4 m1; in vec4 m2; in vec4 m3; in vec3 in_color; in float in_retraso;
uniform mat4 vp; uniform float tiempo;
out vec3 v_normal; out vec3 v_color;
void main() {
    mat4 m = mat4(m0, m1, m2, m3);
    float s = smoothstep(in_retraso, in_retraso + 0.6, tiempo);     // crece desde su base
    vec3 base = m3.xyz;
    vec3 p = base + ((m * vec4(in_pos, 1.0)).xyz - base) * s;
    v_normal = mat3(m) * in_normal; v_color = in_color;
    gl_Position = vp * vec4(p, 1.0);
}
"""

CAJA_FS = """
#version 330
in vec3 v_normal; in vec3 v_color;
out vec4 color;
""" + LUZ + """
void main() { color = vec4(iluminar(v_color, v_normal), 1.0); }
"""

LINEA_VS = """
#version 330
in vec3 in_pos; in vec3 in_color; in vec2 in_ventana;
uniform mat4 vp; uniform float tiempo;
out vec3 v_color; out float v_visible;
void main() {
    v_color = in_color;
    v_visible = step(in_ventana.x, tiempo) * step(tiempo, in_ventana.y);
    gl_Position = vp * vec4(in_pos, 1.0);
}
"""

LINEA_FS = """
#version 330
in vec3 v_color; in float v_visible;
out vec4 color;
void main() { if (v_visible < 0.5) discard; color = vec4(v_color, 1.0); }
"""

TEXTO_VS = """
#version 330
in vec2 in_pos; in vec2 in_uv; out vec2 v_uv;
void main() { v_uv = in_uv; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

TEXTO_FS = """
#version 330
in vec2 v_uv; uniform sampler2D tex; out vec4 color;
void main() { color = texture(tex, v_uv); }
"""


def cubo() -> np.ndarray:
    """36 vértices (posición + normal) de un cubo de lado 1 apoyado en y = 0."""
    datos = []
    for eje in range(3):
        for signo in (1, -1):
            n = np.zeros(3); n[eje] = signo
            u = np.zeros(3); u[(eje + 1) % 3] = 1
            v = np.cross(n, u)
            c = n * 0.5 + np.array([0, 0.5, 0])
            esquinas = [c - u / 2 - v / 2, c + u / 2 - v / 2, c + u / 2 + v / 2, c - u / 2 + v / 2]
            for k in (0, 1, 2, 0, 2, 3):
                datos.extend([*esquinas[k], *n])
    return np.array(datos, dtype="f4")


class Vista3D:
    def __init__(self, ancho=1280, alto=720, semilla=None):
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.set_mode((ancho, alto), pygame.OPENGL | pygame.DOUBLEBUF)
        self.ancho, self.alto = ancho, alto
        ctx = self.ctx = moderngl.create_context()
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.fuente = pygame.font.SysFont("consolas,dejavusansmono,menlo,monospace", 20, bold=True)

        self.p_malla = ctx.program(vertex_shader=MALLA_VS, fragment_shader=MALLA_FS)
        self.p_caja = ctx.program(vertex_shader=CAJA_VS, fragment_shader=CAJA_FS)
        self.p_linea = ctx.program(vertex_shader=LINEA_VS, fragment_shader=LINEA_FS)
        self.p_texto = ctx.program(vertex_shader=TEXTO_VS, fragment_shader=TEXTO_FS)
        self.vbo_cubo = ctx.buffer(cubo().tobytes())
        self.tex_texto = ctx.texture((ancho, 60), 4)
        y0 = 1 - 120 / alto
        q = np.array([-1, y0, 0, 0, 1, y0, 1, 0, 1, 1, 1, 1, -1, y0, 0, 0, 1, 1, 1, 1, -1, 1, 0, 1], "f4")
        self.vao_texto = ctx.vertex_array(self.p_texto, [(ctx.buffer(q.tobytes()), "2f 2f", "in_pos", "in_uv")])
        self.vbo_auto = ctx.buffer(reserve=4 * 21 * 4, dynamic=True)
        self.vao_auto = self._vao_cajas_con(self.vbo_auto)

        self.yaw, self.pitch, self.dist = 0.7, 0.75, 270.0
        self.automatico = True
        self.texto_actual = None
        self.crear_mundo(semilla if semilla is not None else random.randrange(100000))

    # ------------------------------------------------------------ utilidades GPU
    def _vao_malla(self, datos):
        return self.ctx.vertex_array(self.p_malla, [(self.ctx.buffer(datos.tobytes()), "3f 3f 3f 1f",
                                                     "in_pos", "in_normal", "in_color", "in_extra")])

    def _vao_cajas_con(self, vbo):
        return self.ctx.vertex_array(self.p_caja, [(self.vbo_cubo, "3f 3f", "in_pos", "in_normal"),
                                                   (vbo, "4f 4f 4f 4f 3f 1f/i", "m0", "m1", "m2", "m3",
                                                    "in_color", "in_retraso")])

    # ------------------------------------------------------------ mundo nuevo
    def crear_mundo(self, semilla):
        m = self.mundo = nuevo_mundo(semilla)
        self.rnd = random.Random(semilla)
        self.tiempo = 0.0
        self.vao_terreno = self._vao_malla(malla_terreno(m))
        self.vao_carreteras = self._vao_malla(malla_carreteras(m))

        # guion de la animación (segundos)
        self.t_ciudades = 1.5
        self.t_delaunay = 2.8
        lineas, fin_delaunay = guion_delaunay(m, inicio=self.t_delaunay, paso=0.8)
        self.t_voronoi = fin_delaunay
        self.t_carreteras = fin_delaunay + 1.2
        self.t_edificios = self.t_carreteras + 2.0
        self.t_viajes = self.t_edificios + 2.5 + 0.3 * len(m.ciudades)
        self.vao_lineas = self.ctx.vertex_array(
            self.p_linea, [(self.ctx.buffer(lineas.tobytes()), "3f 3f 2f", "in_pos", "in_color", "in_ventana")])

        # cajas: torre de color en el centro de cada ciudad + edificios
        inst = []
        for k, (x, z) in enumerate(m.ciudades):
            matriz = M.traslacion(x, m.altura(x, z), z) @ M.escala(3, 26, 3)
            inst.append(np.concatenate([M.instancia(matriz), ZONAS[k % 8], [self.t_ciudades + 0.12 * k]]))
        for (x, z, ancho, fondo, alto, c, ciudad) in m.edificios:
            matriz = M.traslacion(x, m.altura(x, z) - 0.5, z) @ M.escala(ancho, alto, fondo)
            retraso = self.t_edificios + 0.3 * ciudad + self.rnd.uniform(0, 0.5)
            inst.append(np.concatenate([M.instancia(matriz), color(COLORES_EDIFICIOS[c]), [retraso]]))
        datos = np.array(inst, "f4")
        self.vao_cajas = self._vao_cajas_con(self.ctx.buffer(datos.tobytes()))
        self.n_cajas = len(datos)

        self.viaje = None
        self.viajes_hechos = 0
        pygame.display.set_caption(f"Mundo #{semilla} · {len(m.ciudades)} ciudades · Espacio = otro mundo")

    def nuevo_viaje(self):
        """Ruta aleatoria: Dijkstra entre dos ciudades al azar; la ruta se dibuja y un auto la sigue."""
        camino = viaje_aleatorio(self.mundo, self.rnd)
        puntos = [self.mundo.ciudades[i] for i in camino]
        datos, largo = cinta(self.mundo, puntos, 2.2, 0.55, NARANJA)
        self.viaje = {"camino": camino, "puntos": puntos, "largo": largo, "inicio": self.tiempo,
                      "vao": self._vao_malla(datos)}

    # ------------------------------------------------------------ texto en pantalla
    def paso_actual(self):
        t = self.tiempo
        if t < self.t_ciudades:
            return "1. Terreno: lomas de un fractal (Diamond–Square)"
        if t < self.t_delaunay:
            return "2. Ciudades en lugares al azar (cada una con su torre de color)"
        if t < self.t_voronoi:
            return "3. Delaunay (Bowyer–Watson): círculo vacío de cada triángulo nuevo"
        if t < self.t_carreteras:
            return "4. Voronoi: cada color es la zona de una ciudad"
        if t < self.t_edificios:
            return "5. Las aristas de Delaunay se vuelven carreteras"
        if t < self.t_viajes or not self.viaje:
            return "6. Crecen las mini ciudades"
        nombres = " → ".join(NOMBRES_ZONA[i % 8] for i in self.viaje["camino"])
        return f"7. Ruta aleatoria más corta (Dijkstra): {nombres}"

    def _texto(self, texto):
        if texto != self.texto_actual:
            self.texto_actual = texto
            sup = pygame.Surface((self.ancho, 60), pygame.SRCALPHA)
            img = self.fuente.render(texto, True, (255, 255, 255))
            pygame.draw.rect(sup, (20, 24, 30, 190), (12, 10, img.get_width() + 24, 40), border_radius=10)
            sup.blit(img, (24, 18))
            self.tex_texto.write(pygame.image.tobytes(sup, "RGBA", True))
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.tex_texto.use(0)
        self.vao_texto.render()
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.DEPTH_TEST)

    # ------------------------------------------------------------ dibujar un cuadro
    def dibujar(self):
        t = self.tiempo
        if t > self.t_viajes:                               # rutas aleatorias, una tras otra
            if self.viaje is None or t - self.viaje["inicio"] > self.viaje["largo"] / 45 + 1.5:
                if self.automatico and self.viajes_hechos >= 6:
                    self.crear_mundo(random.randrange(100000))
                    t = self.tiempo
                else:
                    self.nuevo_viaje()
                    self.viajes_hechos += 1

        ojo = (self.dist * math.cos(self.pitch) * math.sin(self.yaw),
               self.dist * math.sin(self.pitch),
               self.dist * math.cos(self.pitch) * math.cos(self.yaw))
        vp = M.a_gl(M.perspectiva(45, self.ancho / self.alto, 1, 1500) @ M.mirar_a(ojo, (0, 0, 0)))
        self.ctx.clear(0.80, 0.90, 0.97)

        pm = self.p_malla
        pm["vp"].write(vp)
        pm["zonas"].write(np.array(ZONAS, "f4").tobytes())
        pm["modo"].value, pm["crecer"].value = 0, min(1.0, t / 1.5)
        pm["zona_mezcla"].value = 0.3 * min(1.0, max(0.0, (t - self.t_voronoi) / 1.0))
        self.vao_terreno.render()
        pm["crecer"].value, pm["modo"].value = 1.0, 1
        pm["avance"].value = max(0.0, (t - self.t_carreteras) * 90)
        self.vao_carreteras.render()

        self.p_caja["vp"].write(vp)
        self.p_caja["tiempo"].value = t
        if self.viaje and t > self.t_viajes:
            recorrido = min((t - self.viaje["inicio"]) * 45, self.viaje["largo"])
            pm["avance"].value = recorrido
            self.viaje["vao"].render()
            self._auto(recorrido)

        self.p_linea["vp"].write(vp)
        self.p_linea["tiempo"].value = t
        self.vao_lineas.render(moderngl.LINES)
        self.vao_cajas.render(instances=self.n_cajas)
        self._texto(self.paso_actual())

    def _auto(self, recorrido):
        """Auto (dos cajas) en el punto del camino que corresponde a la distancia recorrida."""
        pts, resto = self.viaje["puntos"], recorrido
        x, z = pts[-1]
        rumbo = 0.0
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            largo = math.hypot(x1 - x0, z1 - z0)
            rumbo = math.atan2(-(z1 - z0), x1 - x0)
            if resto <= largo:
                x, z = x0 + (x1 - x0) * resto / largo, z0 + (z1 - z0) * resto / largo
                break
            resto -= largo
        base = M.traslacion(x, self.mundo.altura(x, z) + 0.6, z) @ M.rot_y(rumbo)
        partes = [(base @ M.escala(5, 1.6, 2.8), NARANJA),
                  (base @ M.traslacion(-0.4, 1.6, 0) @ M.escala(2.6, 1.3, 2.4), (0.95, 0.95, 0.95))]
        datos = np.array([np.concatenate([M.instancia(mt), c, [-1.0]]) for mt, c in partes], "f4")
        self.vbo_auto.write(datos.tobytes())
        self.vao_auto.render(instances=len(partes))

    def captura(self, ruta):
        datos = self.ctx.screen.read(components=3)
        pygame.image.save(pygame.image.frombytes(datos, (self.ancho, self.alto), "RGB", True), ruta)

    # ------------------------------------------------------------ bucle principal
    def ejecutar(self):
        reloj, arrastre = pygame.time.Clock(), None
        while True:
            dt = reloj.tick(60) / 1000
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                    self.crear_mundo(random.randrange(100000))
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_a:
                    self.automatico = not self.automatico
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_p:
                    self.captura(f"mundo_{self.mundo.semilla}_{int(time.time())}.png")
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    arrastre = ev.pos
                elif ev.type == pygame.MOUSEBUTTONUP:
                    arrastre = None
                elif ev.type == pygame.MOUSEMOTION and arrastre:
                    self.yaw -= (ev.pos[0] - arrastre[0]) * 0.006
                    self.pitch = float(np.clip(self.pitch + (ev.pos[1] - arrastre[1]) * 0.005, 0.2, 1.45))
                    arrastre = ev.pos
                elif ev.type == pygame.MOUSEWHEEL:
                    self.dist = float(np.clip(self.dist * 0.9 ** ev.y, 60, 600))
            self.tiempo += dt
            if arrastre is None:
                self.yaw += dt * 0.07                          # giro lento automático
            self.dibujar()
            pygame.display.flip()


def ejecutar_3d(semilla=None):
    Vista3D(semilla=semilla).ejecutar()


def capturas(carpeta, semillas=(42, 7, 2026)):
    """Imágenes de cada paso y un GIF del mundo dibujándose (para la documentación)."""
    os.makedirs(carpeta, exist_ok=True)
    v = Vista3D(semilla=semillas[0])
    v.automatico = False
    tomas = [(0.9, "mundo_paso1_terreno"), (2.5, "mundo_paso2_ciudades"),
             (v.t_delaunay + 0.8 * 2 + 0.4, "mundo_paso3_delaunay"),
             (v.t_voronoi + 1.0, "mundo_paso4_voronoi"), (v.t_carreteras + 1.8, "mundo_paso5_carreteras"),
             (v.t_viajes - 0.2, "mundo_paso6_ciudades"), (v.t_viajes + 0.05, None),
             (v.t_viajes + 2.5, "mundo_paso7_ruta")]
    for t, nombre in tomas:
        v.tiempo = t
        v.dibujar()
        if nombre:
            v.captura(os.path.join(carpeta, nombre + ".png"))
    for s in semillas[1:]:
        v.crear_mundo(s)
        for t in (v.t_viajes + 0.05, v.t_viajes + 2.0):   # el viaje empieza y avanza 2 s
            v.tiempo = t
            v.dibujar()
        v.captura(os.path.join(carpeta, f"mundo_{s}.png"))
    try:
        from PIL import Image
        v.crear_mundo(semillas[0])
        cuadros, t = [], 0.0
        while t < v.t_viajes + 4:
            v.tiempo = t
            v.yaw += 0.008
            v.dibujar()
            img = Image.frombytes("RGB", (v.ancho, v.alto), v.ctx.screen.read(components=3))
            cuadros.append(img.transpose(Image.FLIP_TOP_BOTTOM).resize((480, 270)).quantize(colors=64))
            t += 0.2
        cuadros[0].save(os.path.join(carpeta, "mundo_animado.gif"), save_all=True,
                        append_images=cuadros[1:], duration=200, loop=0, optimize=True)
    except ImportError:
        pass
    pygame.quit()
