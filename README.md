# Cloud Native Zero Lab

API FastAPI compatível com a-Shell no iPhone e PostgreSQL Neon.

## Rotas
- `GET /` — identificação
- `GET /health` — liveness local
- `GET /dbstatus` — consulta real ao Neon
- `GET /messages` — lê registros da tabela `teste_iphone`
- `POST /messages` — grava mensagem na tabela `teste_iphone`

## Instalação no a-Shell

Instalar dependências:

`python3 -m pip install -r requirements-iphone.txt`

Definir a variável de ambiente `NEON_DB_PASSWORD` **sem colocar a senha no código ou em comandos enviados ao chat**. O método de entrada segura depende do suporte do a-Shell.

Iniciar:

`python3 -m uvicorn main:app --host 127.0.0.1 --port 8000`

Acesse pelo navegador no mesmo iPhone, enquanto o processo estiver ativo.

## Hospedagem e testes

O arquivo render.yaml prepara um serviço web no plano Free em Oregon. Após vincular o repositório ao Render e configurar NEON_DB_PASSWORD como segredo, o Render acompanha a branch main e publica depois que os testes passam. O serviço usa o endpoint pooled do projeto Neon existente. Se o provedor exigir cartão, interrompa a ativação.

O GitHub Actions executa os testes a cada push ou pull request, usando um PostgreSQL 17 temporário e independente do Neon. O teste de integração cria a tabela no banco de teste, grava uma mensagem pela API e confirma sua leitura em outra requisição.

Para executar os testes locais, instale requirements-test.txt e rode python -m unittest discover -s tests -v. Para incluir a integração, use um PostgreSQL descartável em 127.0.0.1, banco lab_ci, e as variáveis do workflow.

As rotas de mensagens do protótipo são abertas. Use apenas dados de demonstração caso publique o serviço.
