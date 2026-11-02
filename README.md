# BeatleXML

BeatleXML é a aplicação web deste Trabalho de Conclusão de Curso em Sistemas de Informação. O repositório público é <https://github.com/Willfragatta/TCC_BeatleXml>.

O sistema reúne:

- uma plataforma web em FastAPI;
- PostgreSQL 16, no schema `nfe_app`;
- um worker de comunicação fiscal, separado da subida padrão;
- o agente de desktop Beatle Uploader;
- o agente de desktop Beatle Contador;
- a extração de parcelas a partir dos XML de NF-e.

A demonstração descrita aqui usa dados sintéticos. Ela não exige certificado digital e não está apresentada como ambiente de produção. Subir os contêineres não torna o software apto a operar com documentos fiscais reais.

Os comandos foram conferidos com os arquivos versionados. O shell usado nesta documentação é o PowerShell. No Git Bash, os mesmos comandos `docker` valem; troque apenas as barras invertidas dos caminhos por barras normais. A execução dos agentes foi descrita para Windows. Linux e macOS não foram verificados.

## Arquitetura resumida

Há três camadas.

A aplicação web atende o navegador em `http://localhost:8000`, autentica os usuários, guarda os XML e extrai as parcelas. O PostgreSQL persiste empresas, vínculos, notas e obrigações. Os dois agentes rodam na máquina local, fora do Docker, e falam com a API. O certificado A1, quando existe, permanece no servidor. O computador do contador não consulta a SEFAZ.

## Pré-requisitos

- Git.
- Docker Desktop para Windows, com Docker Compose e WSL 2 marcados na instalação: <https://www.docker.com/products/docker-desktop/>.
- Python 3.12 na máquina, somente para os agentes e para `scripts/verificar_fluxos.py`. A imagem do [Dockerfile](Dockerfile) é `python:3.12-slim`. Use o mesmo interpretador no `python` e no `python -m pip`.
- Portas livres: `8000` (aplicação), `5432` (PostgreSQL), `8025` (Mailpit) e `1025` (SMTP do Mailpit).

## Instalação rápida

Na pasta em que o repositório deve ficar:

```powershell
git clone https://github.com/Willfragatta/TCC_BeatleXml.git
cd TCC_BeatleXml
docker compose up --build
```

Deixe esse terminal aberto. Na primeira subida, o contêiner executa `python app/core/init_db.py`, depois `python scripts/seed.py`, e então o Uvicorn na porta 8000. `init_db.py` cria o schema `nfe_app` se ele não existir e sincroniza as tabelas. `seed.py` grava a carga fictícia.

Abra outro PowerShell na mesma pasta e confira os contêineres:

```powershell
docker compose ps
```

Os serviços `app`, `db` e `mailpit` precisam estar em execução. Abra:

- aplicação: <http://localhost:8000>
- caixa de e-mail local: <http://localhost:8025>

O log da primeira carga mostra as tabelas criadas e a carga gravada. Se `suporte@demo.local` já existir, o seed imprime que a carga já existe e não duplica o banco. O arquivo `scripts/fixtures/nfce-caixa.xml` é reescrito a cada execução do seed.

Para subir de novo sem reconstruir a imagem, na raiz:

```powershell
docker compose up
```

## Ambiente de demonstração

O [docker-compose.yml](docker-compose.yml) fixa `ENV=development` e credenciais usadas só nesta banca. Elas não devem ser reutilizadas em produção. O arquivo `.env` da pasta não entra na imagem: o [`.dockerignore`](.dockerignore) o exclui. O contêiner lê o bloco `environment` do Compose.

A carga cria quatro organizações fictícias:

| Organização | CNPJ | Vínculo |
| --- | --- | --- |
| Mercado Bom Preço Matriz Ltda | 11.222.333/0001-81 | Grupo do gestor e do contador |
| Mercado Bom Preço Filial Ltda | 11.222.333/0002-62 | Grupo do gestor e do contador |
| Papelaria Folha Nova Ltda | 33.444.555/0001-81 | Grupo do gestor e do contador |
| Padaria Isolada Ltda | 99.888.777/0001-00 | Só o usuário `outro@demo.local` |

As senhas abaixo são públicas e valem apenas para esta demonstração.

| E-mail | Senha | Papel |
| --- | --- | --- |
| gestor@demo.local | Gestor#2026 | Master da matriz, da filial e da papelaria |
| operador@demo.local | Operador#2026 | Operador só da matriz |
| leitura@demo.local | Leitura#2026 | Somente leitura da matriz |
| contador@demo.local | Contador#2026 | Matriz, filial e papelaria. Não vê a Padaria Isolada |
| suporte@demo.local | Suporte#2026 | Suporte. Vê as quatro empresas |
| outro@demo.local | Outro#2026 | Master só da Padaria Isolada |

A matriz já contém uma NF-e de entrada com duas parcelas em aberto, uma NFC-e emitida e a etiqueta Conferir. Nomes, CNPJs e XML são inventados.

A empresa ativa fica no cookie `empresa_ativa`, gravado pelo seletor lateral. Sem esse cookie, a primeira empresa devolvida pela API pode não ser a matriz. Antes de abrir notas ou financeiro com o gestor, escolha **Mercado Bom Preço Matriz Ltda** nesse seletor.

## Recursos disponíveis

Com a matriz selecionada:

- **Notas fiscais** em <http://localhost:8000/notas>. A listagem padrão mostra documentos recebidos.
- **Exportação ZIP** na própria listagem. O perfil leitura recebe HTTP 403 nessa escrita. O contador, com a matriz ativa, recebe um ZIP que contém XML.
- **Contas a pagar** em <http://localhost:8000/financeiro>. As duas parcelas pendentes vêm do grupo de cobrança da NF-e de exemplo.
- **Usuários e papéis** em <http://localhost:8000/usuarios>, na conta do gestor. O master altera vínculos. O perfil leitura não grava.
- **Etiquetas** na tela de notas recebidas. A carga já aplica a etiqueta Conferir.
- **DANFE da NF-e modelo 55**, aberto a partir da nota recebida. A geração usa `BrazilFiscalReport`. Uma execução anterior, neste Docker, produziu um PDF cujo conteúdo começa com `%PDF`.
- **NFC-e modelo 65.** A rota existe e usa `erpbrasil.edoc.pdf`. Na mesma execução anterior, o DANFC-e respondeu HTTP 500 por falta do backend `rlPyCairo` na imagem. Este guia não trata esse PDF como verificado.
- **Uploader e Contador**, nas seções seguintes.
- **Autenticação em dois fatores** em <http://localhost:8000/config>. O 2FA começa desligado. Ao ligar, o código do próximo login aparece no Mailpit.

## Beatle Uploader

O agente fica fora do Docker. A aplicação precisa estar no ar. Abra o PowerShell na raiz do repositório, a pasta que contém `beatle_uploader`.

Confira se o `pip` é o do mesmo Python que vai executar o programa:

```powershell
python -c "import sys; print(sys.executable)"
python -m pip -V
```

As duas linhas precisam apontar para a mesma pasta. Se `python` abrir a Microsoft Store, instale o Python 3.12 em <https://www.python.org/downloads/windows/>, marque **Add python.exe to PATH** e abra um PowerShell novo.

```powershell
python -m pip install -r beatle_uploader\requirements.txt
python beatle_uploader\main.py
```

Não entre na pasta `beatle_uploader` para chamar o módulo. A URL inicial é `http://localhost:8000`. Entre com `gestor@demo.local` e `Gestor#2026`, escolha a empresa cujo CNPJ é o da matriz e indique uma pasta. Copie `scripts\fixtures\nfce-caixa.xml` para essa pasta e clique em **Iniciar monitoramento**. O emitente desse XML é a matriz. O monitoramento não apaga nem move o arquivo original. Fechar a janela no X só esconde o programa na bandeja. Use **Parar** dentro da janela para interromper o envio.

O executável é opcional. Não há `tools\build_uploader.bat` neste repositório. Na raiz, com o mesmo Python:

```powershell
python -m pip install pyinstaller
python -m PyInstaller beatle_uploader\build.spec
```

O arquivo sai em `dist\BeatleUploader.exe`.

## Beatle Contador

Em outro PowerShell, ainda na raiz e com o site no ar:

```powershell
python -m pip install -r beatle_contador\requirements.txt
python beatle_contador\main.py
```

A URL inicial também é `http://localhost:8000`. Entre com `contador@demo.local` e `Contador#2026`. O programa lista as três empresas do grupo, envia presença (heartbeat) e oferece **Parar buscas**, com opção de retomada automática em 2 horas. Quem fala com a SEFAZ é o servidor, e só quando a empresa tem certificado A1. Esta demonstração não pede esse certificado: as senhas do Compose são públicas, e um certificado real não deve ser gravado aqui.

O empacotamento também é opcional. Não há `tools\build_contador.bat`.

```powershell
python -m PyInstaller beatle_contador\build.spec
```

O arquivo sai em `dist\BeatleContador.exe`. A página `/contador` aponta um download para `static/releases/BeatleContador-1.1.0.exe`. Esse arquivo não acompanha o repositório. A demonstração não depende dele.

## Testes reproduzíveis

`scripts/verificar_fluxos.py` fala com a aplicação já em execução em `http://localhost:8000`. Rode-o somente neste ambiente isolado, com o banco sintético do Compose. O script grava dados: envia `scripts/fixtures/nfce-caixa.xml` pela API do Uploader e liga e desliga o 2FA do gestor. No fim, o 2FA volta a ficar desligado. Não use esse comando contra um banco que tenha notas ou certificados reais.

Na raiz, com a aplicação no ar:

```powershell
python -m pip install requests
python scripts\verificar_fluxos.py
```

O script, no estado atual do arquivo, faz o seguinte:

- autentica gestor, operador, leitura, contador e suporte;
- confere que gestor e contador não listam a Padaria Isolada e que o suporte a lista;
- seleciona a matriz pelo CNPJ `11222333000181`, gravando o cookie `empresa_ativa`;
- exige ao menos uma nota recebida e ao menos uma parcela pendente;
- espera HTTP 403 no ZIP pedido pelo perfil leitura;
- espera um ZIP com XML no pedido do contador;
- espera um DANFE da nota recebida cujo conteúdo comece com `%PDF`;
- envia o fixture pela API do Uploader;
- autentica o agente do contador e confere a lista de empresas, sem a padaria;
- liga o 2FA, espera o redirecionamento para `verificar-2fa`, conta mensagens no Mailpit e desliga o 2FA.

O script não chama `POST /api/contador/sincronizar/{id}`. Essa rota executa o worker na própria requisição e ficou fora da bateria. Não há, neste repositório, um registro de que essa bateria tenha sido executada depois dessa remoção. Uma saída `fluxos ok` só vale para a rodada em que o comando foi de fato executado.

## reCAPTCHA e e-mail

Com `ENV=development` e as chaves `RECAPTCHA_SITE_KEY` e `RECAPTCHA_SECRET_KEY` vazias, como vêm no Compose, o servidor não consulta o Google. Login, cadastro e recuperação de senha seguem sem captcha. Confirmação de cadastro, recuperação de senha e código de 2FA chegam ao Mailpit em <http://localhost:8025>.

As chaves abaixo são opcionais e vêm depois da instalação básica. Não as use em produção. Elas entram no serviço `app` do `docker-compose.yml`, não num `.env` da pasta. A máquina precisa de internet para carregar o script do Google.

Chaves públicas de teste do Google, aceitas em `localhost`:

```yaml
RECAPTCHA_SITE_KEY: "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_SECRET_KEY: "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
```

Para uma chave própria, crie um reCAPTCHA v3 em <https://www.google.com/recaptcha/admin/create>, inclua o domínio `localhost` e substitua as duas linhas. A nota mínima aceita é `0.5`.

Recrie só a aplicação para o processo ler o ambiente novo:

```powershell
docker compose up -d --force-recreate app
```

O Beatle Uploader e o Beatle Contador usam rotas próprias de login e não passam por esse captcha.

## Integração com a SEFAZ

O worker usa o certificado A1 custodiado no servidor e a autenticação mTLS da Receita. Ele não faz parte da subida padrão. O perfil só existe para quem for inspecionar o ciclo:

```powershell
docker compose --profile sefaz up
```

Sem certificado, a rotina ignora a empresa e não consulta a SEFAZ. A reprodução pública deste TCC para por aí. Não envie um certificado e-CNPJ real para este ambiente: usuário, senha e chave de cifra do Compose são públicos e estão no arquivo versionado.

O botão **Sincronizar** da tela de notas também pode disparar a mesma rotina dentro do contêiner `app`. Sem certificado, essa chamada igualmente não completa uma consulta à Receita.

## Problemas comuns

- **`docker` não é reconhecido.** Feche o terminal, abra o Docker Desktop, espere **Docker Desktop is running** e abra um PowerShell novo. Se o comando continuar ausente, inclua `C:\Program Files\Docker\Docker\resources\bin` na variável de sistema `Path`.
- **Docker Desktop parado ou WSL 2 ausente.** A instalação do Docker Desktop no Windows pede o WSL 2. Sem o serviço em execução, `docker compose up` não alcança o daemon.
- **Porta 8000 ou 5432 ocupada.** O Compose publica a aplicação em `8000` e o PostgreSQL em `5432`. Outro processo nessas portas impede o contêiner correspondente de subir. Este guia não altera o `docker-compose.yml` para trocar a porta.
- **Mailpit não abre.** Confira `mailpit` em `docker compose ps` e acesse <http://localhost:8025>. Sem ele, o código de 2FA não aparece. O script de fluxos segue e imprime que o Mailpit está indisponível.
- **Uploader para com `FileSystemEventHandler`.** O `watchdog` foi instalado em outro Python. Repita `python -m pip install -r beatle_uploader\requirements.txt` com o mesmo `python` que executa `beatle_uploader\main.py`.
- **reCAPTCHA vazio.** Em `ENV=development`, a ausência das chaves não bloqueia o formulário. Se as chaves forem preenchidas com um par inválido, o login do navegador passa a falhar na verificação do Google.
- **Login recusado.** Use um e-mail e uma senha da tabela de demonstração. O 2FA do gestor, se tiver ficado ligado por uma execução interrompida do script, pede o código no Mailpit.
- **Sem certificado A1.** A sincronização não consulta a SEFAZ. Isso é o comportamento esperado desta demonstração.
- **DANFC-e modelo 65.** A geração do PDF da NFC-e respondeu HTTP 500 numa execução anterior, com a mensagem de que o backend `rlPyCairo` não pôde ser importado. A NF-e modelo 55 não depende desse backend.

## Encerramento

Na raiz, este comando para os contêineres e conserva o volume `pgdata`, inclusive a carga sintética:

```powershell
docker compose down
```

O comando seguinte apaga o volume e, com ele, o banco da demonstração. Não faz parte da manutenção normal. Use-o só quando a perda desses dados for intencional:

```powershell
docker compose down -v
```
