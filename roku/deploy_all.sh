#!/bin/bash
# Deploy the app to every known Roku device.
# Usage: ./deploy_all.sh [PASSWORD]
#
# Password defaults to "admin" (common across all known devices).
# Pass a different value as the first arg to override.

cd "$(dirname "$0")" || exit

DEV_PASSWORD=${1:-admin}

# name:ip pairs
ROKUS=(
  "funroom:192.168.1.108"
  "master_bedroom:192.168.1.70"
  "squirrel_town:192.168.1.29"
  "living_room:192.168.1.63"
)

FAILED=()

for entry in "${ROKUS[@]}"; do
  NAME="${entry%%:*}"
  IP="${entry##*:}"
  echo ""
  echo "=== Deploying to $NAME ($IP) ==="
  if ./deploy.sh "$IP" "$DEV_PASSWORD"; then
    echo "[$NAME] OK"
  else
    echo "[$NAME] FAILED"
    FAILED+=("$NAME ($IP)")
  fi
done

echo ""
echo "=== Summary ==="
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All deployments succeeded."
  exit 0
else
  echo "Failed deployments:"
  for f in "${FAILED[@]}"; do
    echo "  - $f"
  done
  exit 1
fi
