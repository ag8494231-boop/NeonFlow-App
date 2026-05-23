import os
import io
import random
import sqlite3
from PIL import Image, ImageDraw, ImageFont

# Kivy / KivyMD Imports
from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivymd.uix.list import TwoLineAvatarIconListItem, IconRightWidget, IconLeftWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivymd.toast import toast

# ==========================================
# 1. BASE DE DATOS LOCAL (SQLite Móvil)
# ==========================================
class GestorBD:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.crear_tablas()

    def crear_tablas(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS canciones
                     (ruta TEXT PRIMARY KEY, titulo TEXT, artista TEXT, album TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS transiciones
                     (origen TEXT, destino TEXT, peso INTEGER,
                      PRIMARY KEY (origen, destino))''')
        self.conn.commit()

    def guardar_cancion(self, cancion):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO canciones VALUES (?, ?, ?, ?)",
                  (cancion.ruta, cancion.titulo, cancion.artista, cancion.album))
        self.conn.commit()

    def eliminar_cancion(self, ruta):
        c = self.conn.cursor()
        c.execute("DELETE FROM canciones WHERE ruta = ?", (ruta,))
        c.execute("DELETE FROM transiciones WHERE origen = ? OR destino = ?", (ruta, ruta))
        self.conn.commit()

    def obtener_canciones(self):
        c = self.conn.cursor()
        c.execute("SELECT ruta, titulo, artista, album FROM canciones")
        return c.fetchall()

    def actualizar_transicion(self, origen, destino):
        c = self.conn.cursor()
        c.execute("SELECT peso FROM transiciones WHERE origen = ? AND destino = ?", (origen, destino))
        row = c.fetchone()
        peso = 1
        if row:
            peso = row[0] + 1
            c.execute("UPDATE transiciones SET peso = ? WHERE origen = ? AND destino = ?", (peso, origen, destino))
        else:
            c.execute("INSERT INTO transiciones (origen, destino, peso) VALUES (?, ?, ?)", (origen, destino, peso))
        self.conn.commit()

    def obtener_transiciones(self):
        c = self.conn.cursor()
        c.execute("SELECT origen, destino, peso FROM transiciones")
        return c.fetchall()

# ==========================================
# 2. ESTRUCTURAS DE DATOS Y ALGORITMOS
# ==========================================
class Cancion:
    def __init__(self, titulo, artista, album, ruta):
        self.titulo = titulo
        self.artista = artista
        self.album = album
        self.ruta = ruta
    def __lt__(self, other):
        return self.titulo.lower() < other.titulo.lower()

class NodoLista:
    def __init__(self, datos):
        self.datos = datos
        self.siguiente = None
        self.anterior = None

class ListaDoble:
    def __init__(self):
        self.cabeza = None
        self.actual = None

    def agregar(self, cancion):
        nuevo = NodoLista(cancion)
        if self.cabeza is None:
            self.cabeza = nuevo
            self.actual = self.cabeza
        else:
            temp = self.cabeza
            while temp.siguiente is not None:
                temp = temp.siguiente
            temp.siguiente = nuevo
            nuevo.anterior = temp

    def eliminar(self, cancion):
        if self.cabeza is None: return
        temp = self.cabeza
        while temp is not None:
            if temp.datos == cancion:
                if self.actual == temp:
                    self.actual = temp.siguiente if temp.siguiente else temp.anterior
                    if self.cabeza == temp and self.cabeza.siguiente is None:
                        self.actual = None
                if temp.anterior is not None:
                    temp.anterior.siguiente = temp.siguiente
                else:
                    self.cabeza = temp.siguiente
                if temp.siguiente is not None:
                    temp.siguiente.anterior = temp.anterior
                break
            temp = temp.siguiente

    def a_lista(self):
        lista = []
        temp = self.cabeza
        while temp is not None:
            lista.append(temp.datos)
            temp = temp.siguiente
        return lista

    def reconstruir(self, lista_canciones):
        self.cabeza = None
        self.actual = None
        for c in lista_canciones:
            self.agregar(c)
        self.actual = self.cabeza

class NodoArbol:
    def __init__(self, datos):
        self.datos = datos
        self.izq = None
        self.der = None

class ArbolCanciones:
    def __init__(self):
        self.raiz = None
    def limpiar(self):
        self.raiz = None
    def insertar(self, cancion):
        self.raiz = self._insertar_rec(self.raiz, cancion)
    def _insertar_rec(self, raiz, cancion):
        if raiz is None: return NodoArbol(cancion)
        if cancion.titulo.lower() < raiz.datos.titulo.lower():
            raiz.izq = self._insertar_rec(raiz.izq, cancion)
        else:
            raiz.der = self._insertar_rec(raiz.der, cancion)
        return raiz
    def buscar(self, texto):
        resultados = []
        self._buscar_rec(self.raiz, texto.lower(), resultados)
        return resultados
    def _buscar_rec(self, raiz, texto, resultados):
        if raiz is not None:
            self._buscar_rec(raiz.izq, texto, resultados)
            if texto in raiz.datos.titulo.lower() or texto in raiz.datos.artista.lower():
                resultados.append(raiz.datos)
            self._buscar_rec(raiz.der, texto, resultados)

class GrafoPonderado:
    def __init__(self):
        self.lista_adyacencia = {}
    def registrar_transicion(self, origen, destino):
        if origen is None or destino is None or origen == destino: return
        if origen not in self.lista_adyacencia: self.lista_adyacencia[origen] = {}
        if destino not in self.lista_adyacencia[origen]: self.lista_adyacencia[origen][destino] = 0
        self.lista_adyacencia[origen][destino] += 1
    def establecer_peso(self, origen, destino, peso):
        if origen is None or destino is None or origen == destino: return
        if origen not in self.lista_adyacencia: self.lista_adyacencia[origen] = {}
        self.lista_adyacencia[origen][destino] = peso
    def obtener_mejor_siguiente(self, actual, todas_las_canciones):
        if actual in self.lista_adyacencia and len(self.lista_adyacencia[actual]) > 0:
            sugerencias = sorted(self.lista_adyacencia[actual].items(), key=lambda item: item[1], reverse=True)
            return sugerencias[0][0]
        if actual and len(todas_las_canciones) > 1:
            similares = [c for c in todas_las_canciones if c != actual and 
                        ((c.artista != "Desconocido" and c.artista == actual.artista) or 
                         (c.album != "Desconocido" and c.album == actual.album))]
            if similares: return random.choice(similares)
        if len(todas_las_canciones) > 0:
            posibles = [c for c in todas_las_canciones if c != actual]
            if posibles: return random.choice(posibles)
            return todas_las_canciones[0]
        return None
    def eliminar_nodo(self, cancion):
        if cancion in self.lista_adyacencia: del self.lista_adyacencia[cancion]
        for k in self.lista_adyacencia.keys():
            if cancion in self.lista_adyacencia[k]: del self.lista_adyacencia[k][cancion]

def particion(lista, bajo, alto):
    pivote = lista[alto]
    i = bajo - 1
    for j in range(bajo, alto):
        if lista[j] < pivote:
            i += 1
            lista[i], lista[j] = lista[j], lista[i]
    lista[i + 1], lista[alto] = lista[alto], lista[i + 1]
    return i + 1

def quick_sort(lista, bajo, alto):
    if bajo < alto:
        pi = particion(lista, bajo, alto)
        quick_sort(lista, bajo, pi - 1)
        quick_sort(lista, pi + 1, alto)

# ==========================================
# 3. METADATOS Y PORTADAS (Móvil)
# ==========================================
def obtener_info_texto(ruta):
    info = {'titulo': None, 'artista': 'Desconocido', 'album': 'Desconocido'}
    try:
        with open(ruta, 'rb') as f:
            header = f.read(10)
            if len(header) < 10 or header[:3] != b'ID3': return info
            version_mayor = header[3]
            tag_size = (header[6] << 21) | (header[7] << 14) | (header[8] << 7) | header[9]
            while f.tell() < tag_size + 10:
                current_pos = f.tell()
                frame_id = f.read(4)
                if len(frame_id) < 4 or frame_id[0] == 0: break
                size_bytes = f.read(4)
                if version_mayor == 4: frame_size = (size_bytes[0]<<21) | (size_bytes[1]<<14) | (size_bytes[2]<<7) | size_bytes[3]
                else: frame_size = (size_bytes[0]<<24) | (size_bytes[1]<<16) | (size_bytes[2]<<8) | size_bytes[3]
                f.read(2)
                if frame_id in [b'TIT2', b'TPE1', b'TALB']:
                    encoding = f.read(1)
                    text_bytes = f.read(frame_size - 1)
                    text = ""
                    try:
                        if encoding == b'\x00': text = text_bytes.decode('iso-8859-1').strip('\x00')
                        elif encoding == b'\x01': text = text_bytes.decode('utf-16').strip('\x00')
                        elif encoding == b'\x02': text = text_bytes.decode('utf-16-be').strip('\x00')
                        elif encoding == b'\x03': text = text_bytes.decode('utf-8').strip('\x00')
                        else: text = text_bytes.decode('iso-8859-1', errors='ignore').strip('\x00')
                    except: pass
                    if frame_id == b'TIT2': info['titulo'] = text
                    elif frame_id == b'TPE1': info['artista'] = text
                    elif frame_id == b'TALB': info['album'] = text
                else:
                    f.seek(current_pos + 10 + frame_size)
    except: pass
    return info

def generar_portada_temporal(ruta_mp3, ruta_destino):
    # Intentar extraer portada ID3
    img_data = None
    try:
        with open(ruta_mp3, 'rb') as f:
            header = f.read(10)
            if len(header) >= 10 and header[:3] == b'ID3':
                version_mayor = header[3]
                tag_size = (header[6] << 21) | (header[7] << 14) | (header[8] << 7) | header[9]
                while f.tell() < tag_size + 10:
                    current_pos = f.tell()
                    frame_id = f.read(4)
                    if len(frame_id) < 4 or frame_id[0] == 0: break
                    size_bytes = f.read(4)
                    if version_mayor == 4: frame_size = (size_bytes[0]<<21) | (size_bytes[1]<<14) | (size_bytes[2]<<7) | size_bytes[3]
                    else: frame_size = (size_bytes[0]<<24) | (size_bytes[1]<<16) | (size_bytes[2]<<8) | size_bytes[3]
                    f.read(2)
                    if frame_id == b'APIC':
                        f.read(1)
                        while f.read(1) != b'\x00': pass
                        f.read(1)
                        data_start = f.tell()
                        buffer = f.read(200)
                        f.seek(data_start)
                        offset = -1
                        for i in range(len(buffer) - 1):
                            if buffer[i] == 0xFF and buffer[i+1] == 0xD8: offset = i; break
                            if buffer[i] == 0x89 and buffer[i+1] == 0x50: offset = i; break
                        if offset != -1:
                            f.seek(data_start + offset)
                            img_data = f.read(frame_size - (1 + offset))
                        break
                    else:
                        f.seek(current_pos + 10 + frame_size)
    except: pass

    # Si encontramos imagen, la guardamos. Si no, creamos un placeholder sólido.
    if img_data:
        with open(ruta_destino, 'wb') as f:
            f.write(img_data)
    else:
        img = Image.new('RGB', (400, 400), color=(40, 40, 40))
        img.save(ruta_destino)


# ==========================================
# 4. INTERFAZ MÓVIL (KivyMD)
# ==========================================
KV = '''
MDScreen:
    MDBottomNavigation:
        panel_color: app.theme_cls.bg_dark
        selected_color_background: app.theme_cls.primary_color
        text_color_active: app.theme_cls.primary_color

        # ----------- PESTAÑA 1: BIBLIOTECA -----------
        MDBottomNavigationItem:
            name: 'screen_biblioteca'
            text: 'Biblioteca'
            icon: 'music-box-multiple'

            MDBoxLayout:
                orientation: 'vertical'
                
                MDTopAppBar:
                    title: "NeonFlow"
                    elevation: 4
                    right_action_items: [["sort-alphabetical-ascending", lambda x: app.btn_ordenar_click()], ["folder-music", lambda x: app.abrir_explorador()]]
                    md_bg_color: app.theme_cls.bg_dark

                MDBoxLayout:
                    size_hint_y: None
                    height: "60dp"
                    padding: "10dp"
                    MDTextField:
                        id: txt_buscar
                        hint_text: "Buscar canción..."
                        icon_left: "magnify"
                        mode: "fill"
                        radius: [20, 20, 20, 20]
                        on_text: app.buscar_cancion(self.text)

                MDScrollView:
                    MDList:
                        id: lista_canciones
                        padding: "10dp"

        # ----------- PESTAÑA 2: REPRODUCTOR -----------
        MDBottomNavigationItem:
            name: 'screen_reproductor'
            text: 'Reproductor'
            icon: 'play-circle'

            MDBoxLayout:
                orientation: 'vertical'
                padding: "20dp"
                spacing: "20dp"

                # Portada de la Canción
                MDCard:
                    size_hint: None, None
                    size: "280dp", "280dp"
                    pos_hint: {"center_x": .5}
                    radius: 36
                    elevation: 4
                    FitImage:
                        id: img_portada
                        source: ""
                        radius: 36

                # Información
                MDLabel:
                    id: lbl_titulo
                    text: "Sin Selección"
                    halign: "center"
                    font_style: "H5"
                    bold: True
                    adaptive_height: True

                MDLabel:
                    id: lbl_artista
                    text: "Artista Desconocido"
                    halign: "center"
                    theme_text_color: "Secondary"
                    font_style: "Subtitle1"
                    adaptive_height: True

                # Controles de Reproducción
                MDRelativeLayout:
                    size_hint_y: None
                    height: "80dp"
                    
                    MDIconButton:
                        icon: "skip-previous"
                        icon_size: "40sp"
                        pos_hint: {"center_x": 0.2, "center_y": 0.5}
                        on_release: app.anterior_logica()
                        
                    MDIconButton:
                        id: btn_play
                        icon: "play-circle"
                        icon_size: "70sp"
                        theme_text_color: "Custom"
                        text_color: app.theme_cls.accent_color
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}
                        on_release: app.manejar_play_pausa()
                        
                    MDIconButton:
                        icon: "skip-next"
                        icon_size: "40sp"
                        pos_hint: {"center_x": 0.8, "center_y": 0.5}
                        on_release: app.siguiente_logica()

                # Botón de Inteligencia
                MDFillRoundFlatIconButton:
                    icon: "brain"
                    text: "Reproducción Inteligente"
                    pos_hint: {"center_x": .5}
                    md_bg_color: 0.38, 0, 0.92, 1 # Deep purple
                    on_release: app.activar_modo_smart()
                    
                Widget: # Espaciador inferior

<ExploradorArchivos>:
    orientation: 'vertical'
    FileChooserListView:
        id: filechooser
        path: root.ruta_inicial
        filters: ["*.mp3", "*.wav", "*.ogg"]
    MDBoxLayout:
        size_hint_y: None
        height: "50dp"
        spacing: "10dp"
        MDRaisedButton:
            text: "Cancelar"
            md_bg_color: app.theme_cls.error_color
            on_release: root.cancelar()
        MDRaisedButton:
            text: "Importar Canción"
            on_release: root.importar(filechooser.selection)
'''

# Widget temporal para buscar archivos (Simula explorador móvil)
class ExploradorArchivos(BoxLayout):
    def __init__(self, app, dialog, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.dialog = dialog
        # Intenta abrir en la carpeta del usuario
        self.ruta_inicial = os.path.expanduser("~") 

    def cancelar(self):
        self.dialog.dismiss()

    def importar(self, selection):
        if selection:
            self.app.procesar_importacion(selection)
        self.dialog.dismiss()

class ReproductorApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette = "Cyan"
        return Builder.load_string(KV)

    def on_start(self):
        # Configurar rutas seguras para móvil
        self.ruta_bd = os.path.join(self.user_data_dir, "musica_datos.db")
        self.ruta_portada_temp = os.path.join(self.user_data_dir, "temp_cover.jpg")
        
        # Generar portada vacía inicial
        generar_portada_temporal("inexistente.mp3", self.ruta_portada_temp)
        self.root.ids.img_portada.source = self.ruta_portada_temp

        self.bd = GestorBD(self.ruta_bd)
        
        # Variables Lógicas
        self.playlist = ListaDoble()
        self.historial = []
        self.libreria = ArbolCanciones()
        self.grafo = GrafoPonderado()
        
        self.ultima_cancion = None
        self.sound = None
        self.is_playing = False
        self.is_paused = False
        self.dialog_explorador = None

        self.cargar_datos_bd()
        
        # Bucle de comprobación de fin de canción
        Clock.schedule_interval(self.verificar_fin_cancion, 1)

    def cargar_datos_bd(self):
        dict_canciones = {}
        for ruta, titulo, artista, album in self.bd.obtener_canciones():
            if os.path.exists(ruta):
                c = Cancion(titulo, artista, album, ruta)
                self.playlist.agregar(c)
                self.libreria.insertar(c)
                dict_canciones[ruta] = c
            else:
                self.bd.eliminar_cancion(ruta)
                
        for orig_ruta, dest_ruta, peso in self.bd.obtener_transiciones():
            if orig_ruta in dict_canciones and dest_ruta in dict_canciones:
                self.grafo.establecer_peso(dict_canciones[orig_ruta], dict_canciones[dest_ruta], peso)
                
        self.actualizar_lista_visual(self.playlist.a_lista())

    def actualizar_lista_visual(self, lista):
        self.root.ids.lista_canciones.clear_widgets()
        for c in lista:
            item = TwoLineAvatarIconListItem(
                text=c.titulo,
                secondary_text=c.artista,
                on_release=lambda x, song=c: self.reproducir_cancion(song)
            )
            # Icono musical izquierdo
            item.add_widget(IconLeftWidget(icon="music"))
            # Botón eliminar derecho
            btn_eliminar = IconRightWidget(icon="trash-can-outline", theme_text_color="Error")
            btn_eliminar.bind(on_release=lambda x, song=c: self.btn_eliminar_click(song))
            item.add_widget(btn_eliminar)
            
            self.root.ids.lista_canciones.add_widget(item)

    # --- Lógica de Interfaz y Audio ---
    def abrir_explorador(self):
        if not self.dialog_explorador:
            self.dialog_explorador = MDDialog(
                title="Seleccionar Canción",
                type="custom",
                content_cls=ExploradorArchivos(app=self, dialog=None),
                size_hint=(0.9, 0.9)
            )
            self.dialog_explorador.content_cls.dialog = self.dialog_explorador
        self.dialog_explorador.open()

    def procesar_importacion(self, rutas):
        canciones_actuales = [c.ruta.lower() for c in self.playlist.a_lista()]
        for ruta in rutas:
            if ruta.lower() in canciones_actuales: continue
            
            info = obtener_info_texto(ruta)
            titulo = info['titulo'] if info['titulo'] else os.path.splitext(os.path.basename(ruta))[0]
            artista = info['artista'] if info['artista'] else "Desconocido"
            album = info['album'] if info['album'] else "Desconocido"
            
            c = Cancion(titulo, artista, album, ruta)
            self.playlist.agregar(c)
            self.libreria.insertar(c)
            self.bd.guardar_cancion(c)
            
        toast("Música importada")
        self.actualizar_lista_visual(self.playlist.a_lista())

    def buscar_cancion(self, texto):
        if not texto.strip():
            self.actualizar_lista_visual(self.playlist.a_lista())
        else:
            encontradas = self.libreria.buscar(texto)
            self.actualizar_lista_visual(encontradas)

    def btn_ordenar_click(self):
        lista = self.playlist.a_lista()
        if len(lista) > 0:
            quick_sort(lista, 0, len(lista) - 1)
            self.playlist.reconstruir(lista)
            self.actualizar_lista_visual(self.playlist.a_lista())
            toast("Biblioteca ordenada A-Z")

    def reproducir_cancion(self, cancion):
        # Grafo de aprendizaje
        if self.ultima_cancion is not None and self.ultima_cancion != cancion:
            self.grafo.registrar_transicion(self.ultima_cancion, cancion)
            self.bd.actualizar_transicion(self.ultima_cancion.ruta, cancion.ruta)
            
        self.ultima_cancion = cancion

        # Sincronizar lista doble
        temp = self.playlist.cabeza
        while temp is not None:
            if temp.datos == cancion:
                self.playlist.actual = temp
                break
            temp = temp.siguiente

        # Detener audio anterior
        if self.sound:
            self.sound.stop()
            self.sound.unload()

        # Cargar y reproducir nuevo audio (Motor Móvil)
        self.sound = SoundLoader.load(cancion.ruta)
        if self.sound:
            self.sound.play()
            self.is_playing = True
            self.is_paused = False
            
            # Actualizar UI del reproductor
            self.root.ids.lbl_titulo.text = cancion.titulo
            self.root.ids.lbl_artista.text = cancion.artista
            self.root.ids.btn_play.icon = "pause-circle"
            
            # Extraer y mostrar portada
            generar_portada_temporal(cancion.ruta, self.ruta_portada_temp)
            self.root.ids.img_portada.source = self.ruta_portada_temp
            self.root.ids.img_portada.reload()
        else:
            toast("Error al reproducir el archivo")

    def manejar_play_pausa(self):
        if self.sound:
            if self.is_playing and not self.is_paused:
                self.sound.stop() # En Kivy, pause se simula con stop/seek o el motor base. Para simplificar, usamos stop
                self.is_paused = True
                self.root.ids.btn_play.icon = "play-circle"
            else:
                self.sound.play()
                self.is_paused = False
                self.root.ids.btn_play.icon = "pause-circle"
        elif self.playlist.actual:
            self.reproducir_cancion(self.playlist.actual.datos)

    def siguiente_logica(self):
        if self.playlist.actual and self.playlist.actual.siguiente:
            self.historial.append(self.playlist.actual.datos)
            self.reproducir_cancion(self.playlist.actual.siguiente.datos)

    def anterior_logica(self):
        if len(self.historial) > 0:
            prev_cancion = self.historial.pop()
            self.reproducir_cancion(prev_cancion)
        elif self.playlist.actual and self.playlist.actual.anterior:
            self.reproducir_cancion(self.playlist.actual.anterior.datos)

    def activar_modo_smart(self):
        if self.playlist.actual:
            sugerencia = self.grafo.obtener_mejor_siguiente(self.playlist.actual.datos, self.playlist.a_lista())
            if sugerencia:
                self.reproducir_cancion(sugerencia)
                toast("✨ Reproducción Inteligente Activada")
            else:
                toast("Aún no hay suficientes datos para recomendar")

    def verificar_fin_cancion(self, dt):
        # Kivy SoundLoader cambia el state a 'stop' cuando la canción termina naturalmente
        if self.sound and self.is_playing and not self.is_paused:
            if self.sound.state == 'stop':
                self.siguiente_logica()

    def btn_eliminar_click(self, cancion):
        is_playing = (self.root.ids.lbl_titulo.text == cancion.titulo)

        self.playlist.eliminar(cancion)
        self.historial = [c for c in self.historial if c != cancion]
        self.grafo.eliminar_nodo(cancion)
        self.bd.eliminar_cancion(cancion.ruta)

        if self.ultima_cancion == cancion:
            self.ultima_cancion = None

        if is_playing and self.sound:
            self.sound.stop()
            self.sound.unload()
            self.sound = None
            self.is_playing = False
            self.is_paused = False
            self.root.ids.lbl_titulo.text = "Sin Selección"
            self.root.ids.lbl_artista.text = "Artista Desconocido"
            self.root.ids.btn_play.icon = "play-circle"
            generar_portada_temporal("invalido", self.ruta_portada_temp)
            self.root.ids.img_portada.reload()

        self.libreria.limpiar()
        for x in self.playlist.a_lista():
            self.libreria.insertar(x)
            
        self.actualizar_lista_visual(self.playlist.a_lista())
        toast("Canción eliminada")

if __name__ == "__main__":
    ReproductorApp().run()