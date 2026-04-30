#!/usr/bin/env bash
# ============================================================
# Security Lint — 提交前安全检查脚本
# 检查项：绝对路径、硬编码凭证、敏感文件
# 用法：bash scripts/lint.sh [--staged]
# ============================================================
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

red()    { echo -e "${RED}$*${NC}"; }
yellow() { echo -e "${YELLOW}$*${NC}"; }
green()  { echo -e "${GREEN}$*${NC}"; }

echo ""
echo "=============================="
echo "  Security Lint Check"
echo "=============================="
echo ""

# ---------- 获取要检查的文件列表 ----------
if [ "${1:-}" = "--staged" ]; then
    FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || echo "")
    SCOPE="staged"
else
    FILES=$(git diff --name-only --diff-filter=ACM HEAD 2>/dev/null || echo "")
    SCOPE="changed"
fi

if [ -z "$FILES" ]; then
    green "[OK] 没有需要检查的文件"
    exit 0
fi

echo "检查范围: $SCOPE ($(echo "$FILES" | wc -l) files)"
echo ""

# ---------- 检查 1：敏感文件不应被提交 ----------
echo "--- 检查 1: 敏感文件 ---"

SENSITIVE_PATTERNS=(
    "cookies.txt"
    "\.env$"
    "credentials"
    "\.pem$"
    "\.key$"
    "id_rsa"
    "\.pfx$"
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    matches=$(echo "$FILES" | grep -E "$pattern" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        while IFS= read -r f; do
            red "  [ERROR] 敏感文件不应提交: $f"
            ERRORS=$((ERRORS + 1))
        done <<< "$matches"
    fi
done

# ---------- 检查 2：Python 文件中不应有硬编码绝对路径 ----------
echo "--- 检查 2: 硬编码绝对路径 ---"

# 只检查 Python 文件
PY_FILES=$(echo "$FILES" | grep -E '\.py$' 2>/dev/null || true)

if [ -n "$PY_FILES" ]; then
    # Windows 绝对路径 (如 D:/xxx, C:\xxx)
    WIN_ABS=$(grep -Hn '"[A-Z]:[/\\]' $PY_FILES 2>/dev/null || true)
    # 需要排除 Docker 路径 /app/（合法的容器内路径）
    if [ -n "$WIN_ABS" ]; then
        red "  [ERROR] 发现 Windows 硬编码绝对路径:"
        echo "$WIN_ABS" | while IFS= read -r line; do
            # 跳过注释行
            if [[ "$line" != *"#"* || "$line" == *"[A-Z]:[/\\]"* ]]; then
                red "    $line"
                ERRORS=$((ERRORS + 1))
            fi
        done
    fi

    # Unix 用户绝对路径 (如 /home/, /Users/)
    UNIX_ABS=$(grep -Hn '"/home/\|"/Users/' $PY_FILES 2>/dev/null || true)
    if [ -n "$UNIX_ABS" ]; then
        red "  [ERROR] 发现 Unix 用户绝对路径:"
        echo "$UNIX_ABS" | while IFS= read -r line; do
            red "    $line"
            ERRORS=$((ERRORS + 1))
        done
    fi
fi

# ---------- 检查 3：硬编码凭证 ----------
echo "--- 检查 3: 硬编码凭证/密钥 ---"

CRED_PATTERNS=(
    'api_key\s*=\s*"[A-Za-z0-9_-]{20,}"'
    'password\s*=\s*"[^"]+"'
    'secret\s*=\s*"[^"]+"'
    'token\s*=\s*"[^"]+"'
    'sk-[A-Za-z0-9]{20,}'
    'Bearer\s+[A-Za-z0-9_-]{20,}'
    'Authorization\s*[:=]\s*"[^"]+"'
    'access_key\s*=\s*"[^"]+"'
)

ALL_SRC=$(echo "$FILES" | grep -E '\.(py|js|ts|json|yml|yaml|sh)$' 2>/dev/null || true)

if [ -n "$ALL_SRC" ]; then
    for pattern in "${CRED_PATTERNS[@]}"; do
        matches=$(grep -Hn "$pattern" $ALL_SRC 2>/dev/null || true)
        if [ -n "$matches" ]; then
            echo "$matches" | while IFS= read -r line; do
                yellow "  [WARNING] 疑似硬编码凭证: $line"
                WARNINGS=$((WARNINGS + 1))
            done
        fi
    done
fi

# ---------- 检查 4：print 了敏感信息 ----------
echo "--- 检查 4: 调试输出敏感信息 ---"

if [ -n "$PY_FILES" ]; then
    DEBUG_LEAK=$(grep -Hn 'print(.*api_key\|print(.*password\|print(.*token\|print(.*secret' $PY_FILES 2>/dev/null || true)
    if [ -n "$DEBUG_LEAK" ]; then
        yellow "  [WARNING] print 输出可能含敏感信息:"
        echo "$DEBUG_LEAK" | while IFS= read -r line; do
            yellow "    $line"
            WARNINGS=$((WARNINGS + 1))
        done
    fi
fi

# ---------- 结果汇总 ----------
echo ""
echo "=============================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    green "✓ 安全检查通过，未发现问题"
    echo "=============================="
    echo ""
    exit 0
fi

if [ $ERRORS -gt 0 ]; then
    red "✗ $ERRORS 个错误必须修复"
fi
if [ $WARNINGS -gt 0 ]; then
    yellow "! $WARNINGS 个警告建议检查"
fi
echo "=============================="
echo ""

# 错误时返回非 0，可用作 pre-commit hook
[ $ERRORS -eq 0 ] || exit 1
