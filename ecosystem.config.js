module.exports = {
  apps: [{
    name: 'download-bot',
    script: 'main_fixed.py',
    interpreter: 'python3',
    cwd: '/root/download_bot',
    env: {
      NODE_ENV: 'production'
    },
    error_file: '/root/.pm2/logs/download-bot-error.log',
    out_file: '/root/.pm2/logs/download-bot-out.log',
    log_file: '/root/.pm2/logs/download-bot-combined.log',
    time: true,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    restart_delay: 5000,
    max_restarts: 10,
    min_uptime: '10s'
  }]
};
