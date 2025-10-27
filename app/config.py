import os
import threading
from dotenv import load_dotenv

load_dotenv()

# --- Carregamento de Segredos (Iniciação da API) ---
MFA_SECRET_KEY = os.environ.get("MFA_SECRET_KEY")
LOGIN_USER = os.environ.get("LOGIN_USER")
LOGIN_PASS = os.environ.get("LOGIN_PASS")
API_KEY = os.environ.get("API_KEY")
FIXED_CLIENT_ID = os.environ.get("FIXED_CLIENT_ID")

if not all([MFA_SECRET_KEY, LOGIN_USER, LOGIN_PASS, API_KEY, FIXED_CLIENT_ID]):
    raise ValueError(
        "Uma ou mais variáveis de ambiente estão faltando. "
        "Verifique .env (MFA_SECRET_KEY, LOGIN_USER, LOGIN_PASS, API_KEY, FIXED_CLIENT_ID)"
    )

# --- Constantes Globais ---
BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/5.36'
}
API_SEARCH_URL = "https://www.ttravel.com.br/ttravelapi/reservas/BuscarDisponibilidade"
LOGIN_PROCESS_URL = "https://www.ttravel.com.br/connect/login/"
FRAME_URL = "https://www.ttravel.com.br/connect/login/frmnovoframeui.aspx?os="
USERNAME_FIELD = 'Login1$txtLogin'
PASSWORD_FIELD = 'Login1$txtSenha'
LOGIN_BUTTON_FIELD = 'Login1$btnLogarEmp'
MFA_FIELD = 'Login1$txtCodigoSecurityCard'
MFA_BUTTON_FIELD = 'Login1$btnEntrarSecurityCard'
CLIENT_SELECT_PAGE_IDENTIFIER = "frmAcessoAgenciasUI.aspx"
FLIGHT_SEARCH_PAGE_IDENTIFIER = "frmBuscaDispAereo.aspx"

# Lista de trechos fixos para o novo endpoint
TRECHOS_FIXOS = [
    ("CGH", "SSA"),
    ("BSB", "SSA"),
    ("GIG", "SSA"),
    ("FOR", "SSA"),
    ("AJU", "GRU")
]

MAX_CONCURRENT_JOBS = 3 
CONCURRENCY_LIMIT = threading.Semaphore(MAX_CONCURRENT_JOBS)