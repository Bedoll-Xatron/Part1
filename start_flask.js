// PM2 entry point for Flask backend on Windows
const { spawn } = require('child_process');
const path = require('path');

const child = spawn('python', ['run.py'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true,
  windowsHide: true,
});

child.on('exit', (code) => process.exit(code));
