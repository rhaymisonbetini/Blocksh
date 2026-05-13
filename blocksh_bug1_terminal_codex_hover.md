# BUG 1 — Terminal não retorna output ao executar `codex` + output vibrando no hover

## Contexto

O projeto é o **Blocksh**, um terminal/IDE local em Python com uma interface de terminal e integração com agente de IA.

Existem dois problemas na área de terminal:

1. Ao executar o comando `codex`, o terminal não retorna output visível.
2. Ao passar o mouse sobre o output do terminal, o bloco fica “vibrando”, como se o hover alterasse alguns pixels do layout.

---

# 1. Problema A — comando `codex` não retorna nada

## Comportamento atual

Ao executar:

```bash
codex
```

o terminal parece iniciar algo, mas:

- não mostra output;
- não mostra erro;
- não mostra prompt novo;
- não mostra status de execução;
- não fica claro se o processo está rodando, travado ou se o output não está sendo capturado.

Esse problema provavelmente afeta outros comandos interativos também, como:

```bash
claude
python
node
ssh
top
htop
```

---

## Comportamento esperado

Ao executar `codex`, o terminal deve:

- iniciar o processo corretamente;
- mostrar output incremental;
- manter stdin/stdout conectados;
- renderizar stdout e stderr;
- manter a UI responsiva;
- indicar quando o comando está rodando;
- mostrar erro se o comando falhar;
- devolver o prompt quando o processo terminar.

---

# 2. Diagnóstico provável

O terminal pode estar usando execução simples via:

```python
subprocess.run(...)
subprocess.Popen(...).communicate()
stdout.readline()
```

Isso funciona para comandos simples, mas costuma falhar ou travar em comandos interativos.

Comandos como `codex` geralmente precisam de um **PTY real**.

---

# 3. Correção recomendada para `codex`

Verificar os componentes responsáveis por execução de comandos:

```txt
TerminalView
TerminalPane
TerminalRunner
CommandRunner
CommandExecutor
ProcessManager
PtyProcess
ShellSession
TerminalSession
```

Se o projeto estiver usando pipes simples, migrar a execução interativa para PTY.

Exemplo conceitual:

```python
import os
import pty
import subprocess

master_fd, slave_fd = pty.openpty()

process = subprocess.Popen(
    command,
    shell=True,
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    cwd=current_working_directory,
    env=env,
    preexec_fn=os.setsid,
)

os.close(slave_fd)

# Ler master_fd em loop não bloqueante e enviar para o terminal UI.
```

Também pode ser usado, se fizer sentido no projeto:

```txt
ptyprocess
pexpect
pyte
QProcess
prompt_toolkit
```

A escolha deve respeitar a arquitetura atual.

---

# 4. Requisitos técnicos

A execução de comandos no terminal deve suportar:

- stdout streaming;
- stderr streaming;
- stdin interativo;
- ANSI escape sequences;
- comandos longos;
- comandos interativos;
- leitura não bloqueante;
- cancelamento/interrupção;
- resize do terminal, se aplicável.

A UI não pode travar enquanto o comando está rodando.

---

# 5. Feedback visual obrigatório

Quando um comando interativo estiver rodando e ainda não tiver output, mostrar algum feedback:

```txt
● Running codex...
```

ou:

```txt
codex is running...
```

Se o comando falhar:

```txt
Command failed: codex
Exit code: X
stderr: ...
```

Se o comando não existir:

```txt
codex: command not found
```

O terminal não pode parecer morto.

---

# 6. Problema B — output vibra ao passar o mouse

## Comportamento atual

Ao passar o mouse sobre blocos de output do terminal, o bloco parece “vibrar”.

Isso indica que o hover está alterando propriedades que causam reflow/repaint com mudança de geometria.

Possíveis causas:

```txt
border sendo adicionado só no hover
padding mudando no hover
margin mudando no hover
font-size mudando no hover
font-weight mudando no hover
transform/scale no hover
outline-offset alterando layout
shadow ou background mal aplicado
```

---

# 7. Regra para hover do terminal

O hover de blocos do terminal **não pode alterar layout**.

Permitido:

```txt
background-color
color
opacity
box-shadow sem alterar layout
cursor
```

Proibido:

```txt
alterar padding
alterar margin
alterar border-width
alterar font-size
alterar font-weight se mudar métrica
alterar width
alterar height
usar transform scale
reposicionar elemento
```

---

# 8. Correção recomendada do hover

Se o bloco precisa de borda no hover, a borda deve existir sempre como transparente.

Correto:

```css
.terminal-output-block {
  box-sizing: border-box;
  border: 1px solid transparent;
}

.terminal-output-block:hover {
  border-color: var(--border-soft);
}
```

Errado:

```css
.terminal-output-block {
  border: none;
}

.terminal-output-block:hover {
  border: 1px solid var(--border-soft);
}
```

Alternativa segura:

```css
.terminal-output-block:hover {
  box-shadow: 0 0 0 1px var(--border-soft);
}
```

---

# 9. Estilo estável do output

Aplicar um estilo fixo e estável:

```css
.terminal-output-block {
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid transparent;
  line-height: 1.45;
  font-family: "Ubuntu Mono", monospace;
  font-size: 12px;
}

.terminal-output-block:hover {
  background: rgba(255, 255, 255, 0.025);
  border-color: var(--border-soft);
}
```

O hover pode mudar aparência, mas nunca tamanho/posição.

---

# 10. Checklist de validação

## Comando `codex`

- [ ] Executar `ls` e confirmar output normal.
- [ ] Executar `pwd` e confirmar output normal.
- [ ] Executar `codex` e confirmar que aparece output ou estado de execução.
- [ ] Executar `python` e confirmar modo interativo.
- [ ] Executar comando inexistente e confirmar erro claro.
- [ ] Confirmar que stdout e stderr aparecem.
- [ ] Confirmar que a UI não trava.
- [ ] Confirmar que o prompt volta ao fim do processo.

## Hover

- [ ] Passar mouse sobre output pequeno.
- [ ] Passar mouse sobre output grande.
- [ ] Passar mouse rapidamente sobre vários blocos.
- [ ] Confirmar que nenhum bloco vibra.
- [ ] Confirmar que não muda altura/largura.
- [ ] Confirmar que não há reflow.
- [ ] Confirmar que o terminal continua visualmente estável.

---

# 11. Resultado esperado

Depois do fix:

- `codex` deve funcionar corretamente dentro do terminal;
- comandos interativos devem ser suportados;
- o usuário deve receber feedback quando o processo estiver rodando;
- a UI não deve travar;
- blocos de output não devem vibrar no hover;
- o terminal deve parecer estável, profissional e confiável.
