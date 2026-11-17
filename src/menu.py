"""
Menú principal: una ventana con botones para ejecutar cada parte del proyecto.

Cada opción se abre en su propio proceso, así el menú sigue abierto y se puede
lanzar otra cosa (por ejemplo, la vista 2D y la 3D al mismo tiempo).
"""

import importlib.util
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPAQUETADO = getattr(sys, "frozen", False)          # True dentro del .exe de PyInstaller

FONDO = "#0d1117"
TARJETA = "#161b22"
TEXTO = "#e6edf3"
GRIS = "#8b949e"
AZUL = "#1f6feb"
VERDE = "#238636"


def comando(*args):
    """Arma el comando para volver a llamar a main.py (o al .exe) con otros argumentos."""
    if EMPAQUETADO:
        return [sys.executable, *args]
    return [sys.executable, os.path.join(RAIZ, "main.py"), *args]


def faltan_dependencias_3d():
    """Lista de paquetes de la vista 3D que no están instalados."""
    faltan = []
    for modulo, paquete in (("numpy", "numpy"), ("moderngl", "moderngl"), ("pygame", "pygame-ce")):
        if importlib.util.find_spec(modulo) is None:      # revisa sin importar
            faltan.append(paquete)
    return faltan


class Menu:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        raiz.title("Simulador Logístico — Menú")
        raiz.configure(bg=FONDO)
        raiz.resizable(False, False)

        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        tk.Label(raiz, text="Simulador Logístico", font=("Segoe UI", 22, "bold"),
                 fg=TEXTO, bg=FONDO).pack(padx=30, pady=(24, 0), anchor="w")
        tk.Label(raiz, text="Graficación por Computadora · ESCOM IPN · 6CV3 · Erick Daniel Cuenca Castillo",
                 font=("Segoe UI", 10), fg=GRIS, bg=FONDO).pack(padx=30, anchor="w")

        cuerpo = tk.Frame(raiz, bg=FONDO)
        cuerpo.pack(padx=24, pady=16, fill="both")

        self._tarjeta(cuerpo, 0, "Simulador 2D",
                      "Rutas con Bresenham y DDA, coberturas con Punto Medio,\n"
                      "traslación, rotación y mapeo al cuarto cuadrante.",
                      "Abrir 2D", AZUL, self.abrir_2d)
        tarjeta3d = self._tarjeta(cuerpo, 1, "Mundo 3D aleatorio",
                                  "Mini ciudades que se dibujan solas: Delaunay con círculo vacío,\n"
                                  "Voronoi, carreteras y rutas más cortas con Dijkstra.",
                                  "Mundo nuevo", AZUL, lambda: self.abrir_3d(None))
        fila = tk.Frame(tarjeta3d, bg=TARJETA)
        fila.pack(anchor="w", pady=(8, 0))
        tk.Label(fila, text="Mundo número:", fg=GRIS, bg=TARJETA, font=("Segoe UI", 10)).pack(side="left")
        self.semilla = tk.StringVar(value="42")
        ttk.Entry(fila, textvariable=self.semilla, width=8).pack(side="left", padx=6)
        ttk.Button(fila, text="Abrir ese mundo", command=self.abrir_3d_numero).pack(side="left")
        tk.Label(tarjeta3d, text="El mismo número siempre da el mismo mundo (útil para ensayar la exposición).",
                 fg=GRIS, bg=TARJETA, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        self._tarjeta(cuerpo, 2, "Pruebas",
                      "Valida la matemática: 50 pruebas de Bresenham, Punto Medio,\n"
                      "transformaciones, Delaunay, Voronoi, Dijkstra y más.",
                      "Correr pruebas", VERDE, self.correr_pruebas)
        self._tarjeta(cuerpo, 3, "Capturas para la presentación",
                      "Guarda una imagen de cada paso del mundo 3D y un GIF animado\n"
                      "en la carpeta «capturas».",
                      "Generar capturas", AZUL, self.generar_capturas)

        # consola de resultados
        self.salida = tk.Text(raiz, height=9, bg=TARJETA, fg=TEXTO, insertbackground=TEXTO,
                              font=("Consolas", 9), relief="flat", padx=10, pady=8)
        self.salida.pack(padx=24, pady=(0, 10), fill="x")
        self.escribir("Elige una opción. Los resultados de las pruebas aparecen aquí.\n")

        abajo = tk.Frame(raiz, bg=FONDO)
        abajo.pack(padx=24, pady=(0, 20), fill="x")
        self.boton_instalar = ttk.Button(abajo, text="Instalar dependencias 3D", command=self.instalar_3d)
        self.boton_instalar.pack(side="left")
        ttk.Button(abajo, text="Salir", command=raiz.destroy).pack(side="right")

        faltan = faltan_dependencias_3d()
        if faltan and not EMPAQUETADO:
            self.escribir(f"Aviso: para la vista 3D faltan {', '.join(faltan)}. "
                          "Usa «Instalar dependencias 3D».\n")
        else:
            self.boton_instalar.pack_forget()

    # ------------------------------------------------------------------ diseño
    def _tarjeta(self, padre, fila, titulo, descripcion, texto_boton, color, accion):
        marco = tk.Frame(padre, bg=TARJETA, padx=16, pady=12)
        marco.grid(row=fila, column=0, sticky="ew", pady=5)
        padre.grid_columnconfigure(0, weight=1)
        encabezado = tk.Frame(marco, bg=TARJETA)
        encabezado.pack(fill="x")
        textos = tk.Frame(encabezado, bg=TARJETA)
        textos.pack(side="left", fill="x", expand=True)
        tk.Label(textos, text=titulo, font=("Segoe UI", 13, "bold"), fg=TEXTO, bg=TARJETA).pack(anchor="w")
        tk.Label(textos, text=descripcion, font=("Segoe UI", 10), fg=GRIS, bg=TARJETA,
                 justify="left").pack(anchor="w")
        tk.Button(encabezado, text=texto_boton, command=accion, bg=color, fg="white",
                  activebackground=color, activeforeground="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=14, pady=6, cursor="hand2",
                  width=16).pack(side="right", padx=(16, 0))
        return marco

    def escribir(self, texto):
        self.salida.insert("end", texto)
        self.salida.see("end")

    # ------------------------------------------------------------------ acciones
    def lanzar(self, args, descripcion):
        try:
            subprocess.Popen(comando(*args), cwd=RAIZ)
            self.escribir(f"▶ {descripcion}\n")
        except OSError as ex:
            messagebox.showerror("No se pudo abrir", str(ex))

    def abrir_2d(self):
        self.lanzar(["--2d"], "Abriendo el simulador 2D…")

    def _listo_3d(self):
        faltan = faltan_dependencias_3d()
        if faltan and not EMPAQUETADO:
            messagebox.showwarning("Faltan dependencias",
                                   "Para la vista 3D falta instalar: " + ", ".join(faltan) +
                                   "\n\nUsa el botón «Instalar dependencias 3D».")
            return False
        return True

    def abrir_3d(self, semilla):
        if self._listo_3d():
            args = ["--3d"] + ([str(semilla)] if semilla is not None else [])
            texto = f"Abriendo el mundo número {semilla}…" if semilla is not None else "Abriendo un mundo nuevo…"
            self.lanzar(args, texto)

    def abrir_3d_numero(self):
        valor = self.semilla.get().strip()
        if not valor.isdigit():
            messagebox.showerror("Número inválido", "Escribe un número entero, por ejemplo 42.")
            return
        self.abrir_3d(int(valor))

    def generar_capturas(self):
        if self._listo_3d():
            carpeta = os.path.join(RAIZ, "capturas")
            self.lanzar(["--capturas", carpeta], f"Generando capturas en {carpeta} (tarda unos segundos)…")

    def _en_segundo_plano(self, cmd, titulo):
        """Ejecuta un comando sin congelar la ventana y muestra su salida en la consola."""
        self.escribir(f"▶ {titulo}\n")

        def trabajo():
            try:
                p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
                texto = (p.stdout + p.stderr).strip()
                ok = p.returncode == 0
            except OSError as ex:
                texto, ok = str(ex), False
            ultimas = "\n".join(texto.splitlines()[-12:])
            self.raiz.after(0, lambda: self.escribir(ultimas + ("\n✔ Listo.\n" if ok else "\n✘ Hubo un error.\n")))

        threading.Thread(target=trabajo, daemon=True).start()

    def correr_pruebas(self):
        if EMPAQUETADO:
            messagebox.showinfo("Pruebas", "Las pruebas se corren desde el código fuente: py -m unittest")
            return
        self._en_segundo_plano([sys.executable, "-m", "unittest"], "Corriendo las pruebas…")

    def instalar_3d(self):
        faltan = faltan_dependencias_3d()
        if not faltan:
            self.escribir("Las dependencias 3D ya están instaladas.\n")
            return
        self._en_segundo_plano([sys.executable, "-m", "pip", "install", *faltan],
                               f"Instalando {', '.join(faltan)} (puede tardar un minuto)…")


def ejecutar():
    raiz = tk.Tk()
    Menu(raiz)
    raiz.mainloop()
