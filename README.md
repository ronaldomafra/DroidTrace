# Logcat Manager

Visualizador interativo de `adb logcat` para terminal, com cores, filtros locais, busca e exportação.

## Instalação

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org textual pytest pytest-asyncio
.venv/Scripts/python -m pip install --no-build-isolation -e .
```

## Início

```bash
.venv/Scripts/logcat-manager --adb-path "C:/Android/android-studio-sdk/platform-tools/adb.exe"
```

O caminho do ADB é resolvido nesta ordem: `--adb-path`, variável `ADB_PATH`, arquivo de configuração, `adb` no `PATH`, e o padrão Windows `C:/Android/android-studio-sdk/platform-tools/adb.exe`.

Para selecionar um dispositivo específico:

```bash
.venv/Scripts/logcat-manager --serial emulator-5554
```

## Prompt interativo

O campo inferior fica sempre disponível. Texto sem `:` faz uma pesquisa rápida. Use `:help` dentro do aplicativo para a referência de comandos.

Comandos principais:

| Comando | Efeito |
|---|---|
| `:level E` / `:level all` | Filtra por prioridade mínima ou remove o filtro |
| `:tag Activity` / `:tag clear` | Filtra pela tag |
| `:pid 1234` / `:pid clear` | Filtra pelo PID |
| `:find timeout` / `:find clear` | Pesquisa texto localmente |
| `:regex <padrão>` / `:regex clear` | Pesquisa por expressão regular |
| `:pause`, `:resume`, `:follow` | Controla a visualização em tempo real |
| `:save "C:/logs/erros.txt"` | Exporta as linhas visíveis em UTF-8 |
| `:clear confirm` | Limpa somente o buffer local |
| `:adb-clear confirm` | Limpa o buffer de log do dispositivo |
| `:device <serial>` | Troca o dispositivo e reinicia a captura |
| `:restart`, `:quit` | Reinicia a captura ou encerra o aplicativo |

`adb-clear` só é executado com `confirm` explícito. Filtros, pesquisa, pausa e limpeza local não modificam o dispositivo.

## Diagnóstico

Confira a conectividade antes de abrir o visualizador:

```bash
"C:/Android/android-studio-sdk/platform-tools/adb.exe" devices
```

Se um aparelho aparecer como `unauthorized`, desbloqueie-o e aceite a chave de depuração USB. Com mais de um dispositivo, informe `--serial` ou use `:device <serial>`.

## Desenvolvimento

```bash
.venv/Scripts/python -m pytest -v
```
