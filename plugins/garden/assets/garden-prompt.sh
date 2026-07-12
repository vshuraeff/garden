#!/usr/bin/env bash

command -v jq >/dev/null 2>&1 || exit 0

input=$(jq -ce '
  if ((.prompt? | type) == "string") and (.prompt | length > 0)
    and ((.cwd? | type) == "string") and (.cwd | length > 0)
  then {prompt: .prompt, cwd: .cwd}
  else empty
  end
' 2>/dev/null)
input_status=$?

[ "$input_status" -eq 0 ] || exit 0
[ -n "$input" ] || exit 0

prompt=$(printf '%s\n' "$input" | jq -r '.prompt' 2>/dev/null)
prompt_status=$?
cwd=$(printf '%s\n' "$input" | jq -r '.cwd' 2>/dev/null)
cwd_status=$?

[ "$prompt_status" -eq 0 ] || exit 0
[ "$cwd_status" -eq 0 ] || exit 0
[ -n "$prompt" ] || exit 0

# use the event cwd rather than the hook process cwd
case "$cwd" in
  /*) ;;
  *) exit 0 ;;
esac

search_dir=$cwd
project_root=
levels=0

while :; do
  if [ -f "$search_dir/naming-registry.txt" ]; then
    project_root=$search_dir
    break
  fi

  [ "$search_dir" = / ] && break
  [ "$levels" -ge 30 ] && break

  parent_dir=$(dirname "$search_dir" 2>/dev/null) || exit 0
  [ "$parent_dir" = "$search_dir" ] && break
  search_dir=$parent_dir
  levels=$((levels + 1))
done

[ -n "$project_root" ] || exit 0

# bash 3.2 does not support lowercase parameter expansion
prompt_lower=$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]') || exit 0
skills=

case "$prompt_lower" in
  *"new project"*|*bootstrap*|*scaffold*|*"новый проект"*|*"заведи слайс"*|*"new slice"*)
    skills=garden:bootstrap
    ;;
esac

case "$prompt_lower" in
  *retrofit*|*legacy*|*"внедрить garden"*|*"инкрементально"*|*strangler*)
    if [ -n "$skills" ]; then
      skills="$skills or garden:retrofit"
    else
      skills=garden:retrofit
    fi
    ;;
esac

review_request=
garden_context=

case "$prompt_lower" in
  *review*|*"ревью"*|*diff*|*pr*|*commit*) review_request=1 ;;
esac

case "$prompt_lower" in
  *garden*|*principles*|*slice*|*contract*) garden_context=1 ;;
esac

if [ -n "$review_request" ] && [ -n "$garden_context" ]; then
  if [ -n "$skills" ]; then
    skills="$skills or garden:review"
  else
    skills=garden:review
  fi
fi

case "$prompt_lower" in
  *audit*|*"аудит"*|*compliance*|*checklist*|*"зрелость"*)
    if [ -n "$skills" ]; then
      skills="$skills or garden:audit"
    else
      skills=garden:audit
    fi
    ;;
esac

[ -n "$skills" ] || exit 0

message="garden: this is a GARDEN project (naming-registry.txt found); for this request use the $skills skill. Deterministic gates decide merges; never self-certify."
jq -cn --arg message "$message" '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":$message}}' || exit 0

exit 0
