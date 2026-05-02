#!/bin/bash

# 가상환경 활성화
source .venv/bin/activate

# 데이터 업데이트 실행 (한국+미국 통합)
echo "글로벌 주식 데이터를 통합 수집하고 있습니다 (KOSPI, KOSDAQ, S&P 500)..."
python collector.py

# 웹 서버 실행 및 대시보드 열기
echo "웹 서버를 실행하고 통합 대시보드를 브라우저에서 엽니다..."
python3 -m http.server 8080 --directory . > /dev/null 2>&1 &
SERVER_PID=$!

sleep 2
open "http://localhost:8080/index.html"

echo "완료되었습니다! 대시보드를 다 보신 후에는 터미널에서 Ctrl+C를 눌러 서버를 종료하세요."
wait $SERVER_PID
