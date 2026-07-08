// PM2 entry point for Next.js dev server on Windows
const { spawn } = require('child_process');
const path = require('path');

const nextBin = path.join(__dirname, 'node_modules', '.bin', 'next.cmd');
const child = spawn(nextBin, ['dev', '--port', '4000'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true,
  windowsHide: true,
});

child.on('exit', (code) => process.exit(code));
