"""
Ejecuta esto SOLO UNA VEZ: abre un navegador real para que inicies sesión
en Reddit a mano, y guarda esa sesión (cookies) en reddit_session.json.

El scraper reutiliza esa sesión después para comportarse como un usuario
real logueado, en vez de peticiones anónimas que Reddit bloquea con 403.

Instalar (una sola vez):
    pip install playwright
    playwright install chromium
"""
from playwright.sync_api import sync_playwright

RUTA_SESION = "reddit_session.json"


def main():
    with sync_playwright() as p:
        navegador = p.chromium.launch(
            headless=False,
            channel="chrome",  # usa tu Chrome real instalado, no el Chromium interno de Playwright
            args=["--disable-blink-features=AutomationControlled"],
        )
        contexto = navegador.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        contexto.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        pagina = contexto.new_page()
        pagina.goto("https://www.reddit.com/login")

        print("Se ha abierto una ventana de Chrome.")
        print("Inicia sesión en tu cuenta de Reddit ahí normalmente.")
        input("Cuando ya veas tu feed de Reddit logueado, vuelve aquí y pulsa Enter...")

        contexto.storage_state(path=RUTA_SESION)
        print(f"\nSesión guardada en {RUTA_SESION}. Ya puedes usar reddit_scraper.py normal.")
        navegador.close()


if __name__ == "__main__":
    main()
