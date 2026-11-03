(() => {
  const browserBridge = location.hostname === '127.0.0.1' && location.port === '8765';
  if (!window.kitchenDesktop && !browserBridge) return;

  const planDisplayStyle = document.createElement('style');
  planDisplayStyle.textContent = '.canvas .floorplan { filter: contrast(1.55) brightness(.78); }';
  document.head.appendChild(planDisplayStyle);

  const tools = document.querySelector('.toolset');
  const importButton = document.getElementById('import');
  const fileInput = document.getElementById('file');
  const status = document.getElementById('status');
  if (!tools || !importButton || !fileInput || !status) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn ghost';
  button.id = 'importDwg';
  button.textContent = '导入 DWG';
  button.title = '本机转换 DWG 后自动导入锁定 SVG 底图';
  tools.insertBefore(button, importButton);

  function loadSvg(svg, fileName) {
    const transfer = new DataTransfer();
    transfer.items.add(new File([svg], fileName, { type: 'image/svg+xml' }));
    fileInput.files = transfer.files;
    fileInput.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function importWithBrowserBridge() {
    const picker = document.createElement('input');
    picker.type = 'file';
    picker.accept = '.dwg,application/acad,application/x-acad';
    picker.style.display = 'none';
    document.body.appendChild(picker);
    const file = await new Promise((resolve) => {
      picker.addEventListener('change', () => resolve(picker.files[0] || null), { once: true });
      picker.click();
    });
    picker.remove();
    if (!file) return null;
    const form = new FormData();
    form.append('dwg', file, file.name);
    const response = await fetch('/api/dwg/import', { method: 'POST', body: form });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `转换服务返回 ${response.status}`);
    return payload;
  }

  button.addEventListener('click', async () => {
    try {
      button.disabled = true;
      button.textContent = '正在转换 DWG…';
      status.textContent = '正在本机转换 DWG，请稍候…';
      let result;
      if (window.kitchenDesktop) {
        const dwgPath = await window.kitchenDesktop.pickDwg();
        if (!dwgPath) return;
        result = await window.kitchenDesktop.importDwg(dwgPath);
      } else {
        result = await importWithBrowserBridge();
        if (!result) return;
      }
      window.__dwgStructure = result.structure;
      window.__dwgImportFolder = result.outputDir;
      loadSvg(result.svg, result.svgFileName);
      status.textContent = `已导入 DWG 底图；SVG、结构 JSON 和 DXF 已保存至：${result.outputDir}`;
    } catch (error) {
      status.textContent = `DWG 导入失败：${error.message || String(error)}`;
    } finally {
      button.disabled = false;
      button.textContent = '导入 DWG';
    }
  });
})();
