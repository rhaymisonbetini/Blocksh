# Blocksh — FIX urgente: input e autocomplete ficaram fora do lugar após arredondar UI

## Contexto

O projeto é o **Blocksh**, um terminal/IDE local em Python.

Depois da última lapidação visual, as bordas arredondadas ficaram boas e a UI ganhou um aspecto mais moderno. Porém surgiu um bug visual grave:

- o **input principal do terminal** foi parar em uma posição errada;
- o **autocomplete** aparece solto no meio da tela;
- o autocomplete não está ancorado no input;
- existem duas áreas visuais competindo: uma caixa de autocomplete no centro e o command composer embaixo;
- a experiência do terminal ficou quebrada;
- o arredondamento ficou bom, mas o layout do input/autocomplete foi destruído.

Essa task é para corrigir especificamente esse problema.

Não remover o estilo rounded.  
Não voltar para a UI antiga.  
O objetivo é manter o visual moderno, mas posicionar corretamente input, prompt e autocomplete.

---

# 1. Problema observado

Na tela atual:

```txt
Terminal output aparece no topo
Autocomplete aparece como uma caixa azul grande no meio da tela
Command input aparece embaixo
O texto digitado parece aparecer em dois lugares diferentes
```

Visualmente parece que:

- o autocomplete foi renderizado como bloco normal dentro do layout;
- ele está ocupando espaço no fluxo vertical da tela;
- ele não está posicionado de forma absoluta/flutuante;
- o input ou sugestão foi separado do composer;
- o autocomplete parece uma barra gigante central;
- a linha de comando perdeu relação visual com o terminal.

Isso precisa ser corrigido.

---

# 2. Regra principal

O terminal deve ter **um único input principal**, fixado na parte inferior da área do terminal.

O autocomplete deve ser apenas uma camada flutuante ligada a esse input.

Nunca deve existir:

```txt
input no meio da tela
autocomplete ocupando espaço permanente
autocomplete empurrando layout
duas caixas de digitação
sugestão solta longe do input
dropdown gigante no centro do terminal
```

---

# 3. Estrutura correta da tela Terminal

A tela deve seguir esta hierarquia:

```txt
┌──────────────────────────────────────────────────────────────┐
│ Topbar / tabs                                                │
├──────────────────────────────────────────────────────────────┤
│ Terminal Surface                                             │
│                                                              │
│  output do terminal                                          │
│                                                              │
│                                                              │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Command Composer                                             │
│ ~/path $ [ input                                ] [Run]      │
└──────────────────────────────────────────────────────────────┘
```

Quando autocomplete estiver aberto:

```txt
┌──────────────────────────────────────────────────────────────┐
│ Terminal Surface                                             │
│                                                              │
│                                                              │
│                                                              │
│                                                              │
│             NÃO renderizar autocomplete aqui                 │
├──────────────────────────────────────────────────────────────┤
│       ┌──────────────────────────────────────────┐           │
│       │ sugestão 1                               │           │
│       │ sugestão 2                               │           │
│       │ sugestão 3                               │           │
│       └──────────────────────────────────────────┘           │
│ ~/path $ [ input                                ] [Run]      │
└──────────────────────────────────────────────────────────────┘
```

O autocomplete deve aparecer **logo acima do input**, alinhado com o campo de texto.

---

# 4. Autocomplete deve ser overlay/flutuante

## Problema atual

O autocomplete parece estar participando do layout normal, como se fosse um widget/card dentro do terminal.

Isso faz ele aparecer no meio da tela e empurrar ou bagunçar outros elementos.

## Correção

O autocomplete precisa ser renderizado como overlay/dropdown.

Ele deve:

- não ocupar espaço no fluxo vertical;
- não empurrar o terminal;
- não empurrar o command composer;
- ficar ancorado ao input;
- aparecer acima do input;
- ter largura parecida com o input;
- ter altura limitada;
- sumir quando não houver sugestão.

---

## Comportamento esperado

Quando o usuário digitar:

```bash
l
```

e houver sugestões, o dropdown deve aparecer assim:

```txt
                          terminal output
...

┌──────────────────────────────────────────────┐
│ ls                                           │
│ ls -la                                       │
│ ./logs/                                      │
└──────────────────────────────────────────────┘
~/project $ l
```

O dropdown deve ficar próximo ao input, não no meio da tela.

---

# 5. Posicionamento correto do autocomplete

## Regra de posicionamento

O autocomplete deve ser posicionado com base na geometria do input.

Conceito:

```txt
autocomplete.left = command_input.left
autocomplete.bottom = command_composer.top + pequeno_offset
autocomplete.width = command_input.width
autocomplete.max_height = 180px a 240px
```

Ou:

```txt
x = input_global_x
y = input_global_y - autocomplete_height - 6px
```

---

## Se estiver usando layout web/CSS

Usar algo assim:

```css
.command-composer {
  position: relative;
}

.autocomplete-dropdown {
  position: absolute;
  left: 0;
  right: 120px; /* espaço do botão Run, se necessário */
  bottom: calc(100% + 8px);
  z-index: 50;
  max-height: 220px;
  overflow-y: auto;
}
```

Ou, se o input estiver dentro de um wrapper:

```css
.command-input-wrapper {
  position: relative;
}

.autocomplete-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  z-index: 100;
}
```

---

## Se estiver usando PyQt/PySide/Tkinter/CustomTkinter

Não inserir o autocomplete como mais uma linha no layout vertical principal.

Usar uma destas estratégias:

```txt
- popup widget
- floating frame
- absolute positioning dentro do container do terminal
- overlay layer acima do composer
- QCompleter customizado, se PyQt/PySide
- Toplevel/Frame flutuante controlado, se Tkinter
```

A posição deve ser recalculada quando:

```txt
- input muda
- janela redimensiona
- sidebar muda
- terminal ganha/perde foco
- autocomplete abre/fecha
```

---

# 6. O input principal deve existir apenas no rodapé

## Problema atual

Parece existir um input/sugestão renderizado no meio da tela e outro embaixo.

## Correção

Garantir que só existe **um componente de input real**:

```txt
CommandComposer / CommandInput
```

O autocomplete não deve ser um segundo input.

Ele deve renderizar somente opções selecionáveis.

---

## Estrutura recomendada

```txt
CommandComposer
  ├── PromptPrefix
  │   ├── CurrentPath
  │   └── DollarSymbol
  ├── CommandInput
  ├── AutocompleteDropdown overlay
  └── RunButton
```

O autocomplete deve ser filho visual do composer ou de um overlay, mas nunca um bloco independente no terminal output.

---

# 7. Corrigir a caixa azul gigante do autocomplete

## Problema

A caixa azul grande no centro da tela está errada.

Ela parece:

- larga demais;
- alta demais;
- posicionada longe do input;
- com cor de active item aplicada no container inteiro;
- confundida com input.

## Correção visual

O container do autocomplete deve ter:

```txt
background: #111827
border: 1px solid #243047
border-radius: 14px
box-shadow: 0 12px 36px rgba(0,0,0,0.35)
padding: 6px
max-height: 220px
```

Cada item deve ter:

```txt
height: 30px
border-radius: 9px
padding: 0 10px
font-size: 12px
background: transparent
```

Somente o item ativo deve ter fundo azul:

```txt
active item background: rgba(59, 130, 246, 0.22)
```

O container inteiro NÃO deve ficar azul.

---

# 8. Layout do Command Composer

## Objetivo

O input inferior deve parecer parte natural do terminal, mas sem quebrar o layout.

## Estrutura visual correta

```txt
┌──────────────────────────────────────────────────────────────┐
│ ~/pessoal/projeto $ comando digitado                         │ [Run]
└──────────────────────────────────────────────────────────────┘
```

ou:

```txt
~/pessoal/projeto $ comando digitado                  [Run]
```

---

## Estilo recomendado

```txt
height: 56px a 64px
padding: 10px 14px
border-radius: 14px
background: #111827 ou transparente sobre terminal surface
border: 1px solid #243047
display: horizontal
align-items: center
gap: 8px
```

Prompt prefix:

```txt
path color: #60A5FA
$ color: #22C55E
font-size: 12px ou 13px
```

Input:

```txt
flex: 1
min-width: 0
background: transparent
border: none
outline: none
font-family: Ubuntu Mono
font-size: 12px ou 13px
color: #E5E7EB
```

Placeholder:

```txt
color: #64748B
```

Run button:

```txt
width: 96px ou 104px
height: 40px
border-radius: 12px
```

---

# 9. O autocomplete não deve cobrir o output de forma agressiva

O dropdown pode ficar sobreposto ao terminal, mas deve ser discreto e próximo ao composer.

Regras:

- máximo de 6 a 8 itens visíveis;
- scroll interno se tiver mais;
- largura não deve passar da largura do input;
- não deve cobrir metade da tela;
- não deve aparecer no centro;
- não deve aparecer se não houver sugestões úteis.

---

# 10. Autocomplete deve ser contextual e limpo

Manter a regra anterior:

O autocomplete deve sugerir apenas:

```txt
history
filesystem paths
directories/files
```

Não sugerir todos os comandos Linux por padrão.

Confirmar que a correção visual não reintroduziu:

```txt
lsattr
lsblk
lscpu
lshw
...
```

ao digitar `ls`.

---

# 11. Corrigir relação entre autocomplete e texto digitado

## Problema provável

O texto digitado parece aparecer numa caixa separada no centro.

Isso pode acontecer se o componente de autocomplete estiver renderizando a string atual como item ou como input falso.

## Regra

O texto digitado deve aparecer apenas no input real.

O autocomplete deve mostrar apenas sugestões.

Se o usuário digitou:

```bash
ls
```

o input real mostra:

```txt
ls
```

O dropdown mostra sugestões como:

```txt
ls
ls -la
./logs/
```

Mas não deve existir uma caixa gigante central contendo só `ls`.

---

# 12. Estados de abertura/fechamento

O autocomplete deve abrir apenas quando:

```txt
input está focado
existem sugestões
usuário digitou algo relevante
```

Deve fechar quando:

```txt
input perde foco
usuário pressiona ESC
usuário executa comando
usuário seleciona sugestão
não há sugestões
```

Ao executar comando:

```txt
autocomplete.close()
run_command()
```

---

# 13. Z-index / camada

Garantir que o autocomplete aparece acima do terminal, mas abaixo de modal.

Prioridade visual:

```txt
modal/dialog: z-index maior
autocomplete: z-index médio
terminal content: z-index baixo
```

Exemplo:

```txt
terminal output: z 1
composer: z 10
autocomplete: z 50
modal: z 100
```

---

# 14. Responsividade

O layout deve funcionar em diferentes tamanhos de janela.

Quando a janela for menor:

- input continua no rodapé;
- Run continua alinhado;
- autocomplete aparece acima do input;
- autocomplete reduz largura se necessário;
- nada vai para o meio da tela.

---

# 15. Onde investigar no código

Procurar componentes/arquivos como:

```txt
CommandComposer
CommandInput
AutocompleteDropdown
AutocompleteMenu
AutocompleteProvider
TerminalView
TerminalPane
TerminalSurface
MainLayout
AppShell
RunButton
```

Procurar por trechos que adicionam autocomplete no layout principal:

```txt
layout.addWidget(autocomplete)
terminal_layout.addWidget(autocomplete)
main_column.addWidget(autocomplete)
pack autocomplete before composer
grid autocomplete as row
```

Se encontrar isso, provavelmente é a causa.

O autocomplete deve ser overlay/popup, não row normal do layout.

---

# 16. Checklist obrigatório

## Input

- [ ] Existe apenas um input principal.
- [ ] Input fica no rodapé do terminal.
- [ ] Input está alinhado com o output.
- [ ] Input não aparece no centro da tela.
- [ ] Texto digitado não duplica em outro lugar.
- [ ] Prompt/path está integrado ao input.

## Autocomplete

- [ ] Autocomplete aparece acima do input.
- [ ] Autocomplete está ancorado ao input.
- [ ] Autocomplete não ocupa espaço no layout vertical.
- [ ] Autocomplete não aparece no centro da tela.
- [ ] Container do autocomplete não fica todo azul.
- [ ] Apenas item ativo fica azul.
- [ ] Autocomplete tem altura máxima.
- [ ] Autocomplete fecha ao executar comando.
- [ ] Autocomplete fecha com ESC.
- [ ] Autocomplete não lista comandos Linux por padrão.

## Layout

- [ ] Terminal output não é empurrado pelo autocomplete.
- [ ] Command composer não é empurrado pelo autocomplete.
- [ ] Run button continua alinhado.
- [ ] Rounded style foi preservado.
- [ ] A UI continua moderna.
- [ ] Não há duas caixas de comando competindo.

---

# 17. Resultado esperado

Depois do fix:

- o terminal continua com o visual rounded moderno;
- o input fica corretamente no rodapé;
- o autocomplete aparece somente como dropdown flutuante acima do input;
- nenhuma sugestão aparece solta no meio da tela;
- não existe caixa azul gigante central;
- o terminal volta a parecer uma ferramenta profissional;
- a UI fica arredondada, mas estruturalmente correta.

O arredondamento foi bom. O problema é só o layout/ancoragem do input e autocomplete. Corrija sem desfazer o visual moderno.
