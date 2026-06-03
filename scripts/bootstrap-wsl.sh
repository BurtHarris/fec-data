#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[bootstrap-wsl] %s\n' "$*"
}

if [[ "${EUID}" -eq 0 ]]; then
  echo "Do not run as root. Run as your normal user." >&2
  exit 1
fi

if ! grep -qiE '(microsoft|wsl)' /proc/version; then
  log "Not running under WSL. Continuing anyway."
fi

log "Updating apt index"
sudo apt-get update

log "Installing base developer packages"
sudo apt-get install -y \
  build-essential \
  git \
  curl \
  wget \
  unzip \
  zip \
  ca-certificates \
  gnupg \
  lsb-release \
  pkg-config \
  software-properties-common

PROJECTS_DIR="${HOME}/projects"
if [[ ! -d "${PROJECTS_DIR}" ]]; then
  log "Creating ${PROJECTS_DIR}"
  mkdir -p "${PROJECTS_DIR}"
fi

if [[ -z "$(git config --global user.name || true)" ]]; then
  read -r -p "Git user.name: " git_name
  if [[ -n "${git_name}" ]]; then
    git config --global user.name "${git_name}"
  fi
fi

if [[ -z "$(git config --global user.email || true)" ]]; then
  read -r -p "Git user.email: " git_email
  if [[ -n "${git_email}" ]]; then
    git config --global user.email "${git_email}"
  fi
fi

git config --global core.autocrlf input
git config --global init.defaultBranch main

SSH_KEY_PATH="${HOME}/.ssh/id_ed25519"
if [[ ! -f "${SSH_KEY_PATH}" ]]; then
  read -r -p "Create a new SSH key at ${SSH_KEY_PATH}? [y/N]: " create_ssh
  if [[ "${create_ssh}" =~ ^[Yy]$ ]]; then
    mkdir -p "${HOME}/.ssh"
    chmod 700 "${HOME}/.ssh"
    ssh-keygen -t ed25519 -a 100 -f "${SSH_KEY_PATH}"
    eval "$(ssh-agent -s)"
    ssh-add "${SSH_KEY_PATH}"
    log "SSH public key:"
    cat "${SSH_KEY_PATH}.pub"
    log "Add this key to your Git host account before pushing."
  fi
fi

cat <<'OPTIONAL_RUNTIME_BLOCKS'

Optional runtime blocks (uncomment and run as needed):

# Node.js (via nvm)
# curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
# nvm install --lts

# Python (via pyenv)
# curl https://pyenv.run | bash
# export PATH="$HOME/.pyenv/bin:$PATH"
# eval "$(pyenv init -)"
# pyenv install 3.12
# pyenv global 3.12

# Go
# sudo apt-get install -y golang-go

# Rust
# curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Docker Engine in WSL (optional)
# sudo install -m 0755 -d /etc/apt/keyrings
# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
#   sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
# sudo chmod a+r /etc/apt/keyrings/docker.gpg
# echo \
#   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
#   https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
#   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
# sudo apt-get update
# sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# sudo usermod -aG docker "$USER"

OPTIONAL_RUNTIME_BLOCKS

log "WSL bootstrap complete."
log "Next: move repositories under ${PROJECTS_DIR} and open from WSL with: code ."
