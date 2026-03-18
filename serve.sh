#!/usr/bin/env bash
#
# Usage:
#   ./serve.sh        Start the website (http://localhost:8000)
#   ./serve.sh on     Same as above
#   ./serve.sh off    Stop the website
#   ./serve.sh status Check if running
#   ./serve.sh pdf    Build the PDF (outputs site/aosp-internals.pdf)
#   ./serve.sh epub   Build the EPUB (outputs site/aosp-internals.epub)
#
set -euo pipefail

case "${1:-on}" in
  on|start)
    docker compose down 2>/dev/null
    docker compose build serve
    docker compose up -d serve
    echo -n "Waiting for site"
    for i in $(seq 1 30); do
      if curl -s -o /dev/null http://localhost:8000 2>/dev/null; then
        echo ""
        echo "Website ready at http://localhost:8000"
        exit 0
      fi
      echo -n "."
      sleep 1
    done
    echo ""
    echo "Website started but may still be building (check: docker compose logs serve)"
    ;;
  off|stop)
    docker compose down
    echo "Website stopped"
    ;;
  status)
    docker compose ps serve
    ;;
  pdf)
    docker compose down 2>/dev/null
    echo "Building PDF (pre-rendered mermaid diagrams, cached)..."
    docker compose build build-pdf
    docker compose run --rm build-pdf
    echo "PDF generated: site/aosp-internals.pdf"
    ;;
  epub)
    docker compose down 2>/dev/null
    echo "Building EPUB (pre-rendered mermaid diagrams, cached)..."
    docker compose build build-epub
    docker compose run --rm build-epub
    echo "EPUB generated: site/aosp-internals.epub"
    ;;
  *)
    echo "Usage: $0 [on|off|status|pdf|epub]"
    exit 1
    ;;
esac
