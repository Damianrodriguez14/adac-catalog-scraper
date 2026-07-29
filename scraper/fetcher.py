"""
fetcher.py
Descarga páginas de forma responsable: rate limiting, reintentos con backoff,
headers de un navegador real, y chequeo de robots.txt antes de arrancar.
"""

import time
import random
import logging
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://www.adac.de"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Rango de pausa entre requests (segundos) -- variable para no parecer un bot
# con timing perfectamente regular.
MIN_DELAY = 1.5
MAX_DELAY = 3.0

MAX_RETRIES = 3
TIMEOUT = 15


class RobotsBlocked(Exception):
    """La ruta está deshabilitada en robots.txt -- no se scrapea."""


class Fetcher:
    def __init__(self, base_url: str = BASE_URL, respect_robots: bool = True):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.robots = None
        if respect_robots:
            self.robots = RobotFileParser()
            self.robots.set_url(urljoin(base_url, "/robots.txt"))
            try:
                self.robots.read()
                log.info("robots.txt cargado desde %s", urljoin(base_url, "/robots.txt"))
            except Exception as e:
                log.warning("No se pudo leer robots.txt (%s) -- se continúa con precaución", e)
                self.robots = None

    def _allowed(self, url: str) -> bool:
        if self.robots is None:
            return True
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self._allowed(url):
            raise RobotsBlocked(f"robots.txt no permite scrapear: {url}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                if resp.status_code == 200:
                    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                    return resp.text
                elif resp.status_code == 429:
                    wait = 2 ** attempt * 5
                    log.warning("429 (rate limited) en %s -- esperando %ss", url, wait)
                    time.sleep(wait)
                elif resp.status_code == 403:
                    log.error("403 en %s -- posible bloqueo anti-bot. Abortando esta URL.", url)
                    return None
                else:
                    log.warning("Status %s en %s (intento %s/%s)", resp.status_code, url, attempt, MAX_RETRIES)
                    time.sleep(2 ** attempt)
            except requests.RequestException as e:
                log.warning("Error de red en %s: %s (intento %s/%s)", url, e, attempt, MAX_RETRIES)
                time.sleep(2 ** attempt)

        log.error("Falló definitivamente: %s", url)
        return None
