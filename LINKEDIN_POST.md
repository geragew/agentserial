# LinkedIn launch post

## Main version

E se todos os agentes de IA concluírem suas tarefas com sucesso, mas o sistema
como um todo ainda falhar?

Esse foi o problema que me levou a criar o **AgentSerial**, um projeto open
source para analisar os efeitos de agentes executados em paralelo.

Dois agentes podem tomar decisões localmente corretas e, juntos, estourar um
orçamento, duplicar uma reserva ou deixar o sistema em um estado inválido. Os
logs tradicionais mostram que cada tarefa terminou. O AgentSerial verifica se o
resultado global continua correto em todas as ordens de execução possíveis.

O projeto:

- importa históricos em JSONL e traces OpenTelemetry;
- valida regras globais declaradas em contrato;
- identifica falhas que dependem da ordem de execução;
- reduz o problema ao menor contraexemplo compreensível;
- gera um relatório HTML com as evidências;
- funciona localmente, sem API key e sem depender de outro modelo de IA.

Estou publicando a primeira versão como open source para receber feedback de
quem trabalha com agentes, observabilidade, sistemas distribuídos e qualidade de
software.

Repositório: https://github.com/geragew/agentserial

Qual tipo de falha entre agentes você gostaria de conseguir detectar antes de
chegar à produção?

#OpenSource #ArtificialIntelligence #AIAgents #Python #OpenTelemetry
#DistributedSystems #SoftwareEngineering #Observability

## Short version

Todos os agentes terminaram com sucesso. Mesmo assim, o sistema falhou.

Criei o **AgentSerial** para encontrar esse tipo de problema: ele reexecuta
históricos de efeitos paralelos, verifica contratos globais e mostra o menor
contraexemplo que explica a falha.

Open source, local, determinístico e sem API key.

Repositório: https://github.com/geragew/agentserial

#OpenSource #AIAgents #Python #DistributedSystems #Observability

## Suggested carousel/video captions

1. Todos os agentes tiveram sucesso. O sistema nao.
2. A ordem das ações pode mudar o resultado global.
3. AgentSerial testa as ordens viáveis contra um contrato.
4. A falha vira um contraexemplo pequeno e explicável.
5. Open source, local e sem API key.

Use `media/agentserial-demo.webm` as the product demonstration and
`media/social-preview.png` as the cover image.
