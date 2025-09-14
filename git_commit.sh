#!/bin/bash

# 判断是否有参数作为提交说明
if [ -z "$1" ]; then
  COMMIT_MSG="更新"
else
  COMMIT_MSG="$1"
fi

# 拉取最新代码（避免冲突）
git pull origin $(git branch --show-current)

# 添加所有修改文件
git add .

# 提交并附带提交说明
git commit -m "$COMMIT_MSG"

# 推送到远程仓库（当前分支）
git push origin $(git branch --show-current)

echo "✅ 提交完成，信息：$COMMIT_MSG"
