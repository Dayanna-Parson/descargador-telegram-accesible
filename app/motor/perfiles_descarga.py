"""Perfiles de descarga: qué extensiones se piden a tdl según el tipo de contenido."""

# ANCLAJE_INICIO: PERFILES_DESCARGA
PERFILES_DESCARGA = {
    "Todo": [],
    "Vídeo": ["mp4", "mkv", "avi", "mov", "m4v", "wmv"],
    "Cómics": ["cbz", "cbr", "pdf"],
    "Libros": ["epub", "pdf", "mobi", "azw3"],
    "Audio": ["mp3", "m4a", "flac", "ogg", "wav"],
    "Complementos y programas": ["zip", "rar", "7z", "exe", "msi", "nvda-addon"],
}
# ANCLAJE_FIN: PERFILES_DESCARGA


def nombres_de_perfiles():
    return list(PERFILES_DESCARGA.keys())


def extensiones_del_perfil(nombre):
    return list(PERFILES_DESCARGA.get(nombre, []))
