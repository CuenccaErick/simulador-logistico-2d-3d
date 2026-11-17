"""
Interfaz gráfica (Tkinter) del Simulador Logístico Interactivo 2D.

El mapa se dibuja en un framebuffer propio (ver framebuffer.py) que se vuelca a un
tkinter.PhotoImage y se amplía con un factor entero, de modo que cada píxel lógico
se ve como un bloque y se aprecia el trabajo de los algoritmos de rasterización.
Tkinter solo se usa para los controles y para el texto de las etiquetas.
"""

import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .framebuffer import Framebuffer
from .modelo import Almacen, Destino, Escenario, Ruta
from .render import COLOR_FONDO, OpcionesRender, renderizar
from .transformaciones import Camara, redondear

COLORES_RUTA = ["#39d353", "#ff7b72", "#d2a8ff", "#79c0ff", "#ffa657", "#56d4dd", "#f778ba"]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class App:
    ANCHO_VISTA = 960   # píxeles reales del lienzo
    ALTO_VISTA = 640

    def __init__(self, raiz: tk.Tk, escala: int = 3):
        self.raiz = raiz
        # El lienzo se ajusta a la pantalla (p. ej. laptops de 1366×768)
        self.ANCHO_VISTA = max(480, min(960, raiz.winfo_screenwidth() - 440))
        self.ALTO_VISTA = max(360, min(640, raiz.winfo_screenheight() - 200))
        raiz.title("Simulador Logístico Interactivo 2D — Graficación por Computadora")
        raiz.configure(bg="#0d1117")
        self.escenario = Escenario()
        self.op = OpcionesRender()
        self.escala = escala
        self._crear_framebuffer()

        self.modo = tk.StringVar(value="navegar")
        self.var_alg = tk.StringVar(value="bresenham")
        self.var_rejilla = tk.BooleanVar(value=True)
        self.var_relleno = tk.BooleanVar(value=True)
        self.var_dif = tk.BooleanVar(value=False)
        self.var_anim = tk.BooleanVar(value=False)
        self.var_delaunay = tk.BooleanVar(value=False)
        self.var_voronoi = tk.BooleanVar(value=False)
        self.var_rot = tk.DoubleVar(value=0)
        self.var_escala = tk.IntVar(value=escala)

        self.progreso = 0.0
        self.clic_inicio = None      # primer clic al trazar ruta con el ratón
        self.cursor_mundo = None
        self.arrastre = None
        self._pendiente = False

        self._construir_ui()
        self._atajos()
        self.cargar_demo()
        self._tick()

    # ------------------------------------------------------------------ setup
    def _crear_framebuffer(self):
        w = -(-self.ANCHO_VISTA // self.escala)   # división redondeando hacia arriba
        h = -(-self.ALTO_VISTA // self.escala)
        self.fb = Framebuffer(w, h, COLOR_FONDO)
        cam_ant = getattr(self, "cam", None)
        self.cam = Camara(w, h)
        if cam_ant:
            self.cam.tx, self.cam.ty = cam_ant.tx, cam_ant.ty
            self.cam.angulo_grados, self.cam.zoom = cam_ant.angulo_grados, cam_ant.zoom
        self.img = tk.PhotoImage(width=w, height=h)

    def _construir_ui(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TLabelframe", padding=6)

        # ---- menú
        menu = tk.Menu(self.raiz)
        archivo = tk.Menu(menu, tearoff=0)
        archivo.add_command(label="Nuevo escenario", command=self.nuevo)
        archivo.add_command(label="Cargar escenario demo", command=self.cargar_demo)
        archivo.add_command(label="Abrir…", command=self.abrir, accelerator="Ctrl+O")
        archivo.add_command(label="Guardar…", command=self.guardar, accelerator="Ctrl+S")
        archivo.add_separator()
        archivo.add_command(label="Exportar imagen PNG…", command=self.exportar)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.raiz.destroy)
        menu.add_cascade(label="Archivo", menu=archivo)
        ayuda = tk.Menu(menu, tearoff=0)
        ayuda.add_command(label="Controles", command=self.mostrar_ayuda)
        menu.add_cascade(label="Ayuda", menu=ayuda)
        self.raiz.config(menu=menu)

        cuerpo = tk.Frame(self.raiz, bg="#0d1117")
        cuerpo.pack(fill="both", expand=True)

        # ---- lienzo
        self.canvas = tk.Canvas(cuerpo, width=self.ANCHO_VISTA, height=self.ALTO_VISTA,
                                bg=COLOR_FONDO, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side="left", anchor="n", padx=8, pady=8)
        self.canvas.bind("<ButtonPress-1>", self._clic)
        self.canvas.bind("<B1-Motion>", self._arrastrar)
        self.canvas.bind("<ButtonRelease-1>", self._soltar)
        self.canvas.bind("<Motion>", self._mover)
        self.canvas.bind("<MouseWheel>", self._rueda)               # Windows / macOS
        self.canvas.bind("<Button-4>", lambda e: self._zoom(1.1))   # Linux
        self.canvas.bind("<Button-5>", lambda e: self._zoom(1 / 1.1))

        # ---- panel lateral: pestañas + lista de rutas
        lateral = ttk.Frame(cuerpo, padding=(0, 8, 8, 8))
        lateral.pack(side="right", fill="y")
        libreta = ttk.Notebook(lateral)
        libreta.pack(fill="x")
        panel = ttk.Frame(libreta, padding=4)
        panel_vista = ttk.Frame(libreta, padding=4)
        libreta.add(panel, text="  Crear  ")
        libreta.add(panel_vista, text="  Vista y algoritmos  ")
        ttk.Button(lateral, text="▶  Mundo 3D aleatorio (OpenGL)", command=self.abrir_3d).pack(
            fill="x", pady=(6, 0))

        # Ruta
        f = ttk.LabelFrame(panel, text="Nueva ruta (coordenadas euclidianas)")
        f.pack(fill="x", pady=3)
        self.e_ruta = {}
        for i, (k, v) in enumerate([("x0", "-120"), ("y0", "-40"), ("x1", "110"), ("y1", "70")]):
            ttk.Label(f, text=k).grid(row=i // 2, column=(i % 2) * 2, sticky="e")
            e = ttk.Entry(f, width=7)
            e.insert(0, v)
            e.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=3, pady=2)
            self.e_ruta[k] = e
        ttk.Button(f, text="Trazar ruta", command=self.agregar_ruta).grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(4, 0))

        # Almacén / destino
        f = ttk.LabelFrame(panel, text="Puntos de distribución")
        f.pack(fill="x", pady=3)
        self.e_px = ttk.Entry(f, width=6); self.e_px.insert(0, "0")
        self.e_py = ttk.Entry(f, width=6); self.e_py.insert(0, "0")
        self.e_pr = ttk.Entry(f, width=6); self.e_pr.insert(0, "45")
        for c, (t, e) in enumerate([("x", self.e_px), ("y", self.e_py), ("radio", self.e_pr)]):
            ttk.Label(f, text=t).grid(row=0, column=c * 2, sticky="e")
            e.grid(row=0, column=c * 2 + 1, padx=2)
        ttk.Button(f, text="+ Almacén", command=self.agregar_almacen).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Button(f, text="+ Destino", command=self.agregar_destino).grid(
            row=1, column=3, columnspan=3, sticky="ew", pady=(4, 0))

        # Modo de clic
        f = ttk.LabelFrame(panel, text="Clic izquierdo en el mapa")
        f.pack(fill="x", pady=3)
        for t, v in [("Navegar (arrastrar = trasladar)", "navegar"), ("Trazar ruta (2 clics)", "ruta"),
                     ("Colocar almacén", "almacen"), ("Colocar destino", "destino")]:
            ttk.Radiobutton(f, text=t, value=v, variable=self.modo,
                            command=self._cambio_modo).pack(anchor="w")

        # Algoritmo y capas
        f = ttk.LabelFrame(panel_vista, text="Rasterización")
        f.pack(fill="x", pady=3)
        ttk.Radiobutton(f, text="Bresenham (enteros)", value="bresenham", variable=self.var_alg,
                        command=self._opciones).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="DDA (flotante)", value="dda", variable=self.var_alg,
                        command=self._opciones).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(f, text="Rejilla y ejes", variable=self.var_rejilla,
                        command=self._opciones).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(f, text="Rellenar cobertura", variable=self.var_relleno,
                        command=self._opciones).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(f, text="Diferencias DDA↔Bresenham", variable=self.var_dif,
                        command=self._opciones).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(f, text="Triangulación Delaunay", variable=self.var_delaunay,
                        command=self._opciones).grid(row=3, column=0, sticky="w")
        ttk.Checkbutton(f, text="Zonas Voronoi", variable=self.var_voronoi,
                        command=self._opciones).grid(row=3, column=1, sticky="w")
        ttk.Checkbutton(f, text="Animar vehículos", variable=self.var_anim,
                        command=self._opciones).grid(row=4, column=0, sticky="w")
        fe = ttk.Frame(f)
        fe.grid(row=4, column=1, sticky="w")
        ttk.Label(fe, text="Tamaño píxel").pack(side="left")
        ttk.Spinbox(fe, from_=1, to=6, width=3, textvariable=self.var_escala,
                    command=self._cambio_escala).pack(side="left", padx=3)

        # Vista
        f = ttk.LabelFrame(panel_vista, text="Transformaciones de la vista")
        f.pack(fill="x", pady=3)
        flechas = ttk.Frame(f)
        flechas.grid(row=0, column=0, rowspan=3, padx=(0, 8))
        p = 10
        ttk.Button(flechas, text="▲", width=3, command=lambda: self.panear(0, p)).grid(row=0, column=1)
        ttk.Button(flechas, text="◀", width=3, command=lambda: self.panear(p, 0)).grid(row=1, column=0)
        ttk.Button(flechas, text="⟲", width=3, command=self.reiniciar_vista).grid(row=1, column=1)
        ttk.Button(flechas, text="▶", width=3, command=lambda: self.panear(-p, 0)).grid(row=1, column=2)
        ttk.Button(flechas, text="▼", width=3, command=lambda: self.panear(0, -p)).grid(row=2, column=1)
        ttk.Label(f, text="Rotación θ (°)").grid(row=0, column=1, sticky="w")
        ttk.Scale(f, from_=-180, to=180, variable=self.var_rot, orient="horizontal", length=150,
                  command=self._cambio_rot).grid(row=1, column=1)
        zf = ttk.Frame(f)
        zf.grid(row=2, column=1)
        ttk.Button(zf, text="Zoom −", command=lambda: self._zoom(1 / 1.25)).pack(side="left")
        ttk.Button(zf, text="Zoom +", command=lambda: self._zoom(1.25)).pack(side="left")

        # Lista de rutas
        f = ttk.LabelFrame(lateral, text="Rutas y cobertura")
        f.pack(fill="both", expand=True, pady=(6, 0))
        self.lista = tk.Listbox(f, height=8, width=44, bg="#161b22", fg="#c9d1d9",
                                selectbackground="#1f6feb", font=("Consolas", 9), borderwidth=0)
        self.lista.pack(fill="both", expand=True)
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="Eliminar ruta", command=self.eliminar_ruta).pack(side="left", expand=True, fill="x")
        ttk.Button(bf, text="Limpiar todo", command=self.nuevo).pack(side="left", expand=True, fill="x")

        # Barra de estado
        self.estado = tk.Label(self.raiz, anchor="w", bg="#161b22", fg="#8b949e",
                               font=("Consolas", 9), padx=8)
        self.estado.pack(fill="x", side="bottom")

    def _atajos(self):
        r = self.raiz
        r.bind("<Left>", lambda e: self.panear(10, 0))
        r.bind("<Right>", lambda e: self.panear(-10, 0))
        r.bind("<Up>", lambda e: self.panear(0, 10))
        r.bind("<Down>", lambda e: self.panear(0, -10))
        r.bind("<KeyPress-q>", lambda e: self._rotar(-5))
        r.bind("<KeyPress-e>", lambda e: self._rotar(5))
        r.bind("<KeyPress-r>", lambda e: self.reiniciar_vista())
        r.bind("<KeyPress-b>", lambda e: (self.var_alg.set("dda" if self.var_alg.get() == "bresenham"
                                                         else "bresenham"), self._opciones()))
        r.bind("<Escape>", lambda e: self._cancelar_ruta())
        r.bind("<Control-s>", lambda e: self.guardar())
        r.bind("<Control-o>", lambda e: self.abrir())

    # ------------------------------------------------------------ acciones
    def _entero(self, entrada, nombre):
        try:
            return int(float(entrada.get()))
        except ValueError:
            raise ValueError(f"'{nombre}' debe ser un número")

    def agregar_ruta(self):
        try:
            v = {k: self._entero(e, k) for k, e in self.e_ruta.items()}
        except ValueError as ex:
            messagebox.showerror("Dato inválido", str(ex))
            return
        self._nueva_ruta(v["x0"], v["y0"], v["x1"], v["y1"])

    def _nueva_ruta(self, x0, y0, x1, y1):
        n = len(self.escenario.rutas)
        self.escenario.rutas.append(Ruta(f"R{n + 1}", x0, y0, x1, y1,
                                         COLORES_RUTA[n % len(COLORES_RUTA)]))
        self._refrescar_lista()
        self.pedir_render()

    def agregar_almacen(self, x=None, y=None):
        try:
            x = self._entero(self.e_px, "x") if x is None else x
            y = self._entero(self.e_py, "y") if y is None else y
            r = max(1, self._entero(self.e_pr, "radio"))
        except ValueError as ex:
            messagebox.showerror("Dato inválido", str(ex))
            return
        self.escenario.almacenes.append(Almacen(f"A{len(self.escenario.almacenes) + 1}", x, y, r))
        self._refrescar_lista()
        self.pedir_render()

    def agregar_destino(self, x=None, y=None):
        try:
            x = self._entero(self.e_px, "x") if x is None else x
            y = self._entero(self.e_py, "y") if y is None else y
        except ValueError as ex:
            messagebox.showerror("Dato inválido", str(ex))
            return
        self.escenario.destinos.append(Destino(f"D{len(self.escenario.destinos) + 1}", x, y))
        self._refrescar_lista()
        self.pedir_render()

    def eliminar_ruta(self):
        sel = self.lista.curselection()
        if not sel:
            return
        idx = sel[0] - 2    # filas 0 y 1: resumen y encabezado
        if 0 <= idx < len(self.escenario.rutas):
            del self.escenario.rutas[idx]
            self._refrescar_lista()
            self.pedir_render()

    def nuevo(self):
        self.escenario.limpiar()
        self._refrescar_lista()
        self.pedir_render()

    def cargar_demo(self):
        ruta = os.path.join(RAIZ, "escenarios", "demo_cdmx.json")
        if os.path.exists(ruta):
            self.escenario = Escenario.cargar(ruta)
        self._refrescar_lista()
        self.pedir_render()

    def abrir(self):
        ruta = filedialog.askopenfilename(initialdir=os.path.join(RAIZ, "escenarios"),
                                          filetypes=[("Escenario JSON", "*.json")])
        if ruta:
            try:
                self.escenario = Escenario.cargar(ruta)
            except Exception as ex:   # archivo mal formado
                messagebox.showerror("No se pudo abrir", str(ex))
                return
            self._refrescar_lista()
            self.pedir_render()

    def guardar(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialdir=os.path.join(RAIZ, "escenarios"),
                                            filetypes=[("Escenario JSON", "*.json")])
        if ruta:
            self.escenario.guardar(ruta)

    def exportar(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("Imagen PNG", "*.png")])
        if ruta:
            self.img.zoom(self.escala, self.escala).write(ruta, format="png")

    def abrir_3d(self):
        """La vista 3D corre en su propio proceso (pygame y Tkinter tienen bucles distintos)."""
        import subprocess
        import sys
        if getattr(sys, "frozen", False):          # ejecutable de PyInstaller
            cmd = [sys.executable, "--3d"]
        else:
            cmd = [sys.executable, os.path.join(RAIZ, "main.py"), "--3d"]
        try:
            subprocess.Popen(cmd)
        except OSError as ex:
            messagebox.showerror("Vista 3D", f"No se pudo abrir la vista 3D:\n{ex}")

    def mostrar_ayuda(self):
        messagebox.showinfo("Controles", (
            "Flechas / arrastrar: trasladar el mapa (T)\n"
            "Q / E o deslizador: rotar la vista (R(θ))\n"
            "Rueda del ratón: zoom\n"
            "R: reiniciar vista    B: alternar Bresenham/DDA\n"
            "Botón 'Mundo 3D aleatorio': un mundo nuevo que se dibuja paso a paso\n"
            "Esc: cancelar ruta en construcción\n\n"
            "Modo 'Trazar ruta': clic en el origen y clic en el destino.\n"
            "Destinos verdes = dentro de un área de cobertura; rojos = fuera."))

    # --------------------------------------------------------- transformaciones
    def panear(self, dx, dy):
        # Las flechas mueven la "cámara": el contenido se desplaza en sentido contrario.
        # (dx, dy) se expresan en pantalla; en el espacio de vista Y crece hacia arriba.
        self.cam.panear(dx, -dy)
        self.pedir_render()

    def _rotar(self, grados):
        self.var_rot.set(((self.var_rot.get() + grados + 180) % 360) - 180)
        self._cambio_rot()

    def _cambio_rot(self, *_):
        self.cam.angulo_grados = self.var_rot.get()
        self.pedir_render()

    def _zoom(self, f):
        self.cam.zoom = min(8.0, max(0.25, self.cam.zoom * f))
        self.pedir_render()

    def _rueda(self, e):
        self._zoom(1.1 if e.delta > 0 else 1 / 1.1)

    def reiniciar_vista(self):
        self.cam.reiniciar()
        self.var_rot.set(0)
        self.pedir_render()

    # ------------------------------------------------------------- ratón
    def _a_mundo(self, e):
        sx, sy = e.x / self.escala, e.y / self.escala
        x, y = self.cam.pantalla_a_mundo(sx, sy)
        return redondear(x), redondear(y)

    def _clic(self, e):
        m = self.modo.get()
        x, y = self._a_mundo(e)
        if m == "navegar":
            self.arrastre = (e.x, e.y)
        elif m == "almacen":
            self.agregar_almacen(x, y)
        elif m == "destino":
            self.agregar_destino(x, y)
        elif m == "ruta":
            if self.clic_inicio is None:
                self.clic_inicio = (x, y)
            else:
                self._nueva_ruta(*self.clic_inicio, x, y)
                self.clic_inicio = None
                self.op.preview = None

    def _arrastrar(self, e):
        if self.arrastre is None:
            return
        dx = (e.x - self.arrastre[0]) // self.escala
        dy = (e.y - self.arrastre[1]) // self.escala
        if dx or dy:
            self.cam.panear(dx, -dy)
            self.arrastre = (self.arrastre[0] + dx * self.escala, self.arrastre[1] + dy * self.escala)
            self.pedir_render()

    def _soltar(self, _):
        self.arrastre = None

    def _mover(self, e):
        self.cursor_mundo = (self._a_mundo(e), (e.x // self.escala, e.y // self.escala))
        if self.clic_inicio is not None:
            self.op.preview = (*self.clic_inicio, *self.cursor_mundo[0])
            self.pedir_render()
        else:
            self._actualizar_estado()

    def _cancelar_ruta(self):
        self.clic_inicio = None
        self.op.preview = None
        self.pedir_render()

    def _cambio_modo(self):
        self._cancelar_ruta()
        self.canvas.config(cursor="fleur" if self.modo.get() == "navegar" else "crosshair")

    # ------------------------------------------------------------- opciones
    def _opciones(self):
        self.op.algoritmo = self.var_alg.get()
        self.op.rejilla = self.var_rejilla.get()
        self.op.rellenar_cobertura = self.var_relleno.get()
        self.op.mostrar_diferencias = self.var_dif.get()
        self.op.delaunay = self.var_delaunay.get()
        self.op.voronoi = self.var_voronoi.get()
        self.op.progreso_vehiculos = self.progreso if self.var_anim.get() else -1
        self._refrescar_lista()
        self.pedir_render()

    def _cambio_escala(self):
        try:
            nueva = int(self.var_escala.get())
        except (tk.TclError, ValueError):
            return
        if nueva != self.escala and 1 <= nueva <= 6:
            self.escala = nueva
            self._crear_framebuffer()
            self.pedir_render()

    # ---------------------------------------------------------------- render
    def pedir_render(self):
        """Agrupa varias peticiones en un solo cuadro (evita redibujar de más)."""
        if not self._pendiente:
            self._pendiente = True
            self.raiz.after_idle(self._render)

    def _render(self):
        self._pendiente = False
        self.ultimo = renderizar(self.fb, self.cam, self.escenario, self.op)
        self.img.put(self.fb.como_cadena_tk(), to=(0, 0))
        self.img_vista = self.img.zoom(self.escala, self.escala)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.img_vista, anchor="nw")
        fuente = ("Consolas", 8 if self.escala < 3 else 9)
        for et in self.ultimo.etiquetas:
            self.canvas.create_text(et.x * self.escala, et.y * self.escala, text=et.texto,
                                    fill=et.color, font=fuente, anchor="s")
        self._actualizar_estado()

    def _actualizar_estado(self):
        u = getattr(self, "ultimo", None)
        if u is None:
            return
        cur = ""
        if self.cursor_mundo:
            (wx, wy), (sx, sy) = self.cursor_mundo
            cur = f"mundo ({wx:>4}, {wy:>4}) → pantalla ({sx:>3}, {sy:>3}) | "
        c = self.cam
        dif = f" | dif. DDA/Bres: {u.diferencias}px" if self.op.mostrar_diferencias else ""
        self.estado.config(text=(
            f"{cur}T=({c.tx}, {c.ty})  θ={c.angulo_grados:.0f}°  zoom={c.zoom:.2f} | "
            f"framebuffer {self.fb.ancho}×{self.fb.alto} | {u.pixeles} px iluminados en "
            f"{u.ms:.1f} ms | {self.op.algoritmo.upper()}{dif}"))

    def _refrescar_lista(self):
        self.lista.delete(0, "end")
        cub = len(self.escenario.destinos_cubiertos())
        self.lista.insert("end", f"Almacenes: {len(self.escenario.almacenes)}   "
                                 f"Destinos cubiertos: {cub}/{len(self.escenario.destinos)}")
        self.lista.insert("end", f"{'Ruta':<5}{'Origen':>11}{'Destino':>12}{'Dist.':>7}{'Rumbo':>7}")
        for r in self.escenario.rutas:
            self.lista.insert("end", f"{r.nombre:<5}{f'({r.x0},{r.y0})':>11}{f'({r.x1},{r.y1})':>12}"
                                     f"{r.distancia:>7.1f}{r.rumbo_grados:>6.0f}°")

    def _tick(self):
        """Bucle de animación de vehículos (hasta ~30 cuadros por segundo).
        El siguiente cuadro se programa descontando lo que tardó el actual,
        para no saturar la cola de eventos si el equipo es lento."""
        t0 = time.perf_counter()
        if self.var_anim.get() and self.escenario.rutas:
            self.progreso = (self.progreso + 0.008) % 1.0
            self.op.progreso_vehiculos = self.progreso
            self._render()
        transcurrido = int((time.perf_counter() - t0) * 1000)
        self.raiz.after(max(15, 33 - transcurrido), self._tick)


def ejecutar():
    raiz = tk.Tk()
    App(raiz)
    raiz.resizable(False, False)
    raiz.mainloop()
