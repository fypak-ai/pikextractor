# PikPak Link Extractor v4

Extrai links de download reais de pastas compartilhadas do PikPak e envia direto pro Dropbox.

## Funcionalidades

- 🔗 **Extrai links de download** de qualquer link `mypikpak.com/s/...`
- 📂 **Navega subpastas** recursivamente
- ☁️ **Envio em massa pro Dropbox** — direto do PikPak, sem salvar no seu PC
- ✅ **Botão "Testar"** — verifica o token do Dropbox antes de enviar
- 📊 **Progresso em 2 fases** — download do PikPak + upload pro Dropbox
- ❌ **Erros detalhados** — mostra exatamente o que o Dropbox recusou

## Como rodar

```bash
pip install flask requests
python pikpak_extractor.py
```

Abra no navegador: **http://localhost:5000**

## Configuração do Dropbox

1. Acesse [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps)
2. Crie um app (Scoped access → Full Dropbox)
3. Em **Permissions**, marque `files.content.write` + `files.content.read` → **Submit**
4. Volte em **Settings** e gere o **Generated access token**

⚠️ **Importante:** Gere o token DEPOIS de configurar as permissões!
