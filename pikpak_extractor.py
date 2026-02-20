#!/usr/bin/env python3
"""
PikPak Share Link Extractor v4 - with Dropbox bulk upload (fixed)
Extracts real download links from PikPak shared folders and sends to Dropbox.
Run: pip install flask requests && python pikpak_extractor.py
Open: http://localhost:5000
"""

from flask import Flask, render_template_string, request, jsonify, Response
import requests
import re
import hashlib
import json
import time
import tempfile
import os

app = Flask(__name__)

API_BASE = "https://api-drive.mypikpak.net"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
CLIENT_ID = "YNxT9w7GMdWvEOKa"
CHUNK_SIZE = 50 * 1024 * 1024  # 50MB chunks for Dropbox upload sessions

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PikPak Link Extractor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh; color: #e0e0e0;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
        h1 {
            text-align: center; font-size: 2.2em; margin-bottom: 10px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; font-size: 0.95em; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input[type="text"], input[type="password"] {
            flex: 1; padding: 14px 18px; border: 2px solid #444; border-radius: 12px;
            background: rgba(255,255,255,0.06); color: #fff; font-size: 16px; outline: none;
            transition: border-color 0.3s;
        }
        input:focus { border-color: #667eea; }
        input::placeholder { color: #666; }
        .btn {
            padding: 14px 30px; border: none; border-radius: 12px; color: #fff;
            font-size: 16px; font-weight: 600; cursor: pointer; white-space: nowrap;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-extract { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-extract:hover { box-shadow: 0 6px 20px rgba(102,126,234,0.4); }
        .btn-dropbox { background: linear-gradient(135deg, #0061fe, #0d2481); margin-top: 15px; width: 100%; padding: 16px; font-size: 17px; }
        .btn-dropbox:hover { box-shadow: 0 6px 20px rgba(0,97,254,0.4); }
        .btn-test { background: linear-gradient(135deg, #28a745, #1a7a32); padding: 14px 20px; font-size: 14px; }
        .btn-test:hover { box-shadow: 0 6px 20px rgba(40,167,69,0.4); }
        .status { text-align: center; padding: 12px; border-radius: 8px; margin-bottom: 20px; display: none; }
        .status.loading { display: block; background: rgba(102,126,234,0.15); color: #667eea; }
        .status.error { display: block; background: rgba(234,102,102,0.15); color: #ea6666; }
        .status.success { display: block; background: rgba(102,234,126,0.15); color: #66ea7e; }
        .results { margin-top: 20px; }
        .folder-name {
            font-size: 1.3em; font-weight: 600; color: #667eea; margin-bottom: 15px;
            padding: 10px; background: rgba(102,126,234,0.08); border-radius: 8px;
        }
        .file-card {
            background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px; padding: 15px; margin-bottom: 10px; transition: background 0.2s;
        }
        .file-card:hover { background: rgba(255,255,255,0.08); }
        .file-info { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .file-name { font-weight: 500; color: #ddd; word-break: break-all; }
        .file-size { color: #888; font-size: 0.85em; white-space: nowrap; }
        .file-actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
        .btn-dl {
            padding: 8px 16px; border: none; border-radius: 8px; font-size: 13px;
            font-weight: 500; cursor: pointer; text-decoration: none; transition: transform 0.2s;
            display: inline-block;
        }
        .btn-dl:hover { transform: translateY(-1px); }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #ccc; border: 1px solid rgba(255,255,255,0.15); }
        .btn-copy {
            padding: 8px 16px; border: 1px solid rgba(255,255,255,0.15); border-radius: 8px;
            background: rgba(255,255,255,0.05); color: #aaa; font-size: 13px; cursor: pointer;
        }
        .btn-copy:hover { background: rgba(255,255,255,0.1); }
        .summary {
            margin-top: 20px; padding: 15px; background: rgba(102,126,234,0.08);
            border-radius: 10px; text-align: center;
        }
        .btn-copy-all {
            margin-top: 10px; padding: 10px 24px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #764ba2, #667eea); color: #fff;
            font-size: 14px; font-weight: 600; cursor: pointer;
        }
        .spinner {
            display: inline-block; width: 18px; height: 18px;
            border: 2px solid rgba(102,126,234,0.3); border-top: 2px solid #667eea;
            border-radius: 50%; animation: spin 0.8s linear infinite;
            vertical-align: middle; margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .note { text-align: center; color: #666; font-size: 0.8em; margin-top: 30px; }

        /* Dropbox section */
        .dropbox-section {
            display: none; margin-top: 25px; padding: 20px;
            background: rgba(0,97,254,0.08); border: 1px solid rgba(0,97,254,0.2);
            border-radius: 12px;
        }
        .dropbox-section h3 { color: #4d9aff; margin-bottom: 12px; font-size: 1.1em; }
        .dropbox-section .help-text {
            color: #888; font-size: 0.85em; margin-bottom: 12px; line-height: 1.5;
        }
        .dropbox-section a { color: #4d9aff; }
        .token-row { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }
        .folder-row { display: flex; gap: 10px; margin-bottom: 10px; }
        .folder-row input { flex: 1; }
        .token-status {
            font-size: 0.85em; padding: 6px 12px; border-radius: 8px; display: none;
        }
        .token-status.ok { display: inline-block; background: rgba(102,234,126,0.15); color: #66ea7e; }
        .token-status.fail { display: inline-block; background: rgba(234,102,102,0.15); color: #ea6666; }
        .warn-box {
            background: rgba(255,193,7,0.12); border: 1px solid rgba(255,193,7,0.3);
            border-radius: 8px; padding: 12px; margin-bottom: 12px; font-size: 0.85em; color: #ffc107;
        }

        /* Progress */
        .upload-progress { margin-top: 15px; }
        .upload-item {
            display: flex; align-items: center; gap: 12px; padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9em;
        }
        .upload-item:last-child { border-bottom: none; }
        .upload-icon { font-size: 1.2em; width: 24px; text-align: center; }
        .upload-name { flex: 1; color: #ccc; word-break: break-all; }
        .upload-status { color: #888; font-size: 0.85em; white-space: nowrap; }
        .upload-status.done { color: #66ea7e; }
        .upload-status.fail { color: #ea6666; }
        .upload-status.active { color: #4d9aff; }
        .progress-bar-bg {
            width: 100%; height: 6px; background: rgba(255,255,255,0.1);
            border-radius: 3px; margin-top: 10px; overflow: hidden;
        }
        .progress-bar-fill {
            height: 100%; background: linear-gradient(90deg, #0061fe, #4d9aff);
            border-radius: 3px; transition: width 0.3s;
        }
        .error-detail {
            margin-top: 6px; font-size: 0.8em; color: #ea6666; background: rgba(234,102,102,0.08);
            padding: 6px 10px; border-radius: 6px; word-break: break-all; display: none;
        }
        @media (max-width: 600px) {
            .input-group, .token-row, .folder-row { flex-direction: column; }
            .btn { width: 100%; }
            h1 { font-size: 1.6em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>&#128194; PikPak Link Extractor</h1>
        <p class="subtitle">Extraia links de download e envie direto pro Dropbox</p>
        <div class="input-group">
            <input type="text" id="shareUrl" placeholder="https://mypikpak.com/s/VOlvCe8ovMqcWmJglXpE8dpzo2" />
            <button class="btn btn-extract" id="extractBtn" onclick="extractLinks()">Extrair Links</button>
        </div>
        <div class="status" id="status"></div>
        <div class="results" id="results"></div>

        <div class="dropbox-section" id="dropboxSection">
            <h3>&#9729;&#65039; Enviar para Dropbox</h3>
            <div class="warn-box">
                &#9888;&#65039; <b>IMPORTANTE:</b> Marque as permissoes <b>ANTES</b> de gerar o token!<br>
                Se ja gerou, va em Permissions, marque e clique Submit, depois volte e gere um <b>NOVO</b> token.
            </div>
            <div class="help-text">
                1. Acesse <a href="https://www.dropbox.com/developers/apps" target="_blank">dropbox.com/developers/apps</a> &rarr; Create app<br>
                2. Escolha: <b>Scoped access</b> &rarr; <b>Full Dropbox</b> &rarr; nome qualquer<br>
                3. Va na aba <b>Permissions</b>, marque <b>files.content.write</b> e <b>files.content.read</b>, clique <b>Submit</b><br>
                4. Volte na aba <b>Settings</b>, clique <b>Generate</b> em "Generated access token" e cole abaixo
            </div>
            <div class="token-row">
                <input type="password" id="dbxToken" placeholder="Cole seu Dropbox access token aqui" />
                <button class="btn btn-test" onclick="testToken()">&#128275; Testar</button>
            </div>
            <span class="token-status" id="tokenStatus"></span>
            <div class="folder-row">
                <input type="text" id="dbxFolder" placeholder="Pasta no Dropbox (ex: /PikPak Downloads)" value="/PikPak Downloads" />
            </div>
            <button class="btn btn-dropbox" id="dbxBtn" onclick="sendToDropbox()">
                &#9729;&#65039; Enviar Todos os Videos para Dropbox
            </button>
            <div class="upload-progress" id="uploadProgress"></div>
        </div>

        <p class="note">Links de download expiram em ~24h. Uploads pro Dropbox sao permanentes.</p>
    </div>
    <script>
        let extractedFiles = [];
        let shareInfo = {};

        function fmtSize(b) {
            if (!b || b == 0) return 'N/A';
            b = parseInt(b);
            const u = ['B','KB','MB','GB','TB'];
            let i = 0;
            while (b >= 1024 && i < u.length-1) { b /= 1024; i++; }
            return b.toFixed(1)+' '+u[i];
        }
        function setStatus(t, m) {
            const el = document.getElementById('status');
            el.className = 'status ' + t;
            el.innerHTML = t === 'loading' ? '<span class="spinner"></span>' + m : m;
        }
        function cpText(text, btn) {
            navigator.clipboard.writeText(text).then(() => {
                const o = btn.textContent; btn.textContent = 'Copiado!';
                setTimeout(() => btn.textContent = o, 1500);
            });
        }

        async function testToken() {
            const token = document.getElementById('dbxToken').value.trim();
            if (!token) { alert('Cole o token primeiro!'); return; }
            const st = document.getElementById('tokenStatus');
            st.className = 'token-status'; st.style.display = 'inline-block';
            st.textContent = 'Testando...'; st.style.color = '#888';
            try {
                const r = await fetch('/api/dropbox-test', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({token})
                });
                const d = await r.json();
                if (d.success) {
                    st.className = 'token-status ok';
                    st.textContent = '\u2705 Conectado: ' + d.name + ' (' + d.email + ')';
                } else {
                    st.className = 'token-status fail';
                    st.textContent = '\u274C ' + d.error;
                }
            } catch(e) {
                st.className = 'token-status fail';
                st.textContent = '\u274C Erro: ' + e.message;
            }
        }

        async function extractLinks() {
            const url = document.getElementById('shareUrl').value.trim();
            if (!url) return;
            const btn = document.getElementById('extractBtn');
            btn.disabled = true; btn.textContent = 'Extraindo...';
            document.getElementById('results').innerHTML = '';
            document.getElementById('dropboxSection').style.display = 'none';
            extractedFiles = [];
            setStatus('loading', 'Listando arquivos do PikPak...');
            try {
                const r1 = await fetch('/api/list', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url})
                });
                const d1 = await r1.json();
                if (!d1.success) { setStatus('error', 'Erro: ' + d1.error); return; }
                if (d1.files.length === 0) { setStatus('error', 'Nenhum arquivo encontrado.'); return; }
                shareInfo = { share_id: d1.share_id, pass_code_token: d1.pass_code_token, share_name: d1.share_name };

                setStatus('loading', 'Extraindo links de ' + d1.files.length + ' arquivo(s)...');
                const r2 = await fetch('/api/links', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ share_id: d1.share_id, pass_code_token: d1.pass_code_token, files: d1.files })
                });
                const d2 = await r2.json();
                if (!d2.success) { setStatus('error', 'Erro: ' + d2.error); return; }

                extractedFiles = d2.files;
                const withLinks = extractedFiles.filter(f => f.download_url);
                setStatus('success', withLinks.length + '/' + extractedFiles.length + ' link(s) extraido(s)!');

                let html = '';
                if (d1.share_name) html += '<div class="folder-name">&#128193; ' + d1.share_name + '</div>';
                let allLinks = [];
                extractedFiles.forEach(function(f) {
                    const dl = f.download_url || '';
                    if (dl) allLinks.push(dl);
                    html += '<div class="file-card"><div class="file-info">';
                    html += '<span class="file-name">' + f.name + '</span>';
                    html += '<span class="file-size">' + fmtSize(f.size) + '</span>';
                    html += '</div><div class="file-actions">';
                    if (dl) {
                        html += '<a href="' + dl + '" target="_blank" class="btn-dl btn-primary">&#11015; Download</a>';
                        html += '<button class="btn-copy" onclick="cpText(decodeURIComponent(\'' + encodeURIComponent(dl) + '\'), this)">Copiar Link</button>';
                    } else {
                        html += '<span style="color:#ea6666;font-size:13px">Link indisponivel</span>';
                    }
                    html += '</div></div>';
                });
                if (allLinks.length > 0) {
                    const enc = encodeURIComponent(allLinks.join('\n'));
                    html += '<div class="summary"><strong>' + allLinks.length + ' link(s) de download</strong><br/>';
                    html += '<button class="btn-copy-all" onclick="cpText(decodeURIComponent(\'' + enc + '\'), this)">&#128203; Copiar Todos os Links</button></div>';
                }
                document.getElementById('results').innerHTML = html;

                // Show Dropbox section if there are downloadable files
                const videos = extractedFiles.filter(f => f.download_url);
                if (videos.length > 0) {
                    document.getElementById('dropboxSection').style.display = 'block';
                    if (d1.share_name) {
                        document.getElementById('dbxFolder').value = '/PikPak Downloads/' + d1.share_name.replace(/[<>:"|?*]/g, '_');
                    }
                }
            } catch (e) {
                setStatus('error', 'Erro: ' + e.message);
            } finally {
                btn.disabled = false; btn.textContent = 'Extrair Links';
            }
        }

        async function sendToDropbox() {
            const token = document.getElementById('dbxToken').value.trim();
            if (!token) { alert('Cole o Dropbox access token primeiro!'); return; }
            const folder = document.getElementById('dbxFolder').value.trim() || '/PikPak Downloads';
            const videos = extractedFiles.filter(f => f.download_url);
            if (videos.length === 0) { alert('Nenhum arquivo com link disponivel.'); return; }

            const btn = document.getElementById('dbxBtn');
            btn.disabled = true; btn.textContent = 'Enviando...';
            const prog = document.getElementById('uploadProgress');

            let phtml = '<div class="progress-bar-bg"><div class="progress-bar-fill" id="totalBar" style="width:0%"></div></div>';
            phtml += '<div style="text-align:center;color:#888;font-size:0.85em;margin:8px 0" id="totalText">0/' + videos.length + ' arquivos</div>';
            videos.forEach((f, i) => {
                phtml += '<div class="upload-item" id="up-' + i + '">';
                phtml += '<span class="upload-icon">&#9744;</span>';
                phtml += '<span class="upload-name">' + f.name.split('/').pop() + ' (' + fmtSize(f.size) + ')</span>';
                phtml += '<span class="upload-status" id="upst-' + i + '">Aguardando</span>';
                phtml += '</div>';
                phtml += '<div class="error-detail" id="uperr-' + i + '"></div>';
            });
            prog.innerHTML = phtml;

            try {
                const resp = await fetch('/api/dropbox-upload', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        token, folder,
                        share_id: shareInfo.share_id,
                        pass_code_token: shareInfo.pass_code_token,
                        files: videos
                    })
                });
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buf = '';
                let done_count = 0;

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    buf += decoder.decode(value, {stream: true});
                    const lines = buf.split('\n');
                    buf = lines.pop();
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        try {
                            const ev = JSON.parse(line.slice(6));
                            const idx = ev.index;
                            const icon = document.querySelector('#up-' + idx + ' .upload-icon');
                            const st = document.getElementById('upst-' + idx);
                            const errEl = document.getElementById('uperr-' + idx);
                            if (ev.type === 'start') {
                                if (icon) icon.textContent = '\u23F3';
                                if (st) { st.textContent = 'Baixando do PikPak...'; st.className = 'upload-status active'; }
                            } else if (ev.type === 'downloading') {
                                if (st) { st.textContent = 'Baixando ' + ev.percent + '%'; st.className = 'upload-status active'; }
                            } else if (ev.type === 'uploading') {
                                if (st) { st.textContent = 'Enviando pro Dropbox ' + ev.percent + '%'; st.className = 'upload-status active'; }
                            } else if (ev.type === 'done') {
                                done_count++;
                                if (icon) icon.textContent = '\u2705';
                                if (st) { st.textContent = 'Enviado!'; st.className = 'upload-status done'; }
                                document.getElementById('totalBar').style.width = (done_count/videos.length*100) + '%';
                                document.getElementById('totalText').textContent = done_count + '/' + videos.length + ' arquivos';
                            } else if (ev.type === 'error') {
                                done_count++;
                                if (icon) icon.textContent = '\u274C';
                                if (st) { st.textContent = 'Erro'; st.className = 'upload-status fail'; }
                                if (errEl && ev.detail) { errEl.textContent = ev.detail; errEl.style.display = 'block'; }
                                document.getElementById('totalBar').style.width = (done_count/videos.length*100) + '%';
                                document.getElementById('totalText').textContent = done_count + '/' + videos.length + ' arquivos';
                            } else if (ev.type === 'complete') {
                                document.getElementById('totalText').textContent = 'Concluido! ' + ev.ok + '/' + ev.total + ' enviados com sucesso';
                            }
                        } catch(e) {}
                    }
                }
            } catch (e) {
                alert('Erro na conexao: ' + e.message);
            } finally {
                btn.disabled = false; btn.textContent = '\u2601\uFE0F Enviar Todos os Videos para Dropbox';
            }
        }

        const p = new URLSearchParams(location.search);
        if (p.get('url')) { document.getElementById('shareUrl').value = p.get('url'); extractLinks(); }
    </script>
</body>
</html>"""

def extract_share_id(url):
    m = re.search(r'/s/([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else url.strip()

def get_headers(share_id):
    return {
        "User-Agent": USER_AGENT,
        "Referer": "https://mypikpak.com/",
        "Origin": "https://mypikpak.com",
        "X-Client-Id": CLIENT_ID,
        "X-Device-Id": hashlib.md5(share_id.encode()).hexdigest(),
    }

def get_share_info(share_id):
    resp = requests.get(
        f"{API_BASE}/drive/v1/share",
        params={"share_id": share_id, "thumbnail_size": "SIZE_LARGE"},
        headers=get_headers(share_id), timeout=15
    )
    return resp.json()

def list_share_files(share_id, pass_code_token="", parent_id="", prefix=""):
    all_files = []
    page_token = ""
    headers = get_headers(share_id)
    while True:
        params = {
            "share_id": share_id, "parent_id": parent_id,
            "thumbnail_size": "SIZE_LARGE", "limit": "100", "with_audit": "false",
        }
        if pass_code_token:
            params["pass_code_token"] = pass_code_token
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(f"{API_BASE}/drive/v1/share/detail", params=params, headers=headers, timeout=15)
        data = resp.json()
        for f in data.get("files", []):
            name = prefix + f.get("name", "")
            if f.get("kind") == "drive#folder":
                sub = list_share_files(share_id, pass_code_token, f["id"], name + "/")
                all_files.extend(sub)
            else:
                all_files.append({
                    "id": f.get("id", ""),
                    "name": name,
                    "size": f.get("size", "0"),
                    "mime_type": f.get("mime_type", ""),
                })
        next_t = data.get("next_page_token", "")
        if not next_t:
            break
        page_token = next_t
    return all_files

def get_file_download_link(share_id, file_id, pass_code_token=""):
    headers = get_headers(share_id)
    params = {"share_id": share_id, "file_id": file_id, "pass_code_token": pass_code_token}
    resp = requests.get(f"{API_BASE}/drive/v1/share/file_info", params=params, headers=headers, timeout=15)
    data = resp.json()
    fi = data.get("file_info", {})
    wcl = fi.get("web_content_link", "")
    if wcl:
        return wcl
    links = fi.get("links", {})
    if links:
        for v in links.values():
            if v.get("url"):
                return v["url"]
    medias = fi.get("medias", [])
    for m in medias:
        link = m.get("link", {})
        if link and link.get("url"):
            return link["url"]
    return ""


def dropbox_upload_file(token, tmp_path, actual_size, dropbox_path, progress_callback=None):
    """Upload a local temp file to Dropbox. Returns result dict or raises Exception."""
    dbx_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }

    if actual_size <= 140 * 1024 * 1024:  # <=140MB: simple upload
        with open(tmp_path, 'rb') as f:
            data = f.read()
        if progress_callback:
            progress_callback(50)
        resp = requests.post(
            "https://content.dropboxapi.com/2/files/upload",
            headers={
                **dbx_headers,
                "Dropbox-API-Arg": json.dumps({
                    "path": dropbox_path,
                    "mode": "add",
                    "autorename": True,
                    "mute": False,
                }, ensure_ascii=True)
            },
            data=data, timeout=600
        )
        if resp.status_code != 200:
            error_detail = resp.text[:500]
            try:
                ej = resp.json()
                error_detail = ej.get("error_summary", ej.get("error", {}).get(".tag", error_detail))
            except:
                pass
            raise Exception(f"Dropbox {resp.status_code}: {error_detail}")
        if progress_callback:
            progress_callback(100)
        return resp.json()
    else:
        # Large file: upload session with chunks
        with open(tmp_path, 'rb') as f:
            first_chunk = f.read(CHUNK_SIZE)

        # Start session WITH first chunk
        start_resp = requests.post(
            "https://content.dropboxapi.com/2/files/upload_session/start",
            headers={
                **dbx_headers,
                "Dropbox-API-Arg": json.dumps({"close": False}, ensure_ascii=True)
            },
            data=first_chunk, timeout=600
        )
        if start_resp.status_code != 200:
            error_detail = start_resp.text[:500]
            try:
                ej = start_resp.json()
                error_detail = ej.get("error_summary", ej.get("error", {}).get(".tag", error_detail))
            except:
                pass
            raise Exception(f"Dropbox session/start {start_resp.status_code}: {error_detail}")

        session_id = start_resp.json()["session_id"]
        offset = len(first_chunk)
        if progress_callback:
            progress_callback(int(offset * 100 / actual_size))

        with open(tmp_path, 'rb') as f:
            f.seek(offset)
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                remaining_after = actual_size - offset - len(chunk)

                if remaining_after <= 0:
                    # Finish session with last chunk
                    finish_resp = requests.post(
                        "https://content.dropboxapi.com/2/files/upload_session/finish",
                        headers={
                            **dbx_headers,
                            "Dropbox-API-Arg": json.dumps({
                                "cursor": {"session_id": session_id, "offset": offset},
                                "commit": {
                                    "path": dropbox_path,
                                    "mode": "add",
                                    "autorename": True,
                                    "mute": False,
                                }
                            }, ensure_ascii=True)
                        },
                        data=chunk, timeout=600
                    )
                    if finish_resp.status_code != 200:
                        error_detail = finish_resp.text[:500]
                        try:
                            ej = finish_resp.json()
                            error_detail = ej.get("error_summary", error_detail)
                        except:
                            pass
                        raise Exception(f"Dropbox session/finish {finish_resp.status_code}: {error_detail}")
                    if progress_callback:
                        progress_callback(100)
                    return finish_resp.json()
                else:
                    # Append chunk
                    append_resp = requests.post(
                        "https://content.dropboxapi.com/2/files/upload_session/append_v2",
                        headers={
                            **dbx_headers,
                            "Dropbox-API-Arg": json.dumps({
                                "cursor": {"session_id": session_id, "offset": offset},
                                "close": False
                            }, ensure_ascii=True)
                        },
                        data=chunk, timeout=600
                    )
                    if append_resp.status_code != 200:
                        error_detail = append_resp.text[:500]
                        try:
                            ej = append_resp.json()
                            error_detail = ej.get("error_summary", error_detail)
                        except:
                            pass
                        raise Exception(f"Dropbox session/append {append_resp.status_code}: {error_detail}")
                    offset += len(chunk)
                    if progress_callback:
                        progress_callback(int(offset * 100 / actual_size))

        # Edge case: finish with empty data
        finish_resp = requests.post(
            "https://content.dropboxapi.com/2/files/upload_session/finish",
            headers={
                **dbx_headers,
                "Dropbox-API-Arg": json.dumps({
                    "cursor": {"session_id": session_id, "offset": offset},
                    "commit": {
                        "path": dropbox_path,
                        "mode": "add",
                        "autorename": True,
                        "mute": False,
                    }
                }, ensure_ascii=True)
            },
            data=b"", timeout=600
        )
        if finish_resp.status_code != 200:
            error_detail = finish_resp.text[:500]
            try:
                ej = finish_resp.json()
                error_detail = ej.get("error_summary", error_detail)
            except:
                pass
            raise Exception(f"Dropbox session/finish {finish_resp.status_code}: {error_detail}")
        if progress_callback:
            progress_callback(100)
        return finish_resp.json()


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/list", methods=["POST"])
def api_list():
    try:
        data = request.get_json()
        url = data.get("url", "")
        if not url:
            return jsonify({"success": False, "error": "URL nao fornecida"})
        share_id = extract_share_id(url)
        share_info = get_share_info(share_id)
        if share_info.get("error"):
            return jsonify({"success": False, "error": share_info.get("error_description", "Erro")})
        share_name = share_info.get("title", "")
        pass_code_token = share_info.get("pass_code_token", "")
        files = list_share_files(share_id, pass_code_token)
        return jsonify({
            "success": True, "share_name": share_name,
            "share_id": share_id, "pass_code_token": pass_code_token,
            "files": files, "total": len(files)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/links", methods=["POST"])
def api_links():
    try:
        data = request.get_json()
        share_id = data.get("share_id", "")
        pass_code_token = data.get("pass_code_token", "")
        files = data.get("files", [])
        results = []
        for f in files:
            dl_url = get_file_download_link(share_id, f["id"], pass_code_token)
            results.append({
                "id": f["id"], "name": f["name"],
                "size": f.get("size", "0"), "download_url": dl_url,
            })
        return jsonify({"success": True, "files": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/dropbox-test", methods=["POST"])
def api_dropbox_test():
    """Test Dropbox token by calling get_current_account."""
    try:
        data = request.get_json()
        token = data.get("token", "")
        resp = requests.post(
            "https://api.dropboxapi.com/2/users/get_current_account",
            headers={"Authorization": f"Bearer {token}", "Content-Type": ""},
            timeout=10
        )
        if resp.status_code == 200:
            acct = resp.json()
            return jsonify({
                "success": True,
                "name": acct.get("name", {}).get("display_name", "?"),
                "email": acct.get("email", "?"),
            })
        else:
            error_detail = resp.text[:300]
            try:
                ej = resp.json()
                error_detail = ej.get("error_summary", ej.get("error", {}).get(".tag", error_detail))
            except:
                pass
            return jsonify({"success": False, "error": f"HTTP {resp.status_code}: {error_detail}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/dropbox-upload", methods=["POST"])
def api_dropbox_upload():
    data = request.get_json()
    token = data.get("token", "")
    folder = data.get("folder", "/PikPak Downloads").rstrip("/")
    share_id = data.get("share_id", "")
    pass_code_token = data.get("pass_code_token", "")
    files = data.get("files", [])

    def generate():
        ok = 0
        for i, f in enumerate(files):
            fname = f["name"].split("/")[-1]
            # Sanitize filename for Dropbox
            safe_fname = re.sub(r'[<>:"|?*]', '_', fname)
            dbx_path = f"{folder}/{safe_fname}"

            yield f'data: {json.dumps({"type":"start","index":i,"name":fname}, ensure_ascii=True)}\n\n'

            tmp_path = None
            try:
                # Get fresh download link
                dl_url = f.get("download_url", "")
                if not dl_url:
                    dl_url = get_file_download_link(share_id, f["id"], pass_code_token)
                if not dl_url:
                    yield f'data: {json.dumps({"type":"error","index":i,"detail":"Sem link de download"}, ensure_ascii=True)}\n\n'
                    continue

                # Phase 1: Download from PikPak to temp file
                yield f'data: {json.dumps({"type":"downloading","index":i,"percent":0}, ensure_ascii=True)}\n\n'

                tmp_fd, tmp_path = tempfile.mkstemp(suffix='.tmp')
                os.close(tmp_fd)

                dl_resp = requests.get(dl_url, stream=True, timeout=30,
                                       headers={"User-Agent": USER_AGENT})
                dl_resp.raise_for_status()

                total_size = int(f.get("size", 0)) or int(dl_resp.headers.get("content-length", 0))
                downloaded = 0
                with open(tmp_path, 'wb') as tmp_file:
                    for chunk in dl_resp.iter_content(chunk_size=8 * 1024 * 1024):
                        if chunk:
                            tmp_file.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = min(int(downloaded * 100 / total_size), 100)
                                yield f'data: {json.dumps({"type":"downloading","index":i,"percent":pct}, ensure_ascii=True)}\n\n'

                actual_size = os.path.getsize(tmp_path)

                # Phase 2: Upload from temp file to Dropbox
                def upload_progress(pct):
                    pass  # We yield manually below; callback not used in SSE context

                yield f'data: {json.dumps({"type":"uploading","index":i,"percent":0}, ensure_ascii=True)}\n\n'
                result = dropbox_upload_file(token, tmp_path, actual_size, dbx_path)
                yield f'data: {json.dumps({"type":"uploading","index":i,"percent":100}, ensure_ascii=True)}\n\n'

                ok += 1
                yield f'data: {json.dumps({"type":"done","index":i,"path":result.get("path_display","")}, ensure_ascii=True)}\n\n'

            except Exception as e:
                detail = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        ej = e.response.json()
                        detail = ej.get("error_summary", ej.get("error", {}).get(".tag", detail))
                    except:
                        detail = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
                yield f'data: {json.dumps({"type":"error","index":i,"detail":detail[:500]}, ensure_ascii=True)}\n\n'
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass

        yield f'data: {json.dumps({"type":"complete","ok":ok,"total":len(files)}, ensure_ascii=True)}\n\n'

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    print("=" * 50)
    print("  PikPak Link Extractor v4")
    print("  Com envio em massa para Dropbox!")
    print("  Abra: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
