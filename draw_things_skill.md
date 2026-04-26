# Draw Things 앱 자동화 스킬 (엄격한 형식 버전)

이 문서는 로컬 AI가 Draw Things API의 규격을 정확히 지켜서 그림을 그리도록 강제하는 지침서입니다.

## 1. 기본 정보
- **API 주소:** `http://localhost:7860`
- **엔드포인트:** `/sdapi/v1/txt2img`

## 2. 절대 규칙 (반드시 준수)
1. **JSON 항목 제한:** 오직 `prompt`, `steps`, `width`, `height`, `cfg_scale` 항목만 사용하라.
2. **잘못된 항목 금지:** `"style"`, `"lighting"`, `"palette"`, `"detail"`, `"composition"` 같은 항목을 별도로 만들지 마라. (API 오류 발생 원인)
3. **모든 묘사는 Prompt에:** 스타일, 조명, 구도 등 모든 설명은 반드시 `"prompt"` 값 안에 쉼표(,)로 구분하여 텍스트로 넣어라.
4. **해상도:** SDXL 모델 성능을 위해 반드시 `width: 1024`, `height: 1024`를 사용하라.

## 3. 올바른 실행 예시
```bash
curl -X POST http://localhost:7860/sdapi/v1/txt2img -H "Content-Type: application/json" -d '{"prompt": "score_9, score_8, score_7, rating_safe, Cute dog, Studio Ghibli Style, Soft Afternoon Sunlight, masterpiece", "steps": 25, "width": 1024, "height": 1024, "cfg_scale": 7}'
```

---
*이 파일의 지침을 어기면 Draw Things 서버에서 에러를 반환합니다. 지침을 엄격히 따르십시오.*
