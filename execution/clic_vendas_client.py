"""
clic_vendas_client.py
=====================
Cliente para a API REST do Clic Vendas.
Gerencia autenticacao JWT com refresh automatico de tokens.

Uso:
    from clic_vendas_client import ClicVendasClient
    client = ClicVendasClient()
    pedidos = client.get('/extpedidos')
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ClicVendasClient:
    """
    Cliente REST para API Clic Vendas com autenticacao JWT.

    Gerencia tokens automaticamente:
    - Faz login na primeira requisicao
    - Renova token quando expira (via refresh ou re-login)
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        subdomain: str | None = None,
        credential_label: str | None = None,
    ):
        self.base_url = os.getenv('CLIC_VENDAS_URL', '').rstrip('/')
        self.auth_url = os.getenv('CLIC_VENDAS_AUTH_URL', '').rstrip('/')
        self.username = username or os.getenv('CLIC_VENDAS_USER', '')
        self.password = password or os.getenv('CLIC_VENDAS_PASSWORD', '')
        self.subdomain = subdomain or os.getenv('CLIC_VENDAS_SUBDOMAIN', 'sucosspres')
        self.credential_label = credential_label or 'global'

        if not all([self.base_url, self.auth_url, self.username, self.password]):
            raise ValueError(
                'Configuracao Clic Vendas incompleta. '
                'Verifique CLIC_VENDAS_URL, CLIC_VENDAS_AUTH_URL, CLIC_VENDAS_USER e CLIC_VENDAS_PASSWORD no .env'
            )

        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = 0

        # Sessao HTTP para reutilizar conexoes
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'subdominio': self.subdomain,  # Header obrigatorio para API multi-tenant
        })

    @classmethod
    def for_representative(cls, cod_rep: int | str | None, fallback: bool = True):
        """Cria cliente com credenciais especificas do representante, se configuradas."""
        code = str(cod_rep or "").strip()
        if code:
            safe_code = "".join(ch for ch in code if ch.isalnum() or ch == "_")
            user = os.getenv(f"CLIC_VENDAS_REP_{safe_code}_USER", "").strip()
            password = os.getenv(f"CLIC_VENDAS_REP_{safe_code}_PASSWORD", "").strip()
            subdomain = os.getenv(f"CLIC_VENDAS_REP_{safe_code}_SUBDOMAIN", "").strip() or None
            if user and password:
                return cls(
                    username=user,
                    password=password,
                    subdomain=subdomain,
                    credential_label=f"rep:{safe_code}",
                )
            if not fallback:
                raise ValueError(f"Credenciais ClicVendas do representante {safe_code} nao configuradas")
        return cls()

    def _login(self) -> bool:
        """
        Realiza login e obtem tokens JWT.
        Usa servidor de autenticacao separado (auth_url).

        Returns:
            True se login bem-sucedido, False caso contrario.
        """
        url = f'{self.auth_url}/login'
        payload = {
            'login': self.username,
            'senha': self.password,
            'subdominio': self.subdomain,
        }

        logger.info('Clic Vendas: Realizando login (%s)...', self.credential_label)

        try:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            self.access_token = data.get('accessToken')
            self.refresh_token = data.get('refreshToken')

            # Token JWT tipicamente expira em 1h, usamos 50min para margem
            self.token_expires_at = time.time() + 3000

            logger.info('Clic Vendas: Login bem-sucedido (%s)', self.credential_label)
            return True

        except requests.exceptions.HTTPError as e:
            logger.error('Clic Vendas: Falha no login - HTTP %s: %s', e.response.status_code, e.response.text)
            return False
        except Exception as e:
            logger.error('Clic Vendas: Erro no login - %s', e)
            return False

    def _refresh_access_token(self) -> bool:
        """
        Renova o access token usando o refresh token.
        Usa servidor de autenticacao separado (auth_url).

        Returns:
            True se refresh bem-sucedido, False caso contrario.
        """
        if not self.refresh_token:
            return False

        url = f'{self.auth_url}/refresh'
        payload = {'refreshToken': self.refresh_token}

        logger.debug('Clic Vendas: Renovando token...')

        try:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            self.access_token = data.get('accessToken')
            self.refresh_token = data.get('refreshToken')
            self.token_expires_at = time.time() + 3000

            logger.debug('Clic Vendas: Token renovado')
            return True

        except Exception as e:
            logger.warning('Clic Vendas: Falha ao renovar token - %s', e)
            return False

    def _ensure_authenticated(self):
        """Garante que temos um token valido antes de fazer requisicoes."""
        # Se token ainda valido, nada a fazer
        if self.access_token and time.time() < self.token_expires_at:
            return

        # Tenta refresh primeiro
        if self.refresh_token and self._refresh_access_token():
            return

        # Fallback: re-login
        if not self._login():
            raise RuntimeError('Clic Vendas: Falha na autenticacao')

    def _get_headers(self) -> dict:
        """Retorna headers com token de autorizacao."""
        return {'Authorization': f'Bearer {self.access_token}'}

    def get(self, endpoint: str, params: dict = None) -> dict | list:
        """
        Faz requisicao GET autenticada.

        Args:
            endpoint: Caminho do endpoint (ex: '/extpedidos')
            params: Query parameters opcionais

        Returns:
            Resposta JSON parseada.
        """
        self._ensure_authenticated()

        url = f'{self.base_url}{endpoint}'

        try:
            resp = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.HTTPError as e:
            # Se 401, tenta re-autenticar uma vez
            if e.response.status_code == 401:
                logger.warning('Clic Vendas: Token expirado, re-autenticando...')
                if self._login():
                    resp = self.session.get(
                        url,
                        params=params,
                        headers=self._get_headers(),
                        timeout=60,
                    )
                    resp.raise_for_status()
                    return resp.json()
            raise

    def post(self, endpoint: str, data: dict = None) -> dict:
        """
        Faz requisicao POST autenticada.

        Args:
            endpoint: Caminho do endpoint
            data: Payload JSON

        Returns:
            Resposta JSON parseada.
        """
        self._ensure_authenticated()

        url = f'{self.base_url}{endpoint}'

        try:
            resp = self.session.post(
                url,
                json=data,
                headers=self._get_headers(),
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning('Clic Vendas: Token expirado, re-autenticando...')
                if self._login():
                    resp = self.session.post(
                        url,
                        json=data,
                        headers=self._get_headers(),
                        timeout=60,
                    )
                    resp.raise_for_status()
                    return resp.json()
            raise


# ============================================
# CLI - Teste de conexao
# ============================================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    print('='*60)
    print('Teste de Conexao - Clic Vendas API')
    print('='*60)

    try:
        client = ClicVendasClient()
        print(f'API URL: {client.base_url}')
        print(f'Auth URL: {client.auth_url}')
        print(f'Usuario: {client.username}')
        print()

        # Testa login
        if client._login():
            print('[OK] Login realizado com sucesso!')
            print(f'Access Token: {client.access_token[:50]}...')
        else:
            print('[ERRO] Falha no login')

    except Exception as e:
        print(f'[ERRO] {e}')
