#!/usr/bin/env bash

command -v jq >/dev/null 2>&1 || exit 0

file_path=$(jq -r '
  .tool_input? as $input
  | if (($input | type) == "object") and (($input.file_path? | type) == "string")
    then $input.file_path
    else empty
    end
' 2>/dev/null)
jq_status=$?

[ "$jq_status" -eq 0 ] || exit 0
[ -n "$file_path" ] || exit 0

case "$file_path" in
  /*) ;;
  *) exit 0 ;;
esac

file_dir=${file_path%/*}
[ -n "$file_dir" ] || file_dir=/

search_dir=$file_dir
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

file_name=${file_path##*/}

if [ "$file_path" = "$project_root/CONTEXT.md" ] && [ -r "$file_path" ]; then
  line_count=0
  context_line=
  while IFS= read -r context_line || [ -n "$context_line" ]; do
    line_count=$((line_count + 1))
  done < "$file_path"

  if [ "$line_count" -gt 200 ]; then
    printf '%s\n' "garden: CONTEXT.md exceeds the 200-line MUST budget ($line_count lines); trim or move detail into capability READMEs" >&2
    exit 2
  fi
fi

if [ "$file_name" = "CONTRACT.md" ]; then
  first_nonempty=
  contract_line=

  if [ -r "$file_path" ]; then
    while IFS= read -r contract_line || [ -n "$contract_line" ]; do
      if [ -n "$contract_line" ]; then
        first_nonempty=$contract_line
        first_nonempty=${first_nonempty%$'\r'}
        break
      fi
    done < "$file_path"
  fi

  if [[ ! "$first_nonempty" =~ ^Version:\ [0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s\n' "garden: CONTRACT.md must start with a 'Version: MAJOR.MINOR.PATCH' line" >&2
    exit 2
  fi
fi

case "$file_name" in
  .*|*.md|*.txt|*.json|*.yml|*.yaml|*.toml|*.lock|Dockerfile|Makefile|LICENSE|NOTICE|CHANGELOG|Gemfile|Gemfile.lock|Pipfile|Pipfile.lock|Rakefile|Procfile) exit 0 ;;
esac

case "$project_root" in
  /) relative_path=${file_path#/} ;;
  *) relative_path=${file_path#"$project_root"/} ;;
esac

case "$relative_path" in
  */*) ;;
  *) exit 0 ;;
esac

directory_path=${relative_path%/*}
remaining_path=$directory_path

while [ -n "$remaining_path" ]; do
  case "$remaining_path" in
    */*) path_component=${remaining_path%%/*}; remaining_path=${remaining_path#*/} ;;
    *) path_component=$remaining_path; remaining_path= ;;
  esac

  case "$path_component" in
    .*|node_modules|vendor|build|dist|target) exit 0 ;;
  esac
done

capability_name=${relative_path%%/*}
capability_dir=$project_root/$capability_name

[ -d "$capability_dir" ] || exit 0
command -v find >/dev/null 2>&1 || exit 0

message=

if [ ! -f "$capability_dir/CONTRACT.md" ]; then
  message="garden: capability '$capability_name' has no CONTRACT.md; GARDEN requires a contract before implementation (R principle)"
fi

test_match=$(find "$capability_dir" \( -type d -name tests -o -type f -name '*test*' -o -type f -name '*spec*' \) -print -quit 2>/dev/null)
find_status=$?

[ "$find_status" -eq 0 ] || exit 0

if [ -z "$test_match" ]; then
  test_message="garden: capability '$capability_name' has no colocated tests (A principle)"
  if [ -n "$message" ]; then
    message="$message; $test_message"
  else
    message=$test_message
  fi
fi

if [ -n "$message" ]; then
  jq -cn --arg message "$message" '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":$message}}' || exit 0
fi

exit 0
