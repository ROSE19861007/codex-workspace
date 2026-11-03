/* Local-first Supabase project sync. The publishable key is supplied by the owner
   in the app and is included only in the fragment of generated share links. */
(() => {
  const STORAGE_KEY = 'kitchen-space-editor-cloud-v1';
  const PUBLIC_EDITOR_URL = 'https://rose19861007.github.io/codex-workspace/';

  const parseStored = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (_) { return {}; }
  };
  const writeStored = value => localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  const cleanUrl = value => String(value || '').trim().replace(/\/+$/, '');
  const fragment = () => new URLSearchParams(location.hash.replace(/^#/, ''));

  async function rpc(config, name, payload) {
    const response = await fetch(`${cleanUrl(config.url)}/rest/v1/rpc/${name}`, {
      method: 'POST',
      headers: { apikey: config.key, Authorization: `Bearer ${config.key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.message || value.error || `云端请求失败（${response.status}）`);
    return value;
  }

  function clipboard(text) {
    if (navigator.clipboard && location.protocol === 'https:') return navigator.clipboard.writeText(text);
    const field = document.createElement('textarea');
    field.value = text; document.body.appendChild(field); field.select();
    document.execCommand('copy'); field.remove();
    return Promise.resolve();
  }

  function init() {
    const api = window.__spaceEditorCloud;
    const tools = document.querySelector('.toolset');
    const status = document.getElementById('status');
    if (!api || !tools || !status || document.getElementById('cloudSettings')) return;

    const style = document.createElement('style');
    style.textContent = '.cloud-note{font-size:11px;color:#52677e;margin-left:2px}.cloud-note.busy{color:#a56512}.cloud-note.error{color:#b73f39}';
    document.head.appendChild(style);
    const state = parseStored();
    let timer = null, saving = false;

    const settings = document.createElement('button');
    settings.id = 'cloudSettings'; settings.className = 'btn ghost'; settings.type = 'button'; settings.textContent = '云端设置';
    const save = document.createElement('button');
    save.id = 'cloudSave'; save.className = 'btn ghost'; save.type = 'button'; save.textContent = '保存云端';
    const view = document.createElement('button');
    view.id = 'cloudViewLink'; view.className = 'btn ghost'; view.type = 'button'; view.textContent = '复制手机查看链接';
    const edit = document.createElement('button');
    edit.id = 'cloudEditLink'; edit.className = 'btn ghost'; edit.type = 'button'; edit.textContent = '复制手机编辑链接';
    const note = document.createElement('span'); note.className = 'cloud-note';
    tools.append(settings, save, view, edit, note);

    const update = (message, kind = '') => { note.textContent = message; note.className = `cloud-note ${kind}`; };
    const configured = () => Boolean(cleanUrl(state.url) && state.key);
    const configuredProject = () => Boolean(configured() && state.projectId && state.editSecret);

    function setSettings() {
      const url = prompt('Supabase Project URL（例如 https://xxxx.supabase.co）', state.url || '');
      if (url === null) return false;
      const key = prompt('Supabase publishable / anon key（仅保存在此浏览器）', state.key || '');
      if (key === null) return false;
      state.url = cleanUrl(url); state.key = String(key).trim();
      if (!/^https:\/\/.+\.supabase\.co$/i.test(state.url) || !state.key) {
        update('云端设置格式不正确', 'error'); return false;
      }
      writeStored(state); update('云端连接已保存到此设备'); return true;
    }

    function makeLink(secret) {
      const params = new URLSearchParams({ project: state.projectId, secret, supabase: state.url, key: state.key });
      return `${PUBLIC_EDITOR_URL}#${params.toString()}`;
    }

    async function saveCloud(quiet = false) {
      if (saving) return;
      if (!configured() && !setSettings()) return;
      saving = true;
      try {
        const snapshot = api.snapshot();
        if (!state.projectId || !state.editSecret) {
          update('正在创建云端项目…', 'busy');
          const result = await rpc(state, 'space_editor_create_project', { p_name: snapshot.projectName || '商业厨房项目', p_snapshot: snapshot });
          const record = Array.isArray(result) ? result[0] : result;
          state.projectId = record.project_id; state.editSecret = record.edit_secret; state.viewSecret = record.view_secret;
          writeStored(state);
          update('云端项目已创建并保存');
        } else {
          if (!quiet) update('正在保存云端…', 'busy');
          await rpc(state, 'space_editor_write_project', { p_project_id: state.projectId, p_edit_secret: state.editSecret, p_snapshot: snapshot });
          update('已自动同步');
        }
      } catch (error) {
        update(error.message || '云端保存失败', 'error');
      } finally { saving = false; }
    }

    async function loadFromLink() {
      const hash = fragment();
      const projectId = hash.get('project'), secret = hash.get('secret'), url = cleanUrl(hash.get('supabase')),
        key = hash.get('key');
      if (!projectId || !secret || !url || !key) return;
      try {
        update('正在加载云端项目…', 'busy');
        const result = await rpc({ url, key }, 'space_editor_read_project', { p_project_id: projectId, p_secret: secret });
        const record = Array.isArray(result) ? result[0] : result;
        api.load(record.project_snapshot);
        state.url = url; state.key = key; state.projectId = projectId;
        if (record.can_edit) { state.editSecret = secret; } else { delete state.editSecret; }
        writeStored(state);
        update(record.can_edit ? '已载入云端项目（可编辑）' : '已载入云端项目（只读）');
      } catch (error) { update(error.message || '无法载入分享项目', 'error'); }
    }

    settings.addEventListener('click', setSettings);
    save.addEventListener('click', () => saveCloud(false));
    view.addEventListener('click', async () => {
      if (!configuredProject()) { await saveCloud(false); if (!configuredProject()) return; }
      await clipboard(makeLink(state.viewSecret)); update('手机查看链接已复制');
    });
    edit.addEventListener('click', async () => {
      if (!configuredProject()) { await saveCloud(false); if (!configuredProject()) return; }
      await clipboard(makeLink(state.editSecret)); update('手机编辑链接已复制；请只发给可信任的人');
    });
    document.addEventListener('pointerup', () => {
      if (!configuredProject()) return;
      clearTimeout(timer); timer = setTimeout(() => saveCloud(true), 900);
    }, true);
    document.getElementById('projectName').addEventListener('change', () => {
      if (configuredProject()) saveCloud(true);
    });
    loadFromLink();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
