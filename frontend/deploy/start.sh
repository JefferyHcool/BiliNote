#!/bin/sh
###
 # @Author: Jefferyhcool 1063474837@qq.com
 # @Date: 2025-04-16 01:57:05
 # @LastEditors: Jefferyhcool 1063474837@qq.com
 # @LastEditTime: 2025-04-16 01:59:37
 # @FilePath: /hotfix-dev/BillNote_frontend/deploy/start.sh
 # @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
### 
# 等待后端健康检查通过
until curl -s "http://backend:${BACKEND_PORT}/health" > /dev/null; do
    echo "等待后端服务就绪..."
    sleep 2
done

# 生成 nginx 配置文件（动态变量替换）
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# 启动 Nginx（在前台运行）
exec nginx -g 'daemon off;'