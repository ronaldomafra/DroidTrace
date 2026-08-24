# Logcat Manager

Aplicativo Python de terminal para acompanhar `adb logcat` em tempo real, com cores por prioridade, filtros locais, busca, regex, exportação e um prompt interativo sempre disponível na parte inferior da tela.

## Requisitos

- Windows 10/11
- Python 3.11 ou superior
- Android SDK Platform Tools / ADB
- Um dispositivo Android com Depuração USB autorizada, ou um emulador em execução

O ADB encontrado neste computador está em:

```text
C:/Android/android-studio-sdk/platform-tools/adb.exe
```

## Instalação

No Git Bash, abra o diretório do projeto:

```bash
cd C:/temp/prj_temp/logcat_manager
```

Crie o ambiente virtual e instale as dependências:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org textual pytest pytest-asyncio
.venv/Scripts/python -m pip install --no-build-isolation -e .
```

> Os parâmetros `--trusted-host` são necessários neste ambiente por causa de um certificado SSL corporativo/local. Em uma instalação normal de Python, pode-se usar `pip install -e ".[dev]"`.

## Verificar o ADB e o dispositivo

Antes de iniciar, confirme que o ADB reconhece o dispositivo:

```bash
"C:/Android/android-studio-sdk/platform-tools/adb.exe" devices
```

Saída esperada:

```text
List of devices attached
RQ8M708HWEZ    device
```

Se o estado for `unauthorized`, desbloqueie o celular e aceite a autorização de depuração USB. Se houver mais de um dispositivo, use o serial correspondente em `--serial`.

## Executar

### Forma recomendada: caminho e dispositivo explícitos

```bash
.venv/Scripts/logcat-manager \
  --adb-path "C:/Android/android-studio-sdk/platform-tools/adb.exe" \
  --serial RQ8M708HWEZ
```

### Usar descoberta automática

```bash
.venv/Scripts/logcat-manager
```

O executável ADB é resolvido na seguinte ordem:

1. `--adb-path <caminho>`
2. Variável de ambiente `ADB_PATH`
3. Caminho salvo na configuração
4. `adb` disponível no `PATH`
5. `C:/Android/android-studio-sdk/platform-tools/adb.exe`

Exemplo com variável de ambiente na sessão atual do Git Bash:

```bash
export ADB_PATH="C:/Android/android-studio-sdk/platform-tools/adb.exe"
.venv/Scripts/logcat-manager --serial RQ8M708HWEZ
```

## Opções de linha de comando

```text
--adb-path CAMINHO          Caminho do executável adb
--serial SERIAL             Serial do dispositivo Android/emulador
--config ARQUIVO            Caminho alternativo para o JSON de configuração
--max-buffer-lines NUMERO   Máximo de linhas mantidas na memória (padrão: 10000)
-h, --help                  Mostra a ajuda
```

Exemplo para manter até 50 mil linhas:

```bash
.venv/Scripts/logcat-manager --max-buffer-lines 50000
```

## Interface interativa

A tela possui:

- área principal rolável com os logs;
- buffer local circular de até 10.000 linhas por padrão (ajustável com `--max-buffer-lines`);
- janela visual limitada às 2.000 linhas filtradas mais recentes para manter o terminal responsivo;
- cores por prioridade (`V`, `D`, `I`, `W`, `E` e `F`);
- barra de status com quantidade de linhas e filtros ativos;
- campo de comando sempre ativo no rodapé.

O campo inferior fica sempre ativo. Digite `/` para abrir/filtrar o menu de comandos; clique em uma opção para preencher o prompt e ajuste os argumentos antes de pressionar `Enter`. Texto sem `/` ou `:` é uma busca rápida.

Os comandos antigos com `:` continuam compatíveis, mas o formato recomendado é com `/`:

```text
/level E
/tag Activity
/find timeout
```

### Menu de comandos

O menu fica oculto para maximizar a leitura dos logs. Ao digitar `/`, ele mostra apenas os nomes dos comandos; continue digitando, como `/pac` ou `/reg`, para reduzir a lista. Clique em um comando para preenchê-lo no prompt. As explicações e exemplos completos ficam em `/help`, exibido na própria área de logs.

Opções de risco, como limpar logs, nunca inserem `confirm` automaticamente: digite a confirmação explicitamente.

### Filtrar diretamente por package

Não é preciso descobrir ou copiar PID. Informe o package em formato texto:

```text
/package br.com.tbs.afv.multiplatform
```

O aplicativo executa `adb shell pidof` internamente e aplica o filtro a todos os PIDs ativos daquele package. Para remover o filtro, use:

```text
/package clear
```

### Analisar logs com Codex

Depois de aplicar filtros, envie as linhas visíveis ao Codex para receber uma análise na própria área de logs:

```text
/analise
```

Inclua um foco opcional após o comando:

```text
/analise priorize erros de rede e timeouts
```

A análise é assíncrona e não bloqueia o prompt. O aplicativo envia no máximo 250 linhas filtradas, executa `codex exec --ephemeral --sandbox read-only` e exibe a resposta no painel principal. Digite qualquer filtro, busca ou comando depois da resposta para voltar à visualização de logs.

> Atenção: as linhas selecionadas são enviadas ao serviço do Codex. Evite analisar logs que contenham tokens, senhas, identificadores pessoais ou outros dados sensíveis.

| Comando | Descrição |
|---|---|
| `:level E` | Mostra somente erros `E` e fatais `F` |
| `:level all` | Remove o filtro de prioridade |
| `:tag Activity` | Filtra por tag, sem diferenciar maiúsculas/minúsculas |
| `:tag clear` | Remove o filtro de tag |
| `:pid 1234` | Filtra pelo PID do processo |
| `:pid clear` | Remove o filtro de PID |
| `:find timeout` | Filtra pela ocorrência de texto na mensagem |
| `:find clear` | Remove a busca textual |
| `:regex "FATAL EXCEPTION|ANR"` | Filtra por expressão regular, sem diferenciar maiúsculas/minúsculas |
| `:regex clear` | Remove o filtro regex |

Os filtros são combinados com **AND**. Por exemplo, `:level E` e `:tag OkHttp` exibem apenas erros/fatais cuja tag contém `OkHttp`.

### Controle da visualização

| Comando | Descrição |
|---|---|
| `:pause` | Pausa a atualização visual; logs continuam no buffer local |
| `:resume` | Retoma a visualização |
| `:follow` ou `End` | Volta ao fim da lista de logs |
| `:restart` | Reinicia a captura do `adb logcat` |
| `:device SERIAL` | Troca o dispositivo selecionado e reinicia a captura |
| `:quit` ou `q` | Fecha o aplicativo |

### Configuração e exportação

| Comando | Descrição |
|---|---|
| `:config show` | Mostra ADB e serial configurados |
| `:config adb "C:/Android/.../adb.exe"` | Salva um novo caminho padrão do ADB |
| `:save "C:/logs/erros.txt"` | Exporta as linhas atualmente visíveis em UTF-8 |

Por segurança, `:save` não sobrescreve um arquivo existente. Informe outro nome/caminho se necessário.

### Limpeza de logs

| Comando | Efeito |
|---|---|
| `:clear confirm` | Apaga somente o buffer local mostrado pelo aplicativo |
| `:adb-clear confirm` | Executa `adb logcat -c` e apaga o buffer de logs do dispositivo |

A limpeza remota exige obrigatoriamente `confirm`. Não execute `:adb-clear confirm` se quiser preservar os logs atuais do dispositivo.

## Cores das prioridades

| Nível | Cor |
|---|---|
| `V` | cinza discreto |
| `D` | azul |
| `I` | verde |
| `W` | amarelo |
| `E` | vermelho em negrito |
| `F` | vermelho vivo em negrito |

## Atalhos

| Atalho | Ação |
|---|---|
| `Ctrl+C` | Sai do aplicativo |
| `q` | Sai do aplicativo |
| `End` | Acompanha novamente o fim do log |
| `Esc` | Limpa o texto atualmente digitado no prompt |

## Solução de problemas

### ADB não encontrado

Informe o caminho diretamente:

```bash
.venv/Scripts/logcat-manager --adb-path "C:/Android/android-studio-sdk/platform-tools/adb.exe"
```

### Nenhum dispositivo aparece

Execute `adb devices`, confirme que o cabo/depuração USB estão ativos e aceite a chave RSA exibida no aparelho.

### Há mais de um dispositivo/emulador

Liste os seriais e inicie com um serial explícito:

```bash
"C:/Android/android-studio-sdk/platform-tools/adb.exe" devices
.venv/Scripts/logcat-manager --serial emulator-5554
```

### A tela não recebe novos logs

Confirme que o dispositivo selecionado está com estado `device`; em seguida, use `:restart`. Alguns dispositivos não geram linhas até que um aplicativo execute alguma ação.

## Desenvolvimento e validação

Execute a suíte automatizada:

```bash
.venv/Scripts/python -m pytest -v
```

Resultado validado nesta versão: **45 testes passando**.
