import base64
import tempfile
import os
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from requests import Session
from zeep import Client
from zeep.transports import Transport
from app.core.security import descriptografar

WSDL_PRODUCAO = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx?WSDL"

def criar_sessao_ssl(cert_base64_cripto, senha_cripto):
    """Descriptografa o PFX e devolve uma Session sem certificado anexado."""
    cert_pfx_base64 = descriptografar(cert_base64_cripto)
    cert_senha = descriptografar(senha_cripto).encode()
    pfx_data = base64.b64decode(cert_pfx_base64)

    private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
        pfx_data, cert_senha, default_backend()
    )

    session = Session()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file, \
         tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as key_file:
        pass 

    return session

def buscar_notas(empresa):
    print(f"🔍 Consultando SEFAZ para {empresa.cnpj} a partir do NSU {empresa.ultimo_nsu}...")
    return []