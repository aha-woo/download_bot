module.exports = {
  apps: [{
    name: 'download-bot',
    script: './main.py',
    interpreter: '/root/download_bot/venv/bin/python3', // 虚拟环境Python路径
    cwd: '/root/download_bot', // 工作目录
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '2G', // User API可能需要更多内存
    restart_delay: 5000,
    max_restarts: 10,
    min_uptime: '10s',
    env: {
      NODE_ENV: 'production',
      PYTHONPATH: '/root/download_bot', // 确保Python路径
      // .env文件会被python-dotenv自动加载，无需在这里重复定义
    },
    // 日志配置
    error_file: '/root/download_bot/logs/err.log',
    out_file: '/root/download_bot/logs/out.log',
    log_file: '/root/download_bot/logs/combined.log',
    time: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    // 自动创建日志目录
    combine_logs: true,
    merge_logs: true
  }]
};