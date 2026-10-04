# Invoked through the shell's ENOEXEC fallback: iPadOS rejects script shebang
# execs. Calling Bash explicitly also survives updates to the vendor script.
export MACWS_JIT_MPROTECT_COMPAT=1
export MACWS_JIT_FAULT_WRITE_COMPAT=1
exec /bin/bash '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code' "$@"
