# Toobar Full Stack

Sistema full stack gratuito e local para barzinho com cardapio digital, autenticacao de usuarios, pedidos e banco de dados SQLite.

## Gratuito e local

- Nao precisa de hospedagem paga para rodar na sua maquina.
- Nao usa CDN, Google Fonts, Unsplash, banco externo ou SaaS.
- O backend roda em Python local.
- O banco fica em `data/toobar.sqlite3`.
- A interface conversa com `http://127.0.0.1:8000`.
- As imagens do cardapio sao servidas pelo proprio backend.

## Arquitetura

- `index.html`: frontend responsivo em HTML, CSS e JavaScript, sem dependencias externas.
- `server.py`: servidor HTTP, arquivos estaticos e API REST.
- `toobar/database.py`: schema SQLite, migracoes e seed do cardapio.
- `toobar/security.py`: hash de senha com PBKDF2 e geracao de tokens.
- `toobar/service.py`: regras de negocio de usuarios, sessoes, menu e pedidos.
- `tests/test_service.py`: testes automatizados da camada de negocio.

## Recursos

- Cadastro e login de usuarios.
- Cookie de sessao `HttpOnly` com validade de 7 dias.
- Cardapio persistido no SQLite e carregado via `/api/menu`.
- Assets locais/offline servidos via `/api/assets/menu/*.svg`.
- Pedido autenticado via `/api/orders`.
- Historico de pedidos do usuario logado.
- Testes de cadastro, login, menu, autenticacao e pedidos.

## Rodar localmente

Use o Python do sistema ou o Python empacotado pelo Codex.

```powershell
python server.py
```

Se o comando global `python` nao responder, use:

```powershell
C:\Users\Lindomar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe server.py
```

Depois abra:

```text
http://127.0.0.1:8000
```

O banco sera criado automaticamente em:

```text
data/toobar.sqlite3
```

## Testes

```powershell
python -m unittest discover -s tests
```

Ou com o Python empacotado:

```powershell
C:\Users\Lindomar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
```

## API

- `GET /api/health`: status da aplicacao.
- `GET /api/menu?category=drinks`: lista itens do cardapio.
- `GET /api/me`: usuario logado.
- `POST /api/auth/register`: cria usuario.
- `POST /api/auth/login`: autentica usuario.
- `POST /api/auth/logout`: encerra sessao.
- `POST /api/orders`: cria pedido autenticado.
- `GET /api/orders`: lista pedidos do usuario.

## Proximos passos de producao

- Painel administrativo para alterar cardapio e status dos pedidos.
- Integracao com WhatsApp, impressora da cozinha ou sistema de caixa.
- Deploy com HTTPS para proteger cookies e trafego.
- Rate limit e logs estruturados.
- Separar frontend em build moderno se o projeto crescer.
