"""
Genera una imagen PNG transparente (1080x1920) con una tarjeta estilo
"post de Reddit" (avatar del canal, nombre del canal, fila de emojis de
reacción, la pregunta/título, y una fila de upvote/comentarios/share
abajo), para superponer sobre el video los primeros segundos.

Necesita el logo del canal guardado como "channel_avatar.png" en la
misma carpeta que este script.

Instalar: pip install pillow
"""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ============================================================
#  CONFIGURACIÓN — cambia aquí lo que quieras personalizar
# ============================================================
CHANNEL_NAME = "RedditNoir"
AVATAR_PATH = str(Path(__file__).resolve().parent / "assets" / "canal" / "avatar_redditplot_galleta.png")

UPVOTES_COUNT = "999+"
COMMENTS_COUNT = "999+"
SHARE_LABEL = "Compartir"

# Fila de emojis de reacción bajo el nombre del canal (para "más dopamina")
REACTION_EMOJIS = "😂 😍 🔥 😱 🤯 👀"
# ============================================================

ANCHO = 1080
ALTO = 1920

COLOR_TARJETA = (255, 255, 255, 255)
COLOR_SOMBRA = (0, 0, 0, 70)
COLOR_TEXTO_TITULO = (20, 20, 20, 255)
COLOR_TEXTO_CANAL = (20, 20, 20, 255)
COLOR_GRIS = (120, 120, 120, 255)
COLOR_LINEA = (225, 225, 225, 255)

FUENTES_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "arialbd.ttf",
]
FUENTES_NORMAL = [
    "C:/Windows/Fonts/arial.ttf",
    "arial.ttf",
]
FUENTES_EMOJI = [
    "C:/Windows/Fonts/seguiemj.ttf",  # Segoe UI Emoji (Windows), soporta color
    "seguiemj.ttf",
]


def _cargar_fuente(candidatas: list[str], tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in candidatas:
        try:
            return ImageFont.truetype(ruta, tamano)
        except OSError:
            continue
    return ImageFont.load_default()


def _dibujar_emojis(draw: ImageDraw.ImageDraw, x: int, y: int, emojis: str, tamano: int):
    fuente_emoji = _cargar_fuente(FUENTES_EMOJI, tamano)
    try:
        draw.text((x, y), emojis, font=fuente_emoji, embedded_color=True)
    except TypeError:
        # Pillow/freetype sin soporte de emoji a color: se dibujan en gris
        draw.text((x, y), emojis, font=fuente_emoji, fill=COLOR_GRIS)


def _avatar_circular(ruta_avatar: str, tamano: int) -> Image.Image:
    avatar = Image.open(ruta_avatar).convert("RGBA")
    lado = min(avatar.size)
    avatar = avatar.crop((0, 0, lado, lado)).resize((tamano, tamano), Image.LANCZOS)
    mascara = Image.new("L", (tamano, tamano), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, tamano, tamano), fill=255)
    resultado = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    resultado.paste(avatar, (0, 0), mascara)
    return resultado


def _triangulo_arriba(draw: ImageDraw.ImageDraw, cx: int, cy: int, tamano: int, color):
    puntos = [(cx, cy - tamano), (cx - tamano, cy + tamano * 0.7), (cx + tamano, cy + tamano * 0.7)]
    draw.polygon(puntos, fill=color)


def _icono_comentario(draw: ImageDraw.ImageDraw, cx: int, cy: int, tamano: int, color):
    box = [cx - tamano, cy - tamano * 0.75, cx + tamano, cy + tamano * 0.55]
    draw.rounded_rectangle(box, radius=tamano * 0.4, outline=color, width=5)
    cola = [
        (cx - tamano * 0.3, cy + tamano * 0.5),
        (cx - tamano * 0.55, cy + tamano * 1.05),
        (cx + tamano * 0.05, cy + tamano * 0.5),
    ]
    draw.polygon(cola, fill=color)
    draw.rectangle(
        [cx - tamano * 0.4, cy + tamano * 0.4, cx + tamano * 0.2, cy + tamano * 0.6],
        fill=(255, 255, 255, 255),
    )


def _icono_compartir(draw: ImageDraw.ImageDraw, cx: int, cy: int, tamano: int, color):
    draw.line([(cx - tamano, cy + tamano * 0.6), (cx + tamano, cy - tamano * 0.6)], fill=color, width=6)
    draw.line([(cx + tamano * 0.15, cy - tamano * 0.6), (cx + tamano, cy - tamano * 0.6)], fill=color, width=6)
    draw.line([(cx + tamano, cy - tamano * 0.6), (cx + tamano, cy + tamano * 0.15)], fill=color, width=6)


def crear_tarjeta_titulo(
    titulo: str,
    ruta_salida: str,
    ancho: int = ANCHO,
    alto: int = ALTO,
    channel_name: str = CHANNEL_NAME,
    avatar_path: str = AVATAR_PATH,
) -> str:
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margen_x = 60
    padding = 40
    avatar_tamano = 90
    card_x0, card_x1 = margen_x, ancho - margen_x
    card_y0 = 130

    fuente_canal = _cargar_fuente(FUENTES_BOLD, 34)
    fuente_titulo = _cargar_fuente(FUENTES_BOLD, 50)
    fuente_stats = _cargar_fuente(FUENTES_BOLD, 32)
    fuente_share = _cargar_fuente(FUENTES_NORMAL, 30)
    tamano_emoji = 34

    ancho_texto_titulo = (card_x1 - card_x0) - padding * 2
    caracteres_por_linea = max(10, int(ancho_texto_titulo / (fuente_titulo.size * 0.55)))
    lineas_titulo = textwrap.wrap(titulo, width=caracteres_por_linea) or [titulo]

    line_height_titulo = fuente_titulo.size + 16
    header_height = avatar_tamano + tamano_emoji + 20  # avatar + hueco para fila de emojis
    titulo_height = line_height_titulo * len(lineas_titulo) + 20
    footer_height = 90

    card_height = padding + header_height + titulo_height + footer_height + padding
    card_y1 = card_y0 + card_height

    # --- sombra + tarjeta ---
    draw.rounded_rectangle(
        [card_x0 + 8, card_y0 + 14, card_x1 + 8, card_y1 + 14], radius=45, fill=COLOR_SOMBRA
    )
    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=45, fill=COLOR_TARJETA)

    # --- avatar + nombre del canal + fila de emojis ---
    avatar_x = card_x0 + padding
    avatar_y = card_y0 + padding
    try:
        avatar_img = _avatar_circular(avatar_path, avatar_tamano)
        img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
    except FileNotFoundError:
        draw.ellipse(
            [avatar_x, avatar_y, avatar_x + avatar_tamano, avatar_y + avatar_tamano],
            fill=(60, 60, 60, 255),
        )

    nombre_x = avatar_x + avatar_tamano + 24
    nombre_y = avatar_y
    draw.text((nombre_x, nombre_y), channel_name, font=fuente_canal, fill=COLOR_TEXTO_CANAL)

    emoji_y = nombre_y + fuente_canal.size + 8
    if REACTION_EMOJIS.strip():
        _dibujar_emojis(draw, nombre_x, emoji_y, REACTION_EMOJIS, tamano_emoji)

    # --- título / pregunta ---
    y = card_y0 + padding + header_height
    for linea in lineas_titulo:
        draw.text((card_x0 + padding, y), linea, font=fuente_titulo, fill=COLOR_TEXTO_TITULO)
        y += line_height_titulo

    # --- línea separadora ---
    linea_y = card_y1 - footer_height
    draw.line([(card_x0 + padding, linea_y), (card_x1 - padding, linea_y)], fill=COLOR_LINEA, width=3)

    # --- fila de upvote / comentarios / share ---
    fila_y = linea_y + footer_height // 2
    icon_r = 22

    x_upvote = card_x0 + padding + icon_r
    _triangulo_arriba(draw, x_upvote, fila_y, icon_r, COLOR_GRIS)
    draw.text(
        (x_upvote + icon_r + 12, fila_y - fuente_stats.size // 2),
        UPVOTES_COUNT, font=fuente_stats, fill=COLOR_GRIS,
    )

    x_comentario = card_x0 + (card_x1 - card_x0) // 2 - 40
    _icono_comentario(draw, x_comentario, fila_y, icon_r, COLOR_GRIS)
    draw.text(
        (x_comentario + icon_r + 16, fila_y - fuente_stats.size // 2),
        COMMENTS_COUNT, font=fuente_stats, fill=COLOR_GRIS,
    )

    x_share = card_x1 - padding - 140
    _icono_compartir(draw, x_share, fila_y, icon_r, COLOR_GRIS)
    draw.text(
        (x_share + icon_r + 14, fila_y - fuente_share.size // 2),
        SHARE_LABEL, font=fuente_share, fill=COLOR_GRIS,
    )

    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    img.save(ruta_salida)
    print(f"Tarjeta de título generada: {ruta_salida}", flush=True)
    return ruta_salida


def crear_miniatura_video(
    titulo: str,
    ruta_salida: str,
    channel_name: str = CHANNEL_NAME,
    avatar_path: str = AVATAR_PATH,
) -> str:
    """Miniatura 16:9: una caja de comentario grande, limpia y legible."""
    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = salida.with_name(f"{salida.stem}_tarjeta.png")
    crear_tarjeta_titulo(
        titulo, str(temporal), ancho=1280, alto=720,
        channel_name=channel_name, avatar_path=avatar_path,
    )
    fondo = Image.new("RGBA", (1280, 720), (20, 9, 5, 255))
    draw = ImageDraw.Draw(fondo)
    for y in range(720):
        proporcion = y / 719
        draw.line((0, y, 1280, y), fill=(
            int(48 + 70 * (1 - proporcion)),
            int(16 + 25 * (1 - proporcion)),
            int(8 + 8 * (1 - proporcion)),
            255,
        ))
    with Image.open(temporal).convert("RGBA") as tarjeta:
        fondo.alpha_composite(tarjeta)
    fondo.convert("RGB").save(salida, "JPEG", quality=94, optimize=True)
    temporal.unlink(missing_ok=True)
    print(f"Miniatura grande generada: {salida}", flush=True)
    return str(salida)


if __name__ == "__main__":
    crear_tarjeta_titulo(
        "What's the biggest lie you told that completely spiraled out of control?",
        "salida/titulo.png",
    )
