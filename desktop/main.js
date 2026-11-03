const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs/promises');
const path = require('path');
const os = require('os');

const DEFAULT_ODA = 'C:\\Program Files\\ODA\\ODAFileConverter 27.9.0\\ODAFileConverter.exe';

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { windowsHide: true, ...options });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', data => { stdout += data; });
    child.stderr.on('data', data => { stderr += data; });
    child.on('error', reject);
    child.on('close', code => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${path.basename(command)} failed (exit ${code}). ${stderr || stdout}`));
    });
  });
}

async function odaPath() {
  const candidate = process.env.ODA_FILE_CONVERTER_PATH || DEFAULT_ODA;
  try {
    await fs.access(candidate);
    return candidate;
  } catch (_) {
    throw new Error(`未找到 ODA File Converter。请安装后重试：${candidate}`);
  }
}

function converterScriptPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'converter', 'convert_dxf.py')
    : path.join(__dirname, 'converter', 'convert_dxf.py');
}

function importFolderFor(filePath) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const safeName = path.basename(filePath, path.extname(filePath)).replace(/[\\/:*?"<>|]/g, '_');
  return path.join(app.getPath('documents'), '商业厨房空间编辑器', 'DWG导入', `${safeName}-${stamp}`);
}

async function convertDwg(sourcePath) {
  if (path.extname(sourcePath).toLowerCase() !== '.dwg') throw new Error('请选择 DWG 文件。');
  await fs.access(sourcePath);

  const oda = await odaPath();
  const outputDir = importFolderFor(sourcePath);
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'kitchen-dwg-'));
  const inputDir = path.join(temporaryRoot, 'input');
  const filename = path.basename(sourcePath);
  const baseName = path.basename(sourcePath, path.extname(sourcePath));

  try {
    await fs.mkdir(inputDir, { recursive: true });
    await fs.mkdir(outputDir, { recursive: true });
    await fs.copyFile(sourcePath, path.join(inputDir, filename));
    await run(oda, [inputDir, outputDir, 'ACAD2018', 'DXF', '0', '1', filename]);

    const dxfPath = path.join(outputDir, `${baseName}.dxf`);
    await fs.access(dxfPath);
    await run(process.env.PYTHON || 'python', [converterScriptPath(), dxfPath, outputDir]);

    const svgPath = path.join(outputDir, `${baseName}.svg`);
    const jsonPath = path.join(outputDir, `${baseName}.json`);
    const manifestPath = path.join(outputDir, `${baseName}.manifest.json`);
    const [svg, structure] = await Promise.all([
      fs.readFile(svgPath, 'utf8'),
      fs.readFile(jsonPath, 'utf8')
    ]);
    return { outputDir, svgFileName: path.basename(svgPath), svg, structure: JSON.parse(structure), manifestPath };
  } finally {
    await fs.rm(temporaryRoot, { recursive: true, force: true });
  }
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 960,
    minHeight: 680,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });
  window.loadFile(path.join(__dirname, '..', 'index.html'));
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
}

app.whenReady().then(() => {
  ipcMain.handle('dwg:pick', async () => {
    const result = await dialog.showOpenDialog({
      title: '选择 DWG 平面图',
      properties: ['openFile'],
      filters: [{ name: 'AutoCAD DWG', extensions: ['dwg'] }]
    });
    return result.canceled ? null : result.filePaths[0];
  });
  ipcMain.handle('dwg:import', (_, filePath) => convertDwg(filePath));
  ipcMain.handle('folder:reveal', (_, folderPath) => shell.openPath(folderPath));
  createWindow();
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
