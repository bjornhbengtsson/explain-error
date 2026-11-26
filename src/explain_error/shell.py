"""Shell integration: `eval "$(xerr init bash)"` and friends.

After a command fails, the shell prints a dim hint. Typing `huh` explains the
failure. Shells don't keep a command's output, so `huh` re-runs the failed
command (after asking) to capture its error. PowerShell keeps its own errors in
$Error, so those are explained without re-running.

The hooks are plain shell code that runs at each prompt; Python only starts
when you type `huh`.
"""

from __future__ import annotations

import re

NAME_PLACEHOLDER = "__XERR_HUH__"
DEFAULT_NAME = "huh"
SHELLS = ("bash", "zsh", "fish", "powershell")

BASH = r"""
# explain-error shell integration for bash. Load it with:  eval "$(xerr init bash)"
__xerr_failed_cmd=""
__xerr_failed_status=0
__xerr_hist_id=$(HISTTIMEFORMAT= builtin history 1 | sed -E 's/^ *([0-9]+).*/\1/')

__xerr_prompt_hook() {
  local ec=$? line id cmd
  line=$(HISTTIMEFORMAT= builtin history 1)
  if [[ $line =~ ^[[:space:]]*([0-9]+)[*]?[[:space:]]+(.*)$ ]]; then
    id=${BASH_REMATCH[1]}
    cmd=${BASH_REMATCH[2]}
  else
    return $ec
  fi
  [[ $id == "$__xerr_hist_id" ]] && return $ec
  __xerr_hist_id=$id
  if (( ec != 0 && ec != 130 )) && [[ $cmd != __XERR_HUH__* ]]; then
    __xerr_failed_cmd=$cmd
    __xerr_failed_status=$ec
    [[ -z ${XERR_NO_HINT-} ]] && printf '\033[2mexit %s - type __XERR_HUH__ to explain\033[0m\n' "$ec" >&2
  fi
  return $ec
}

__XERR_HUH__() {
  local cmd=$__xerr_failed_cmd ec=$__xerr_failed_status reply tmp code
  local -a flags=()
  [[ -t 1 ]] && flags+=(--color)
  [[ -n ${XERR_AI-} ]] && flags+=(--ai)
  if [[ -z $cmd ]]; then
    echo "__XERR_HUH__: no failed command to explain yet" >&2
    return 1
  fi
  if (( ec == 127 )); then
    command explain-error "${flags[@]}" "bash: ${cmd%% *}: command not found"
    return
  fi
  if [[ -z ${XERR_NO_CONFIRM-} ]]; then
    read -r -p "Re-run \`$cmd\` to capture its error? [Y/n] " reply || return 130
    [[ $reply == [nN]* ]] && return 1
  fi
  tmp=$(mktemp "${TMPDIR:-/tmp}/xerr.XXXXXX") || return 1
  { eval "$cmd"; } 2>&1 | tee "$tmp"
  code=${PIPESTATUS[0]}
  if (( code == 0 )); then
    printf '\033[2m(it worked this time)\033[0m\n'
  else
    echo
    command explain-error "${flags[@]}" < "$tmp"
  fi
  rm -f "$tmp"
  return 0
}

if [[ ${PROMPT_COMMAND-} != *__xerr_prompt_hook* ]]; then
  PROMPT_COMMAND="__xerr_prompt_hook${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi
"""

ZSH = r"""
# explain-error shell integration for zsh. Load it with:  eval "$(xerr init zsh)"
typeset -g __xerr_cur_cmd="" __xerr_failed_cmd="" __xerr_failed_status=0

__xerr_preexec() { __xerr_cur_cmd=$1 }

__xerr_precmd() {
  local ec=$? cmd=$__xerr_cur_cmd
  __xerr_cur_cmd=""
  [[ -z $cmd ]] && return
  if (( ec != 0 && ec != 130 )) && [[ $cmd != __XERR_HUH__* ]]; then
    __xerr_failed_cmd=$cmd
    __xerr_failed_status=$ec
    [[ -z ${XERR_NO_HINT-} ]] && printf '\033[2mexit %s - type __XERR_HUH__ to explain\033[0m\n' "$ec" >&2
  fi
}

__XERR_HUH__() {
  local cmd=$__xerr_failed_cmd ec=$__xerr_failed_status reply tmp code
  local -a flags
  [[ -t 1 ]] && flags+=(--color)
  [[ -n ${XERR_AI-} ]] && flags+=(--ai)
  if [[ -z $cmd ]]; then
    print -u2 "__XERR_HUH__: no failed command to explain yet"
    return 1
  fi
  if (( ec == 127 )); then
    command explain-error $flags "zsh: command not found: ${${(z)cmd}[1]}"
    return
  fi
  if [[ -z ${XERR_NO_CONFIRM-} ]]; then
    read -r "reply?Re-run \`$cmd\` to capture its error? [Y/n] " || return 130
    [[ $reply == [nN]* ]] && return 1
  fi
  tmp=$(mktemp "${TMPDIR:-/tmp}/xerr.XXXXXX") || return 1
  { eval "$cmd" } 2>&1 | tee "$tmp"
  code=${pipestatus[1]}
  if (( code == 0 )); then
    printf '\033[2m(it worked this time)\033[0m\n'
  else
    echo
    command explain-error $flags < "$tmp"
  fi
  rm -f "$tmp"
  return 0
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec __xerr_preexec
# Run first, so no other hook has changed $? yet.
precmd_functions=(__xerr_precmd ${precmd_functions:#__xerr_precmd})
"""

FISH = r"""
# explain-error shell integration for fish. Load it with:  xerr init fish | source
set -g __xerr_failed_cmd ""
set -g __xerr_failed_status 0

function __xerr_postexec --on-event fish_postexec
    set -l ec $status
    if test $ec -ne 0 -a $ec -ne 130; and not string match -qr '^\s*__XERR_HUH__\b' -- $argv[1]
        set -g __xerr_failed_cmd $argv[1]
        set -g __xerr_failed_status $ec
        if not set -q XERR_NO_HINT
            printf '\033[2mexit %s - type __XERR_HUH__ to explain\033[0m\n' $ec >&2
        end
    end
end

function __XERR_HUH__ --description "Explain the last failed command"
    set -l cmd $__xerr_failed_cmd
    set -l flags
    isatty stdout; and set flags $flags --color
    set -q XERR_AI; and set flags $flags --ai
    if test -z "$cmd"
        echo "__XERR_HUH__: no failed command to explain yet" >&2
        return 1
    end
    if test $__xerr_failed_status -eq 127
        set -l word (string split -m1 ' ' -- $cmd)[1]
        command explain-error $flags "fish: command not found: $word"
        return
    end
    if not set -q XERR_NO_CONFIRM
        read -l -P "Re-run `$cmd` to capture its error? [Y/n] " reply; or return 130
        string match -qr '^[nN]' -- $reply; and return 1
    end
    set -l tmp (mktemp); or return 1
    eval $cmd 2>&1 | tee $tmp
    set -l code $pipestatus[1]
    if test $code -eq 0
        printf '\033[2m(it worked this time)\033[0m\n'
    else
        echo
        command explain-error $flags < $tmp
    end
    rm -f $tmp
    return 0
end
"""

POWERSHELL = r"""
# explain-error shell integration for PowerShell. Load it with:
#   Invoke-Expression (& xerr init powershell | Out-String)
$global:__xerr_lastHistoryId = (Get-History -Count 1).Id
$global:__xerr_lastError = $global:Error[0]
$global:__xerr_failedCmd = $null
$global:__xerr_failedError = $null
if (-not $global:__xerr_origPrompt) { $global:__xerr_origPrompt = $function:prompt }

function global:prompt {
    $ok = $?
    $h = Get-History -Count 1
    if ($h -and $h.Id -ne $global:__xerr_lastHistoryId) {
        $global:__xerr_lastHistoryId = $h.Id
        $err = $global:Error[0]
        $newError = $err -and -not [object]::ReferenceEquals($err, $global:__xerr_lastError)
        if (-not $ok -and $h.CommandLine -notmatch '^\s*__XERR_HUH__\b') {
            $global:__xerr_failedCmd = $h.CommandLine
            $global:__xerr_failedError = if ($newError) { $err | Out-String } else { $null }
            if (-not $env:XERR_NO_HINT) {
                Write-Host "failed - type __XERR_HUH__ to explain" -ForegroundColor DarkGray
            }
        }
    }
    $global:__xerr_lastError = $global:Error[0]
    & $global:__xerr_origPrompt
}

function global:__XERR_HUH__ {
    $cmd = $global:__xerr_failedCmd
    if (-not $cmd) { Write-Host "__XERR_HUH__: no failed command to explain yet"; return }
    $exe = Get-Command explain-error -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exe) { Write-Host "__XERR_HUH__: explain-error isn't on PATH"; return }
    $flags = @()
    if (-not $env:NO_COLOR) { $flags += '--color' }
    if ($env:XERR_AI) { $flags += '--ai' }
    $OutputEncoding = New-Object System.Text.UTF8Encoding $false

    # PowerShell's own errors (like a command that doesn't exist) are already saved.
    if ($global:__xerr_failedError) {
        $global:__xerr_failedError | & $exe.Source @flags
        return
    }
    if (-not $env:XERR_NO_CONFIRM) {
        $answer = Read-Host "Re-run '$cmd' to capture its error? [Y/n]"
        if ($answer -match '^[nN]') { return }
    }
    $global:LASTEXITCODE = 0
    $script:__xerr_sawError = $false
    $lines = & { Invoke-Expression $cmd } 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $script:__xerr_sawError = $true }
        $line = "$_"
        Write-Host $line
        $line
    }
    if ($global:LASTEXITCODE -eq 0 -and -not $script:__xerr_sawError) {
        Write-Host "(it worked this time)" -ForegroundColor DarkGray
        return
    }
    Write-Host ""
    ($lines -join "`n") | & $exe.Source @flags
}
"""

SCRIPTS = {"bash": BASH, "zsh": ZSH, "fish": FISH, "powershell": POWERSHELL}

SETUP = """\
Add one line to your shell's startup file, then open a new terminal:

  bash        echo 'eval "$(xerr init bash)"' >> ~/.bashrc
  zsh         echo 'eval "$(xerr init zsh)"' >> ~/.zshrc
  fish        echo 'xerr init fish | source' >> ~/.config/fish/config.fish
  PowerShell  Add-Content $PROFILE 'Invoke-Expression (& xerr init powershell | Out-String)'

After a command fails, type `{name}` to explain it.
Use --name to pick another command name: xerr init bash --name wtf
Settings: XERR_NO_HINT=1 hides the hint, XERR_NO_CONFIRM=1 re-runs without asking,
XERR_AI=1 adds --ai.
"""

_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def script_for(shell: str, name: str = DEFAULT_NAME) -> str:
    shell = shell.lower()
    if shell in ("pwsh", "ps"):
        shell = "powershell"
    if shell not in SCRIPTS:
        raise ValueError(f"unsupported shell {shell!r}; choose from {', '.join(SHELLS)}")
    if not _VALID_NAME.match(name):
        raise ValueError(f"invalid command name {name!r}")
    return SCRIPTS[shell].replace(NAME_PLACEHOLDER, name).lstrip("\n")


def setup_text(name: str = DEFAULT_NAME) -> str:
    return SETUP.format(name=name)
