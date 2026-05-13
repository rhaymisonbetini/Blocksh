# BUG 2 — IA se perde no fluxo interno e confunde tool calls/comandos

## Contexto

O projeto é o **Blocksh**, um terminal/IDE local em Python com uma tela de conversa com IA.

A IA funciona como um agente multi-turn e executa ações internas como:

```txt
ask_user(...)
read_file(...)
list_dir(...)
```

O problema atual é que a IA parece estar se perdendo no fluxo e confundindo comandos/tool calls.

---

# 1. Problema observado

Exemplo de prompt enviado pelo usuário:

```txt
the project progest stay in job/pdm. Can you access and tell me more about it?
```

Na tela, a IA executa algo como:

```txt
read_file(/home/skullbones/job/pdm)
list_dir(/home/skullbones/job/pdm)
```

Problemas visíveis:

- ela tenta usar `read_file` em um diretório;
- uma tool call falha;
- outra tool call funciona;
- a resposta final não fica clara;
- os comandos internos aparecem confusos;
- a IA não parece seguir um plano;
- a conversa fica com cara de fluxo quebrado;
- o usuário não recebe uma síntese boa sobre o projeto.

---

# 2. Objetivo

Corrigir a lógica do agente para que ele tenha um fluxo interno previsível, robusto e claro.

A IA precisa:

1. Entender se o caminho informado é arquivo ou diretório.
2. Não tentar `read_file` diretamente em diretório.
3. Usar `list_dir` primeiro quando o caminho for uma pasta.
4. Escolher arquivos relevantes depois de listar o diretório.
5. Ler arquivos úteis como README, CLAUDE.md, AGENTS.md, composer.json, package.json, pyproject.toml etc.
6. Consolidar as informações em uma resposta final clara.
7. Separar tool calls internas da mensagem final ao usuário.
8. Tratar erros de tool calls sem quebrar o fluxo.

---

# 3. Fluxo correto para analisar projeto/pasta

Quando o usuário pedir para analisar um projeto ou pasta, seguir esta ordem:

```txt
1. Resolver o caminho informado.
2. Verificar se o caminho existe.
3. Detectar se é arquivo ou diretório.
4. Se for diretório:
   4.1 listar diretório
   4.2 identificar arquivos relevantes
   4.3 ler arquivos relevantes
   4.4 opcionalmente listar subpastas importantes
5. Se for arquivo:
   5.1 ler arquivo diretamente
6. Consolidar informações encontradas.
7. Responder ao usuário em linguagem clara.
```

---

# 4. Regra crítica: não usar read_file em diretório

Se o path for:

```txt
/home/skullbones/job/pdm
```

e isso for uma pasta, a IA NÃO deve chamar:

```txt
read_file(/home/skullbones/job/pdm)
```

Deve chamar primeiro:

```txt
list_dir(/home/skullbones/job/pdm)
```

Depois, com base no resultado, pode chamar:

```txt
read_file(/home/skullbones/job/pdm/README.md)
read_file(/home/skullbones/job/pdm/CLAUDE.md)
read_file(/home/skullbones/job/pdm/AGENTS.md)
read_file(/home/skullbones/job/pdm/composer.json)
read_file(/home/skullbones/job/pdm/package.json)
read_file(/home/skullbones/job/pdm/pyproject.toml)
```

dependendo do que existir.

---

# 5. Criar etapa de classificação do path

Antes de qualquer leitura, adicionar uma etapa interna:

```txt
classify_path(path)
```

ou equivalente.

Retorno esperado:

```json
{
  "exists": true,
  "type": "directory",
  "path": "/home/skullbones/job/pdm"
}
```

ou:

```json
{
  "exists": true,
  "type": "file",
  "path": "/home/skullbones/job/pdm/README.md"
}
```

ou:

```json
{
  "exists": false,
  "type": null,
  "path": "/home/skullbones/job/pdm"
}
```

Se não existir tool específica, implementar essa validação dentro do roteador de tools antes de executar `read_file`.

---

# 6. Tratamento de erro de tool call

Se uma tool call falhar, o agente deve recuperar o fluxo.

Exemplo:

```txt
read_file(/home/skullbones/job/pdm) => erro: path is directory
```

A IA deve entender:

```txt
O path é um diretório. Vou listar a pasta.
```

E chamar:

```txt
list_dir(/home/skullbones/job/pdm)
```

Mas a resposta final ao usuário não deve ser apenas uma sequência de tool calls.  
Sempre precisa haver uma conclusão em linguagem natural.

---

# 7. Resposta final obrigatória

Ao final do fluxo, sempre gerar uma resposta final para o usuário.

A resposta final deve conter, quando possível:

- caminho analisado;
- tipo de projeto detectado;
- arquivos principais encontrados;
- estrutura resumida;
- tecnologias identificadas;
- próximos passos sugeridos;
- erros encontrados, se houver.

Exemplo esperado:

```txt
Analisei a pasta /home/skullbones/job/pdm.

Pela estrutura encontrada, parece ser um projeto Laravel/PHP. Os principais indícios são composer.json, artisan, app/, routes/ e config/.

Arquivos importantes encontrados:
- README.md
- composer.json
- .env.example
- app/
- routes/

Resumo:
...
```

---

# 8. Separar tool activity da conversa final

As tool calls devem ser tratadas como atividade interna do agente.

Na UI, elas podem aparecer como linhas técnicas, mas não devem substituir a resposta final.

Exemplo ruim:

```txt
read_file(...)
list_dir(...)
```

Exemplo correto:

```txt
Checking path: /home/skullbones/job/pdm
Listing directory: /home/skullbones/job/pdm
Reading file: README.md
Reading file: composer.json

Resposta final:
Encontrei o projeto...
```

---

# 9. Planejamento interno do agente

Antes de executar tools, o agente deve montar um plano simples.

Exemplo:

```txt
User wants to inspect project folder /home/skullbones/job/pdm.
Plan:
1. Check whether the path exists and whether it is file or directory.
2. If directory, list files.
3. Read README or metadata files.
4. Summarize project.
```

Esse plano não precisa aparecer completo para o usuário, mas deve guiar o executor.

---

# 10. Evitar loops e confusão de tools

Adicionar proteções:

```txt
max_tool_calls_per_turn: 8 ou 10
não repetir a mesma tool com os mesmos argumentos mais de 1 vez
não chamar read_file em path identificado como diretório
não chamar list_dir repetidamente no mesmo path sem motivo
se uma tool falhar 2 vezes, parar e explicar
```

---

# 11. Corrigir roteamento de intenção

Quando o usuário disser:

```txt
Can you access and tell me more about it?
```

e informar um path de projeto, a intenção correta deve ser:

```txt
inspect_project_directory
```

Não deve ser:

```txt
read_single_file
```

Criar ou ajustar intenções como:

```txt
inspect_project
inspect_directory
read_file
answer_question
ask_user
```

---

# 12. Arquivos importantes para detectar projeto

Ao inspecionar uma pasta, procurar por:

## Python

```txt
pyproject.toml
requirements.txt
setup.py
run.py
```

## Node

```txt
package.json
vite.config.*
next.config.*
```

## PHP / Laravel

```txt
composer.json
artisan
app/
routes/
config/
.env.example
```

## Geral

```txt
README.md
CLAUDE.md
AGENTS.md
Dockerfile
docker-compose.yml
Makefile
```

---

# 13. Onde aplicar no código

Procurar componentes/serviços como:

```txt
AIAssistant
AIAgent
AgentRunner
ToolRouter
ToolExecutor
ConversationManager
ChatController
AssistantService
AgentOrchestrator
read_file tool
list_dir tool
ask_user tool
```

Se ainda não houver separação, criar uma camada mais clara:

```txt
IntentRouter
ToolPlanner
ToolExecutor
ResponseSynthesizer
```

---

# 14. Checklist de validação

## Projeto/pasta

Prompt:

```txt
the project progest stay in job/pdm. Can you access and tell me more about it?
```

Esperado:

- [ ] IA resolve o caminho corretamente.
- [ ] IA identifica que é diretório.
- [ ] IA chama `list_dir` antes de `read_file`.
- [ ] IA lê arquivos relevantes.
- [ ] IA gera resposta final clara.

## Arquivo específico

Prompt:

```txt
read /home/skullbones/job/pdm/README.md and summarize it
```

Esperado:

- [ ] IA identifica que é arquivo.
- [ ] IA chama `read_file`.
- [ ] IA resume o conteúdo.

## Path inexistente

Prompt:

```txt
tell me about /home/skullbones/job/project-that-does-not-exist
```

Esperado:

- [ ] IA informa que o caminho não existe.
- [ ] IA não entra em loop.
- [ ] IA sugere verificar o caminho.

## Diretório sem README

Esperado:

- [ ] IA lista diretório.
- [ ] IA identifica arquivos alternativos.
- [ ] IA responde com base na estrutura.

---

# 15. Resultado esperado

Depois da correção:

- A IA não deve mais se perder no fluxo.
- A IA não deve tentar ler diretório como arquivo.
- Tool calls devem seguir uma ordem lógica.
- Erros de tool devem ser tratados e recuperados.
- A resposta final ao usuário deve ser clara.
- A UI deve mostrar atividade técnica de forma organizada.
- O usuário deve sentir que a IA realmente entendeu o projeto e explicou o que encontrou.
