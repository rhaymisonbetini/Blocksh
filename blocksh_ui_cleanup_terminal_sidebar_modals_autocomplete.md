# Blocksh — Ajustes visuais e UX do terminal, sidebar, modais e autocomplete

## Contexto

O projeto é o **Blocksh**, um terminal/IDE local em Python.

O objetivo desta task é fazer um ajuste visual e de experiência na interface atual. A aplicação já está funcional, mas alguns pontos estão deixando a UI poluída, bugada ou menos profissional do que deveria.

Esta task NÃO é para criar novas features grandes.  
É para corrigir e simplificar a experiência atual.

---

# Objetivos principais

Corrigir estes pontos:

1. Sidebar lateral ocupa espaço demais.
2. Não precisamos mais de menu lateral abrindo/fechando com texto.
3. Sidebar deve ser compacta e baseada apenas em ícones.
4. Remover o botão **Run README** da tela vazia do terminal.
5. Corrigir os modais da seção **Data Management**, que estão com aparência transparente/bugada.
6. Corrigir autocomplete de comandos: não listar todos os comandos Linux.
7. Autocomplete deve sugerir apenas histórico e caminhos/diretórios/arquivos relevantes.
8. Simplificar visualmente a linha de input/comando do terminal.
9. Deixar a experiência do terminal mais plana, integrada e menos dividida em blocos artificiais.

---

# 1. Sidebar compacta apenas com ícones

## Problema atual

A sidebar lateral está ocupando espaço demais.

Hoje ela tem:

- ícone;
- texto;
- botão de abrir/fechar;
- muita largura;
- áreas vazias;
- comportamento de colapsar/expandir que já não agrega tanto.

Isso rouba espaço útil do terminal.

## Decisão de produto

Remover a necessidade de sidebar expandida.

A sidebar deve ser **sempre compacta**, apenas com ícones.

Não precisamos mais dos textos ao lado dos ícones.

---

## Comportamento esperado

A sidebar deve ter uma largura fixa compacta:

```txt
width: 48px a 56px
```

Ela deve mostrar apenas ícones:

```txt
Terminal
History
Favorites
Projects
SSH
Workflows
---
Settings
Themes
About
```

Mas visualmente apenas os ícones devem aparecer.

O texto pode aparecer somente em tooltip no hover.

Exemplo:

```txt
┌────┐
│ >_ │  Terminal
│ ≡  │  History
│ ◇  │  Favorites
│ ▦  │  Projects
│ ↝  │  SSH
│ ▶  │  Workflows
│    │
│ ⚙  │  Settings
│ ◐  │  Themes
│ ○  │  About
└────┘
```

---

## Remover comportamento de abrir/fechar

Como a sidebar será sempre compacta, remover ou desativar o antigo comportamento de:

```txt
expand sidebar
collapse sidebar
```

Também remover o botão de colapsar/expandir menu lateral.

Esse botão hoje só adiciona complexidade visual.

## Regras

- Não deve existir sidebar larga por padrão.
- Não deve existir texto visível dentro da sidebar.
- Não deve existir botão de abre/fecha sidebar.
- Ao passar o mouse no ícone, mostrar tooltip com o nome.
- Item ativo deve continuar claro, com highlight discreto.
- A sidebar não deve roubar espaço do terminal.

---

## Estilo sugerido

```txt
sidebar_width: 52px
sidebar_bg: #0B1020
item_size: 36px
icon_size: 16px
item_radius: 8px
gap: 8px
active_bg: rgba(59, 130, 246, 0.22)
active_border_left: 2px solid #3B82F6
```

---

# 2. Remover botão "Run README"

## Problema atual

Na tela vazia do terminal, aparece o botão:

```txt
Run README
```

Esse botão não faz muito sentido no contexto de terminal.

O README normalmente é um arquivo de documentação, não algo para “rodar”.

## Correção

Remover o botão **Run README** do empty state.

Manter apenas ações úteis.

Sugestão:

```txt
Open Project
List Files
Create venv
```

Ou, se quiser deixar ainda mais simples:

```txt
Open Project
List Files
```

## Resultado esperado

A tela vazia deve ficar mais objetiva.

Exemplo:

```txt
No command running

Start by typing a command below or choose a quick action.

[Open Project] [List Files]
```

---

# 3. Corrigir modais da seção Data Management

## Problema atual

Os modais acionados na seção **Data Management**, por exemplo:

```txt
Clear command history
Clear favorites
Clear projects
Clear ALL data
```

estão com aparência muito ruim.

O modal parece transparente ou com aspecto de PNG/overlay bugado.

Visualmente:

- o fundo do modal parece mal renderizado;
- o contraste está ruim;
- há sensação de transparência indesejada;
- os botões parecem soltos;
- o modal não parece parte da UI;
- parece um bug visual.

---

## Correção esperada

Criar um modal sólido, limpo e consistente com o design system do Blocksh.

## Modal deve ter

```txt
overlay/backdrop escuro
card central opaco
título claro
descrição legível
ícone opcional
botões alinhados
ação destrutiva destacada
```

---

## Estilo recomendado

### Backdrop

```txt
background: rgba(0, 0, 0, 0.55)
blur opcional: 2px a 4px
```

### Modal card

```txt
background: #111827
border: 1px solid #243047
border-radius: 12px
box-shadow: 0 18px 50px rgba(0,0,0,0.45)
padding: 20px
width: 420px máximo
opacity: 1
```

### Título

```txt
font-size: 15px ou 16px
font-weight: 700
color: text_primary
```

### Descrição

```txt
font-size: 12px
color: text_muted
line-height: 1.45
```

### Botões

```txt
Cancel: secondary button
Confirm/Delete: danger button
```

---

## Exemplo de texto

Para Clear ALL data:

```txt
Delete all history, favorites, and projects?

This action cannot be undone.
```

Botões:

```txt
[Cancel] [Delete all data]
```

---

## Regras

- Modal não pode parecer transparente.
- Modal não pode usar imagem/png como fundo.
- Modal não pode deixar texto se misturar com tela de trás.
- Modal deve bloquear interação com o fundo.
- `ESC` deve fechar o modal.
- Clicar fora pode fechar, exceto em ação muito destrutiva se quiser bloquear.
- A ação destrutiva precisa ter confirmação clara.

---

# 4. Corrigir autocomplete de comandos

## Problema atual

Sempre que o usuário começa a digitar um comando, o autocomplete carrega uma lista enorme de comandos Linux possíveis.

Isso está deixando a experiência ruim.

Exemplo: ao digitar algo como `ls`, aparecem várias sugestões do sistema:

```txt
ls
lsattr
lsb_release
lsblk
lscpu
lshw
...
```

Isso vira uma zona visual e não ajuda.

## Decisão de produto

O autocomplete do Blocksh deve ser mais simples e contextual.

Não deve listar todos os comandos Linux disponíveis no sistema.

---

## Comportamento esperado

O autocomplete deve sugerir apenas:

1. Comandos do histórico.
2. Diretórios e arquivos do caminho atual.
3. Caminhos relativos ou absolutos quando o usuário estiver digitando path.
4. Talvez favoritos/workflows no futuro, mas não agora.

---

## Regras de autocomplete

### Histórico

Se o usuário digitar:

```bash
git
```

sugerir comandos já usados que começam com `git`, por exemplo:

```txt
git status
git pull
git checkout main
```

### Diretórios/arquivos

Se o usuário digitar:

```bash
cd do
```

sugerir diretórios locais como:

```txt
documentacao/
documentos-hierarquicos/
```

### Path relativo

Se o usuário digitar:

```bash
cat README
```

sugerir:

```txt
README.md
```

### Path absoluto

Se o usuário digitar:

```bash
cd /home/skullbones/
```

sugerir diretórios dentro desse path.

---

## Não fazer

Não sugerir automaticamente todos os binários do Linux:

```txt
lsattr
lsblk
lscpu
lshw
systemctl
journalctl
...
```

Isso pode ser implementado futuramente como feature opcional, mas deve estar desligado por padrão.

---

## Configuração recomendada

Criar uma opção interna ou setting:

```txt
autocomplete_system_commands: false
```

Default:

```txt
false
```

Fontes permitidas por padrão:

```txt
autocomplete_sources:
  - history
  - filesystem
```

Fontes desativadas:

```txt
  - system_commands
```

---

## UX da lista de autocomplete

A lista de sugestões deve ser compacta e não dominar a tela.

```txt
max_visible_items: 6 a 8
height por item: 28px
font-size: 11px ou 12px
```

Se houver muitas sugestões, usar scroll interno.

A lista deve aparecer próxima ao input, mas sem cobrir de forma agressiva o terminal inteiro.

---

# 5. Simplificar a linha de comando/input do terminal

## Problema atual

A região onde o usuário digita o comando e onde os comandos aparecem está visualmente feia e dividida demais.

Hoje existe muita separação visual entre:

- área de output;
- linha de input;
- barra inferior;
- botões;
- divisórias;
- blocos/cards.

Isso faz o terminal parecer menos natural.

## Objetivo

Criar uma experiência de terminal mais plana e integrada.

A tela deve parecer mais como um terminal real moderno, e menos como vários blocos separados.

---

## Comportamento visual esperado

O terminal deve ter uma superfície única.

Algo mais próximo de:

```txt
┌──────────────────────────────────────────────┐
│ ~/job/pdm $ ls                               │
│ args                                         │
│ argus-logger                                 │
│ delphi                                       │
│                                              │
│ ~/job/pdm $                                  │
└──────────────────────────────────────────────┘
```

Em vez de:

```txt
┌──────── output card ────────┐
│ output                      │
└─────────────────────────────┘
──────── divisor ─────────────
┌──────── input card ─────────┐
│ input                       │
└─────────────────────────────┘
```

---

## Correção visual

Reduzir divisões e bordas pesadas.

### Terminal container

```txt
background: #080C16 ou bg_terminal
border: none ou border muito sutil
border-radius: 0 ou 8px discreto
padding: 16px
```

### Input/prompt

O input deve parecer continuação natural do terminal.

```txt
~/job/pdm $
```

E o usuário digita ao lado.

---

## Botão Run

O botão **Run** pode continuar existindo, mas deve ser menos intrusivo.

Hoje ele fica muito destacado e separado.

Opções:

### Opção A — manter botão à direita, mas integrado

```txt
prompt/input ocupa quase tudo
Run button à direita
sem divisor pesado
```

### Opção B — esconder botão quando terminal estiver focado

Usuário usa Enter para executar.

Botão Run aparece só em hover ou fica discreto.

---

## Regras

- Remover divisórias exageradas.
- Reduzir sensação de card dentro de card.
- Input deve parecer parte do terminal.
- Output e input devem ter a mesma fonte e escala.
- Usar Ubuntu Mono 12px/13px.
- Não criar padding exagerado no rodapé.
- Não deixar a linha de comando parecer um formulário web.

---

# 6. Empty state do terminal

Com a sidebar compacta, o empty state pode ficar mais centralizado e limpo.

## Remover

```txt
Run README
```

## Manter

```txt
Open Project
List Files
```

## Opcional

```txt
Create venv
```

## Ajuste visual

O empty state deve ser discreto, não deve parecer tela principal demais.

```txt
Ícone: 42px a 48px
Título: 14px ou 15px
Descrição: 11px
Botões: 32px altura
```

---

# 7. Onde aplicar no código

Procurar e ajustar componentes como:

```txt
AppShell
MainLayout
Sidebar
SidebarItem
NavigationRail
TerminalView
TerminalPane
TerminalOutput
CommandComposer
CommandInput
AutocompleteDropdown
AutocompleteProvider
HistoryAutocompleteProvider
FilesystemAutocompleteProvider
SettingsView
DataManagement
ConfirmDialog
Modal
Dialog
EmptyTerminalState
```

Se ainda não existirem componentes separados, extrair pelo menos:

```txt
NavigationRail
ConfirmDialog
AutocompleteDropdown
CommandLineInput
TerminalSurface
```

---

# 8. Prioridade de implementação

## Prioridade alta

1. Sidebar fixa compacta só com ícones.
2. Remover botão Run README.
3. Corrigir autocomplete para não listar comandos Linux.
4. Corrigir modal transparente/bugado.

## Prioridade média

5. Simplificar visual da linha de comando.
6. Reduzir divisões visuais do terminal.
7. Melhorar empty state.

---

# 9. Checklist de validação

## Sidebar

- [ ] Sidebar tem apenas ícones.
- [ ] Sidebar não mostra textos.
- [ ] Sidebar não abre/fecha mais.
- [ ] Não existe botão de collapse/expand.
- [ ] Tooltips aparecem no hover.
- [ ] Item ativo está claro.
- [ ] Terminal ganhou mais espaço horizontal.

## Empty state

- [ ] Botão Run README foi removido.
- [ ] Empty state continua bonito e simples.
- [ ] Botões restantes fazem sentido.

## Modais

- [ ] Modal de Clear command history está opaco e bonito.
- [ ] Modal de Clear favorites está opaco e bonito.
- [ ] Modal de Clear projects está opaco e bonito.
- [ ] Modal de Clear ALL data está opaco e bonito.
- [ ] Não há aparência de PNG/transparência bugada.
- [ ] Backdrop escurece corretamente a tela.
- [ ] Botões estão alinhados.

## Autocomplete

- [ ] Ao digitar `ls`, não aparecem `lsattr`, `lsblk`, `lscpu` etc.
- [ ] Sugestões vêm do histórico.
- [ ] Sugestões vêm de diretórios/arquivos quando fizer sentido.
- [ ] Autocomplete não domina a tela.
- [ ] Lista tem altura limitada.
- [ ] É possível navegar com teclado.
- [ ] Enter/Tab seleciona corretamente, se já suportado.

## Terminal visual

- [ ] Input parece parte do terminal.
- [ ] Menos divisórias visuais.
- [ ] Output e input usam a mesma fonte.
- [ ] Botão Run não parece descolado.
- [ ] Terminal parece mais plano e integrado.
- [ ] Não há sensação de formulário web dentro do terminal.

---

# 10. Resultado esperado

Depois destes ajustes, o Blocksh deve parecer:

- mais limpo;
- mais profissional;
- mais focado no terminal;
- com mais espaço útil;
- com sidebar menos intrusiva;
- com modais sólidos e bonitos;
- com autocomplete inteligente e não poluído;
- com input de terminal mais natural;
- com menos divisões visuais desnecessárias.

A experiência deve ficar mais próxima de uma ferramenta de terminal/IDE moderna e menos de um painel com muitos blocos separados.
