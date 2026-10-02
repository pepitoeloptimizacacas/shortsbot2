"""
Busca posts tipo "historia" en un conjunto de subreddits usando un
navegador real (Playwright) con una sesión ya logueada, para evitar el
bloqueo 403 que sufren las peticiones anónimas normales.

ANTES DE USAR ESTO: corre una vez playwright_setup.py para iniciar sesión
y generar reddit_session.json.

Instalar:
    pip install playwright
    playwright install chromium
"""
import json
import re
import time
from pathlib import Path
from estado_bot import guardar_json
from filtro_misterio import puntuar_misterio, FUENTES_FICCION

SUBREDDITS_HISTORIAS = [
    "nosleep",
    "shortscarystories",
    "creepypasta",
    "Glitch_in_the_Matrix",
    "TrueScaryStories",
    "creepyencounters",
    "Paranormal",
]

# En AskReddit las historias no están en el post, sino en sus respuestas.
SUBREDDIT_ASKREDDIT = "AskReddit"
SUBREDDITS = [*SUBREDDITS_HISTORIAS, SUBREDDIT_ASKREDDIT]

PISTAS_ASKREDDIT = re.compile(
    r"\b(?:creep(?:y|iest)|scariest|terrifying|disturbing|unexplained|paranormal|"
    r"myster(?:y|ious)|bizarre|sinister|haunted|stalk(?:er|ed|ing)|close call|"
    r"horror|nightmare|strange encounter|darkest secret|cannot explain|can't explain)\b",
    re.I,
)

MIN_LENGTH = 800    # caracteres mínimos para que dé para un short de 60-90s
MAX_LENGTH = 3500   # evitar historias demasiado largas
MIN_UPVOTES = 50
PAUSA_ENTRE_PETICIONES = 2.5  # segundos, para no parecer un bot agresivo

RUTA_SESION = Path("reddit_session.json")
USADOS_PATH = Path("historias_usadas.json")


def _cargar_usados() -> set:
    if USADOS_PATH.exists():
        return set(json.loads(USADOS_PATH.read_text(encoding="utf-8")))
    return set()


def _guardar_usado(post_id: str):
    usados = _cargar_usados()
    usados.add(post_id)
    guardar_json(USADOS_PATH, sorted(usados))


def _obtener_posts_subreddit(pagina, nombre_sub: str, limite: int = 15) -> list[dict]:
    url = f"https://www.reddit.com/r/{nombre_sub}/top.json?limit={limite}&t=month&raw_json=1"
    respuesta = pagina.goto(url)

    if respuesta is None or respuesta.status != 200:
        estado = respuesta.status if respuesta else "sin respuesta"
        print(f"  [!] r/{nombre_sub}: respuesta {estado}, se salta.")
        return []

    contenido = pagina.evaluate("() => document.body.innerText")
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError:
        print(f"  [!] r/{nombre_sub}: la respuesta no es JSON válido, se salta.")
        return []

    return [child["data"] for child in datos.get("data", {}).get("children", [])]


def _es_hilo_askreddit_interesante(post: dict) -> bool:
    """Evita preguntas cotidianas: solo abre hilos que prometen relatos inquietantes."""
    titulo = post.get("title", "")
    return bool(PISTAS_ASKREDDIT.search(titulo)) and not post.get("stickied") and not post.get("over_18")


def _obtener_comentarios_askreddit(pagina, post_id: str, limite: int = 50) -> list[dict]:
    url = (
        f"https://www.reddit.com/comments/{post_id}.json"
        f"?sort=top&limit={limite}&depth=1&raw_json=1"
    )
    respuesta = pagina.goto(url)
    if respuesta is None or respuesta.status != 200:
        estado = respuesta.status if respuesta else "sin respuesta"
        print(f"  [!] AskReddit/{post_id}: respuesta {estado}, se salta.")
        return []

    contenido = pagina.evaluate("() => document.body.innerText")
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError:
        print(f"  [!] AskReddit/{post_id}: la respuesta no es JSON válido, se salta.")
        return []

    if not isinstance(datos, list) or len(datos) < 2:
        return []
    return [
        child.get("data", {})
        for child in datos[1].get("data", {}).get("children", [])
        if child.get("kind") == "t1"
    ]


def _candidatos_askreddit(pagina, posts: list[dict], usados: set,
                          min_length: int, max_length: int) -> list[dict]:
    candidatos = []
    # Abrir pocos hilos de alta calidad mantiene el scraper rápido y respetuoso.
    hilos = [p for p in posts if _es_hilo_askreddit_interesante(p)][:10]
    for post in hilos:
        post_id = post.get("id")
        if not post_id:
            continue
        comentarios = _obtener_comentarios_askreddit(pagina, post_id)
        for comentario in comentarios:
            comentario_id = comentario.get("id")
            candidato_id = f"askreddit-{post_id}-{comentario_id}"
            texto = (comentario.get("body") or "").strip()
            autor = (comentario.get("author") or "").casefold()
            if not comentario_id or candidato_id in usados:
                continue
            if autor in {"automoderator", "[deleted]"} or autor.endswith("bot"):
                continue
            if texto in {"[removed]", "[deleted]"} or not (min_length <= len(texto) <= max_length):
                continue
            if comentario.get("score", 0) < MIN_UPVOTES:
                continue
            intriga = puntuar_misterio(post.get("title", ""), texto)
            if intriga < 2:
                continue
            permalink = comentario.get("permalink") or post.get("permalink", "")
            candidatos.append({
                "id": candidato_id,
                "subreddit": SUBREDDIT_ASKREDDIT,
                "title": post.get("title", ""),
                "text": texto,
                "score": comentario.get("score", 0),
                "intriga": intriga,
                "ficcion": False,
                "url": f"https://reddit.com{permalink}",
            })
        time.sleep(PAUSA_ENTRE_PETICIONES)
    return candidatos


def buscar_candidatos(limite_por_sub: int = 100, max_candidatos: int = 12,
                      min_length: int = MIN_LENGTH, max_length: int = MAX_LENGTH) -> list[dict]:
    """Devuelve una lista de historias candidatas: {id, subreddit, title, text, score, url}."""
    from playwright.sync_api import sync_playwright

    if not RUTA_SESION.exists():
        raise RuntimeError(
            "No existe reddit_session.json. Corre primero playwright_setup.py "
            "para iniciar sesión en Reddit y generar la sesión."
        )

    usados = _cargar_usados()
    candidatos = []

    with sync_playwright() as p:
        navegador = p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        contexto = navegador.new_context(
            storage_state=str(RUTA_SESION),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        contexto.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        pagina = contexto.new_page()

        for nombre_sub in SUBREDDITS:
            posts = _obtener_posts_subreddit(pagina, nombre_sub, limite_por_sub)

            if nombre_sub == SUBREDDIT_ASKREDDIT:
                candidatos.extend(
                    _candidatos_askreddit(pagina, posts, usados, min_length, max_length)
                )
                continue

            for post in posts:
                post_id = post.get("id")
                texto = (post.get("selftext") or "").strip()

                if not post_id or post_id in usados:
                    continue
                if post.get("stickied") or post.get("over_18") or texto in ("[removed]", "[deleted]") or not texto:
                    continue
                if not (min_length <= len(texto) <= max_length):
                    continue
                if post.get("score", 0) < MIN_UPVOTES:
                    continue
                intriga = puntuar_misterio(post.get('title', ''), texto)
                if intriga < 2:
                    continue

                candidatos.append({
                    "id": post_id,
                    "subreddit": nombre_sub,
                    "title": post.get("title", ""),
                    "text": texto,
                    "score": post.get("score", 0),
                    "intriga": intriga,
                    "ficcion": nombre_sub.casefold() in FUENTES_FICCION,
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                })

            time.sleep(PAUSA_ENTRE_PETICIONES)

        navegador.close()

    candidatos.sort(key=lambda c: (c['intriga'], c["score"]), reverse=True)
    return candidatos[:max_candidatos]


if __name__ == "__main__":
    candidatos = buscar_candidatos()
    print(f"\nEncontrados {len(candidatos)} candidatos:\n")
    for c in candidatos:
        print(f"[{c['score']:>6}] r/{c['subreddit']} - {c['title'][:70]}")
