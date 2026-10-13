#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="leon0906"
BACKEND_IMAGE="${NAMESPACE}/contract-review-backend"
FRONTEND_IMAGE="${NAMESPACE}/contract-review-frontend"
PLATFORM="${PLATFORM:-linux/amd64}"
PUSH_IMAGES=true
TAG_LATEST=false

usage() {
  cat <<'EOF'
用法：
  ./scripts/build-and-push-images.sh <版本号> [--latest] [--load-only]

示例：
  ./scripts/build-and-push-images.sh v1.0.0
  ./scripts/build-and-push-images.sh v1.0.0 --latest
  ./scripts/build-and-push-images.sh v1.0.0 --load-only

选项：
  --latest     同时创建并推送 latest 标签；正式部署仍应使用明确版本号。
  --load-only  只构建并加载到本机，不检查登录、不执行推送，用于发布前验证。

默认平台为 linux/amd64，可通过 PLATFORM 环境变量覆盖。
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

trap 'echo "ERROR: 镜像构建或推送失败（脚本第 ${LINENO} 行）。" >&2' ERR

VERSION="${1:-}"
if [[ -z "${VERSION}" || "${VERSION}" == "--help" || "${VERSION}" == "-h" ]]; then
  usage
  [[ -n "${VERSION}" ]] && exit 0
  exit 2
fi
shift

while (($#)); do
  case "$1" in
    --latest) TAG_LATEST=true ;;
    --load-only) PUSH_IMAGES=false ;;
    --help|-h) usage; exit 0 ;;
    *) fail "未知参数：$1" ;;
  esac
  shift
done

[[ "${VERSION}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] \
  || fail "版本号不符合 Docker 标签规则：${VERSION}"
[[ "${PLATFORM}" == "linux/amd64" ]] \
  || echo "WARNING: 当前构建平台为 ${PLATFORM}；普通阿里云 x86 服务器应使用 linux/amd64。" >&2

docker info >/dev/null 2>&1 \
  || fail "Docker 未运行或当前用户无法访问 Docker。请先启动 Docker Desktop/Engine。"
docker buildx version >/dev/null 2>&1 \
  || fail "当前 Docker 未提供 buildx，无法执行跨平台构建。"

grep -qx '.env' "${ROOT_DIR}/backend/.dockerignore" \
  || fail "backend/.dockerignore 未排除 .env，已停止构建。"
grep -qx '.env' "${ROOT_DIR}/frontend/.dockerignore" \
  || fail "frontend/.dockerignore 未排除 .env，已停止构建。"

if ${PUSH_IMAGES}; then
  docker info 2>/dev/null | grep -Eq '^[[:space:]]*Username:' \
    || fail "未检测到 Docker Hub 登录状态。请先亲自执行：docker login -u leon0906"
fi

build_image() {
  local image="$1"
  local context="$2"
  local tags=(-t "${image}:${VERSION}")

  if ${TAG_LATEST}; then
    tags+=(-t "${image}:latest")
  fi

  echo "Building ${image}:${VERSION} for ${PLATFORM}..."
  docker buildx build \
    --platform "${PLATFORM}" \
    "${tags[@]}" \
    --load \
    "${context}"
}

verify_local_image() {
  local image="$1"
  local expected_tag="${image}:${VERSION}"
  local architecture
  local operating_system

  architecture="$(docker image inspect --format '{{.Architecture}}' "${expected_tag}")"
  operating_system="$(docker image inspect --format '{{.Os}}' "${expected_tag}")"
  [[ "${architecture}" == "amd64" ]] \
    || fail "${expected_tag} 架构为 ${architecture}，期望 amd64。"
  [[ "${operating_system}" == "linux" ]] \
    || fail "${expected_tag} 操作系统为 ${operating_system}，期望 linux。"
  docker image inspect --format '{{range .RepoTags}}{{println .}}{{end}}' "${expected_tag}" \
    | grep -Fxq "${expected_tag}" \
    || fail "本地镜像缺少预期标签：${expected_tag}"
}

verify_runtime() {
  docker run --rm --platform "${PLATFORM}" --entrypoint sh "${BACKEND_IMAGE}:${VERSION}" -c '
    set -eu
    python -c "import fastapi, sqlalchemy, alembic, httpx, pypdf, docx"
    command -v soffice >/dev/null
    command -v pdftoppm >/dev/null
    command -v tesseract >/dev/null
    tesseract --list-langs 2>/dev/null | grep -qx chi_sim
    tesseract --list-langs 2>/dev/null | grep -qx eng
    fc-match "Noto Sans CJK SC" | grep -qi Noto
  '
  docker run --rm --platform "${PLATFORM}" --add-host backend:127.0.0.1 \
    --entrypoint sh "${FRONTEND_IMAGE}:${VERSION}" -c '
    set -eu
    nginx -t
    grep -q "proxy_pass http://backend:8000" /etc/nginx/conf.d/default.conf
  '
}

build_image "${BACKEND_IMAGE}" "${ROOT_DIR}/backend"
build_image "${FRONTEND_IMAGE}" "${ROOT_DIR}/frontend"

verify_local_image "${BACKEND_IMAGE}"
verify_local_image "${FRONTEND_IMAGE}"
verify_runtime

if ${PUSH_IMAGES}; then
  echo "Runtime verification passed; pushing version tags..."
  docker push "${BACKEND_IMAGE}:${VERSION}"
  docker push "${FRONTEND_IMAGE}:${VERSION}"
  if ${TAG_LATEST}; then
    docker push "${BACKEND_IMAGE}:latest"
    docker push "${FRONTEND_IMAGE}:latest"
  fi
fi

echo "Verified images:"
echo "  ${BACKEND_IMAGE}:${VERSION} (${PLATFORM})"
echo "  ${FRONTEND_IMAGE}:${VERSION} (${PLATFORM})"
if ${TAG_LATEST}; then
  if ${PUSH_IMAGES}; then
    echo "  latest tags were also created and pushed."
  else
    echo "  latest tags were also created locally."
  fi
fi
if ! ${PUSH_IMAGES}; then
  echo "Local-only validation completed; no Docker Hub push was attempted."
fi
