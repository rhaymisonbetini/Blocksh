# Blocksh — Lapidação visual: bordas rounded, ícones melhores, input/prompt, Run button e modal

## Contexto

O projeto é o **Blocksh**, um terminal/IDE local em Python.

Depois dos últimos ajustes, a interface ficou muito mais limpa e profissional:

- sidebar compacta;
- terminal com mais espaço;
- empty state mais simples;
- botão `Run README` removido;
- modais melhores;
- autocomplete menos poluído.

Agora o objetivo é uma **lapidação visual final** para deixar o app com cara de produto moderno e bem acabado.

Esta task NÃO é para redesenhar tudo do zero.  
É para refinar o que já ficou bom.

---

# Objetivos desta task

Aplicar melhorias visuais nos seguintes pontos:

1. Alinhar melhor o input inferior com o prompt do terminal.
2. Deixar o botão `Run` menos chamativo quando o terminal estiver vazio.
3. Melhorar os ícones da sidebar.
4. Usar ícones maiores, mais vivos e mais atrativos.
5. Dar mais respiro no modal de confirmação.
6. Melhorar o texto do modal de confirmação.
7. Aplicar bordas mais arredondadas em caixas, menus, inputs, outputs, autocomplete e modais.
8. Deixar a UI com um estilo mais moderno, menos “quadrado/pontudo”.
9. Manter a identidade dark/minimalista do Blocksh.

---

# 1. Bordas mais rounded em todo o sistema

## Problema atual

A interface está melhor, mas ainda existem muitas caixas com aparência muito reta/pontuda.

Isso aparece principalmente em:

- menu/sidebar;
- input inferior;
- output do terminal;
- autocomplete;
- cards de settings;
- botões;
- modais;
- campos de formulário;
- painel de data management.

A intenção é dar uma sensação mais moderna, parecida com apps premium atuais.

---

## Regra visual

A UI do Blocksh deve usar bordas arredondadas consistentes.

Criar ou ajustar tokens globais:

```txt
radius_xs: 6px
radius_sm: 8px
radius_md: 10px
radius_lg: 14px
radius_xl: 18px
radius_2xl: 22px
```

---

## Aplicação sugerida

### Sidebar items

```txt
border-radius: 10px ou 12px
```

### Botões normais

```txt
border-radius: 10px ou 12px
```

### Botão Run

```txt
border-radius: 12px ou 14px
```

### Inputs

```txt
border-radius: 12px ou 14px
```

### Autocomplete dropdown

```txt
border-radius: 14px
```

### Output blocks

```txt
border-radius: 12px ou 14px
```

### Cards de Settings

```txt
border-radius: 14px ou 16px
```

### Modal

```txt
border-radius: 18px ou 20px
```

---

## Regra importante

Não usar bordas completamente circulares em tudo.

Evitar:

```txt
border-radius: 999px
```

exceto em badges pequenos ou pills.

O estilo deve ser:

```txt
rounded moderno
macio
profissional
sem parecer infantil
```

---

# 2. Terminal mais plano, mas com caixas suavemente arredondadas

## Problema

A tela do terminal ainda pode parecer um pouco dividida e rígida.

Queremos manter o visual limpo, mas com caixas mais suaves.

---

## Objetivo

A superfície principal do terminal deve parecer única, mas os elementos internos podem ter bordas suaves.

Exemplo esperado:

```txt
┌──────────────────────────────────────────────┐
│ ~/demo $ ls                                  │
│ args                                         │
│ app                                          │
│ README.md                                    │
│                                              │
│ ~/demo $ ready when you are...               │
└──────────────────────────────────────────────┘
```

O input não deve parecer um formulário separado demais.

---

# 3. Alinhar melhor o input inferior com o prompt

## Problema atual

O input inferior ainda parece uma barra separada, com o texto começando meio solto.

O prompt deveria parecer parte natural do terminal.

---

## Comportamento esperado

A linha inferior deve parecer uma continuação do terminal:

```txt
~/job/pdm $
```

e depois o texto digitado.

Exemplo:

```txt
~/job/pdm $ ready when you are...
```

ou, se preferir placeholder:

```txt
~/job/pdm $ write something awesome...
```

---

## Regras

- O input deve começar alinhado com o output do terminal.
- Usar mesmo padding horizontal do output.
- Usar mesma fonte do terminal.
- Usar mesmo tamanho de fonte.
- O prompt/path deve ter cor diferente do texto digitado.
- Evitar input com cara de campo web grande demais.
- A barra inferior deve se integrar visualmente ao terminal.

---

## Estilo sugerido

```txt
command_bar_height: 58px a 64px
padding_horizontal: igual ao terminal output
font-family: Ubuntu Mono
font-size: 12px ou 13px
background: transparente ou bg_terminal levemente elevado
border-top: 1px solid border_soft
```

Prompt:

```txt
path: accent_blue
symbol $: accent_green
placeholder: text_faint
typed text: text_primary
```

---

# 4. Botão Run menos chamativo quando terminal está vazio

## Problema atual

O botão `Run` fica muito forte visualmente mesmo quando não há comando digitado.

Isso chama atenção demais e compete com o empty state.

---

## Comportamento esperado

O botão `Run` deve ter estados visuais.

### Quando input está vazio

```txt
background: bg_surface ou accent_green com baixa opacidade
text/icon: text_muted
opacity: 0.65
```

Ou:

```txt
disabled visual state
```

### Quando há comando digitado

```txt
background: accent_green
text/icon: dark ou white
opacity: 1
```

---

## Regras

- `Run` não deve dominar a tela quando não existe comando.
- `Run` deve ficar forte apenas quando existe ação real.
- Se o app permitir executar vazio, ainda assim o visual deve parecer inativo.
- Se o app bloquear execução vazia, o botão pode ficar disabled.

---

## Estilo sugerido

### Empty state

```txt
Run button:
background: rgba(34, 197, 94, 0.28)
color: rgba(229, 231, 235, 0.70)
border: 1px solid rgba(34, 197, 94, 0.22)
```

### Active command

```txt
Run button:
background: #22C55E
color: #04130A
border: none
```

---

# 5. Melhorar ícones da sidebar

## Problema atual

Os ícones da sidebar estão funcionais, mas ainda podem parecer pequenos, fracos ou pouco atrativos.

Como agora a sidebar é somente ícones, eles precisam carregar mais identidade visual.

---

## Objetivo

Os ícones devem ser:

- maiores;
- mais visíveis;
- mais consistentes;
- com estilo único;
- mais bonitos;
- mais “vivos” sem exagero.

---

## Recomendação

Usar uma biblioteca única de ícones outline, como:

```txt
Lucide Icons
Heroicons
Phosphor Icons
Feather Icons
Tabler Icons
```

Escolher apenas uma e usar em toda a aplicação.

---

## Tamanho recomendado

Atualmente os ícones parecem pequenos.

Usar:

```txt
icon_size: 18px a 20px
active_icon_size: 20px
```

Sidebar item:

```txt
item_size: 40px ou 42px
```

---

## Cores

### Ícone normal

```txt
color: #94A3B8
opacity: 0.85
```

### Hover

```txt
color: #E5E7EB
background: rgba(255, 255, 255, 0.04)
```

### Ativo

```txt
color: #60A5FA ou #93C5FD
background: rgba(59, 130, 246, 0.22)
border-left: 2px solid #3B82F6
```

---

## Ícones sugeridos por item

```txt
Terminal   => terminal-square ou square-terminal
History    => history ou clock-3
Favorites  => star
Projects   => folder-kanban ou panels-top-left
SSH        => server ou terminal
Workflows  => workflow ou play-circle
Settings   => settings
Themes     => palette
About      => circle-help ou info
```

---

## Regras

- Não misturar ícones unicode com SVG se possível.
- Não usar ícones muito finos.
- Não usar ícones sem alinhamento vertical.
- Todos devem ter o mesmo stroke width.
- Todos devem centralizar perfeitamente dentro do item.
- Hover deve parecer suave, sem pular layout.
- Tooltip deve aparecer ao passar o mouse.

---

# 6. Sidebar com mais presença visual, sem ocupar espaço

## Objetivo

A sidebar deve continuar compacta, mas parecer mais premium.

---

## Ajustes sugeridos

```txt
sidebar_width: 56px
item_size: 40px
icon_size: 19px
item_radius: 12px
gap: 8px
padding_top: 10px
padding_horizontal: 8px
```

Separadores:

```txt
divider_width: 32px
divider_color: border_soft
margin_vertical: 12px
```

---

## Tooltip

Como os textos foram removidos, tooltip é obrigatório.

Estilo:

```txt
background: #111827
border: 1px solid #243047
border-radius: 8px
font-size: 11px
padding: 6px 8px
box-shadow: 0 8px 24px rgba(0,0,0,0.35)
```

---

# 7. Dar mais respiro no modal

## Problema atual

O modal já melhorou, mas ainda pode ficar apertado.

O conteúdo precisa respirar mais.

---

## Ajuste esperado

Modal deve ter:

```txt
padding: 24px
gap entre título e descrição: 8px
gap entre descrição e botões: 20px
width: 420px a 460px
border-radius: 18px ou 20px
```

---

## Layout do modal

Estrutura sugerida:

```txt
┌────────────────────────────────────────────┐
│ Confirm action                             │
│                                            │
│ Delete all projects?                       │
│ This action cannot be undone.              │
│                                            │
│                      [Cancel] [Delete]     │
└────────────────────────────────────────────┘
```

---

## Ícone do modal

Adicionar ícone pequeno no topo ou ao lado do título.

Para ação destrutiva:

```txt
warning-triangle
trash
alert-circle
```

Estilo:

```txt
icon_size: 22px
icon_bg: rgba(239, 68, 68, 0.12)
icon_color: #F87171
icon_container: 36px x 36px
border-radius: 10px
```

---

# 8. Melhorar texto do modal de confirmação

## Problema

O texto atual é funcional, mas pode ser mais claro e profissional.

Exemplo atual:

```txt
Delete ALL projects? This cannot be undone.
```

Melhorar para textos mais específicos.

---

## Textos sugeridos

### Clear command history

Título:

```txt
Clear command history?
```

Descrição:

```txt
This will permanently remove all saved terminal commands from your local history. This action cannot be undone.
```

Botões:

```txt
Cancel
Clear history
```

---

### Clear favorites

Título:

```txt
Clear favorites?
```

Descrição:

```txt
This will permanently remove all saved favorite commands and shortcuts. This action cannot be undone.
```

Botões:

```txt
Cancel
Clear favorites
```

---

### Clear projects

Título:

```txt
Clear projects?
```

Descrição:

```txt
This will remove all saved project entries from Blocksh. Your project files will not be deleted from disk.
```

Botões:

```txt
Cancel
Clear projects
```

---

### Clear ALL data

Título:

```txt
Delete all local Blocksh data?
```

Descrição:

```txt
This will permanently remove command history, favorites, saved projects, and local app data. Your files on disk will not be deleted. This action cannot be undone.
```

Botões:

```txt
Cancel
Delete all data
```

---

# 9. Melhorar botões do modal

## Estilo

### Cancel

```txt
background: transparent ou bg_surface
border: 1px solid border
color: text_muted
hover: bg_hover
```

### Destructive

```txt
background: #EF4444
color: white
hover: #DC2626
```

Tamanho:

```txt
height: 36px
padding: 0 14px
border-radius: 10px
font-size: 12px
font-weight: 600
```

---

# 10. Autocomplete mais arredondado e bonito

## Ajuste visual

A dropdown de autocomplete deve acompanhar o novo estilo rounded.

```txt
border-radius: 14px
background: #111827
border: 1px solid #243047
box-shadow: 0 12px 36px rgba(0,0,0,0.35)
padding: 6px
```

Itens:

```txt
height: 30px
border-radius: 9px
padding: 0 10px
font-size: 12px
```

Item ativo:

```txt
background: rgba(59, 130, 246, 0.22)
color: text_primary
```

---

# 11. Cards e outputs com rounded consistente

## Terminal output

Se houver blocos/cards de output:

```txt
border-radius: 14px
padding: 12px 14px
```

Mas cuidado: não criar visual de vários cards desnecessários.

Se a intenção for terminal plano, usar output integrado com apenas uma superfície.

---

## Settings cards

```txt
border-radius: 16px
padding: 18px
```

---

## Data Management card

```txt
border-radius: 16px
```

Botões destrutivos:

```txt
border-radius: 10px ou 12px
```

---

# 12. Manter a UI elegante, não exagerada

Apesar de querermos mais rounded e ícones mais vivos, evitar exageros.

Não fazer:

```txt
ícones gigantes demais
cores neon excessivas
bordas redondas demais em tudo
sombras pesadas demais
gradientes coloridos demais
```

A estética deve ser:

```txt
dark
premium
terminal
moderna
técnica
limpa
```

---

# 13. Onde aplicar no código

Procurar e ajustar:

```txt
AppShell
NavigationRail
Sidebar
SidebarItem
IconButton
Button
RunButton
CommandComposer
CommandInput
TerminalSurface
TerminalOutput
AutocompleteDropdown
Modal
ConfirmDialog
SettingsView
DataManagement
ThemeCreator
Card
Input
Select
Tooltip
```

Se ainda não existirem, extrair componentes básicos:

```txt
NavigationIconButton
ConfirmDialog
RoundedInput
RoundedButton
AutocompleteMenu
Tooltip
```

---

# 14. Checklist de validação

## Rounded visual

- [ ] Sidebar items têm bordas arredondadas bonitas.
- [ ] Inputs têm border-radius moderno.
- [ ] Botões têm border-radius consistente.
- [ ] Modais têm border-radius maior e premium.
- [ ] Autocomplete tem bordas arredondadas.
- [ ] Cards de settings têm cantos mais suaves.
- [ ] Não há caixas pontudas demais.

## Ícones

- [ ] Ícones da sidebar estão maiores.
- [ ] Ícones estão centralizados.
- [ ] Ícones têm estilo único.
- [ ] Ícones têm cor mais viva no ativo.
- [ ] Hover dos ícones é suave.
- [ ] Tooltip aparece no hover.
- [ ] Não há mistura estranha de ícones.

## Input / terminal

- [ ] Input inferior está alinhado com o prompt.
- [ ] Input parece parte do terminal.
- [ ] Output e input usam mesma fonte.
- [ ] Botão Run fica discreto quando vazio.
- [ ] Botão Run fica forte quando há comando.
- [ ] Terminal não parece formulário web.

## Modal

- [ ] Modal tem mais padding.
- [ ] Texto está mais claro.
- [ ] Botões estão bem alinhados.
- [ ] Ação destrutiva está destacada.
- [ ] Modal parece sólido e moderno.
- [ ] O backdrop está correto.

---

# 15. Resultado esperado

Após esta lapidação, o Blocksh deve parecer:

- mais moderno;
- mais rounded;
- mais premium;
- menos quadrado;
- com ícones mais bonitos;
- com sidebar compacta e atrativa;
- com terminal mais integrado;
- com modal mais profissional;
- com botão Run mais inteligente;
- com UI mais coesa e polida.

O objetivo é transformar a interface de “funcional e limpa” para “produto bonito e pronto para uso diário”.
