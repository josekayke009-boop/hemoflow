# Arquitetura e requisitos — HemoFlow

## Objetivo

Oferecer uma base demonstrativa para cadastro e acompanhamento operacional de estoque de bolsas. O escopo acadêmico abrange cadastro, consulta, filtros, indicadores de inventário e histórico de mudanças de status. O sistema não recomenda doadores, não calcula compatibilidade para transfusão e não substitui a decisão de profissionais habilitados.

## Componentes

```text
Navegador
  ├── static/index.html + styles.css + app.js
  └── HTTP/JSON em localhost
          └── app.py (servidor e API padrão do Python)
                  └── SQLite (hemoflow.db)
```

O cliente renderiza a interface e consome a API JSON. O servidor valida os dados, aplica regras simples de inventário e persiste os registros em SQLite. Os arquivos da interface são servidos apenas a partir da pasta `static`.

## Requisitos funcionais

- **RF01:** cadastrar bolsa com tipo sanguíneo, volume, coleta, validade, localização e status inicial.
- **RF02:** gerar automaticamente um código interno único para a bolsa.
- **RF03:** listar bolsas ordenadas pela data de validade.
- **RF04:** filtrar por tipo sanguíneo e status; pesquisar por código ou localização.
- **RF05:** exibir totais gerais, disponíveis válidas, vencidas, vencimentos próximos e totais disponíveis por tipo.
- **RF06:** alterar o status segundo as transições documentadas, identificando responsável/observação.
- **RF07:** consultar até 200 movimentações recentes.

## Requisitos não funcionais

- **RNF01:** interface em português, adaptável a telas pequenas e sem dependências de instalação.
- **RNF02:** persistência relacional SQLite local com chaves estrangeiras e índices de consulta.
- **RNF03:** validação de entrada na interface e no servidor; o servidor é a autoridade das regras.
- **RNF04:** operações SQL parametrizadas e escape de conteúdo pelo uso de `textContent` no cliente.
- **RNF05:** escuta local em `127.0.0.1` por padrão; proteger e revisar antes de qualquer implantação em rede.

## Regras operacionais demonstrativas

- Tipos sanguíneos aceitos: A+, A−, B+, B−, AB+, AB−, O+, O−.
- Volume aceito: inteiro de 1 a 1000 ml.
- A validade deve ser igual ou posterior à coleta; não se cadastra uma nova bolsa já vencida.
- Bolsa vencida não conta como disponível válida e não pode ser marcada como transfundida pela API.
- Status inicial: disponível ou quarentena.
- As transições permitidas constam em `banco-de-dados.md`.

Essas regras são simplificações didáticas e devem ser substituídas/revisadas segundo protocolos aplicáveis, se o projeto evoluir.

## Limitações conhecidas

Sem autenticação, autorização, criptografia de dados, HTTPS, backup automatizado, gestão de concorrência clínica, integração com laboratório, controle de lote/hemocomponente, validação por autoridade sanitária ou certificação. Histórico recente limitado a 200 linhas; listagem limitada a 500 bolsas. O status de vencimento é calculado com a data local do servidor.

## Casos de uso

1. Operador cadastra uma unidade recebida e informa sua localização de armazenamento.
2. Operador localiza unidades por código/tipo/status.
3. Operador registra reserva, retorno à disponibilidade, quarentena, transfusão ou descarte conforme as transições permitidas.
4. Orientador avalia os indicadores e o registro de movimentações durante a demonstração.
