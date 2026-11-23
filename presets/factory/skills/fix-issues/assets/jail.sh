# Sourced from the repo root. jail <dir> <cmd...>: empty HOME, no inherited secrets, repo hidden,
# $check read-only, only <dir> and $evidence writable, and only the $jail_tools runtimes mounted.

# jail_resolve <tool | tool=path>...: prints "<name> <executable> <runtime root>" lines to confirm.
jail_resolve() {
  local t exe top d
  for t; do
    case "$t" in *=*) exe=${t#*=} ;; *) exe=$(command -v "$t") ;; esac
    exe=$(readlink -f "$exe") top=$exe d=$(dirname "$exe")
    while [ "$d" != / ]; do
      [ -f "$d/package.json" ] && { top=$d; break; }
      d=$(dirname "$d")
    done
    echo "${t%%=*} $exe $top"
  done
}

jail() {
  local dir=$1 root=$PWD mask=() binds=() path=/tmp/bin name exe top p
  shift
  command -v bwrap > /dev/null || { echo "jail: needs Linux with bwrap; other platforms are later" >&2; return 1; }
  [ -S /run/docker.sock ] && mask=(--ro-bind /dev/null /run/docker.sock)
  while read -r name exe top; do
    [ -n "$name" ] || continue
    case "$top" in
      "$HOME"/.config/* | "$HOME"/.ssh/* | "$HOME"/.gnupg/* | "$HOME"/.local/share/keyrings*)
        echo "jail: refusing $top" >&2; return 1 ;;
      "$HOME"/*/*/*) binds+=(--ro-bind "$top" "$top") ;;
      "$HOME" | "$HOME"/*) echo "jail: refusing broad mount $top" >&2; return 1 ;;
    esac
    binds+=(--symlink "$exe" "/tmp/bin/$name")
  done <<< "${jail_tools:-}"
  for p in ${PATH//:/ }; do
    case "$p" in "$HOME" | "$HOME"/*) ;; *) path+=:$p ;; esac
  done
  (
    for v in $(compgen -e); do
      case $v in HOME | PATH | LANG | TERM | ANTHROPIC_API_KEY | CLAUDE_CODE_OAUTH_TOKEN) ;; *) unset "$v" 2> /dev/null ;; esac
    done
    exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /run/user --tmpfs "$HOME" \
      --tmpfs "$root" --dir /tmp/bin ${mask[@]+"${mask[@]}"} ${binds[@]+"${binds[@]}"} \
      --bind "$dir" "$dir" --bind "$evidence" "$evidence" --ro-bind "$check" "$check" \
      --ro-bind-try "$dir/.git" "$dir/.git" --setenv PATH "$path" --setenv evidence "$evidence" \
      --setenv check "$check" --unshare-pid --die-with-parent --chdir "$dir" "$@"
  )
}

# Passes only when the boundary holds and every confirmed tool starts: run before each stage.
jail_probe() {
  jail "$1" sh -c 'spec=$1; shift
    ! test -e "$spec" && ! test -e "$HOME/.config" && ! test -S /run/docker.sock && ! test -w .git &&
      ! test -w "$check" && test -w "$evidence" && claude --version > /dev/null || exit 1
    for t; do "$t" --version > /dev/null 2>&1 || { echo "jail: $t does not start" >&2; exit 1; }; done' \
    _ "$2" $(printf '%s\n' "${jail_tools:-}" | cut -d' ' -f1)
}
