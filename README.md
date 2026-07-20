# 활주로 이용률 정밀 분석 (Runway Wind Usability Analysis)

기상청 ASOS/AWS 시간 관측자료를 기반으로 활주로 방향별 측풍(Crosswind) 이용률과 풍배도를
분석하는 Streamlit 단일 파일 앱입니다. ICAO Annex 14 / Doc.9157 Airport Design Manual
Part 1 기준에 따라 최적 활주로 방향을 산정하고, 분석 결과를 검토서(.docx) 초안으로도
내보냅니다.

## 주요 기능

- **관측소 선택**: 전국 94개 ASOS(종관) 관측소 내장 선택 + AWS(방재) 시간자료 CSV 업로드 +
  주소 입력으로 가까운 관측소 자동 탐색(카카오 지오코딩 + 기상청 API 허브 위경도 DB)
- **분석기간**: 최근 10년 / 최근 5년 / 사용자 지정 프리셋 (ICAO 권고 최소 5년 자동 안내)
- **측풍 허용치**: 활주로 길이 입력 시 ICAO Doc.9157 Table 1 기준 10 / 13 / 20 kt 자동 선택,
  수동 전환 가능 — 세 허용치를 항상 동시에 계산해 비교
- **분석 결과**: 허용치별 종합표, 방향별 이용률 곡선, 16방위 바람장미, 16방위×풍속구간
  빈도표, 2개 활주로 최적 조합(합집합 이용률), 10° 간격 방위각 상세표(CSV 다운로드)
- **데이터 품질 검토**: 유효/결측 데이터 구분 및 Excel 2-시트 다운로드
- **검토서 자동 생성**: 분석 결과를 ICAO 기준 서술형 검토서(.docx)로 즉시 다운로드
  (`assets/report_template.docx` 스타일 상속, matplotlib 정적 차트 삽입)

## 빠른 시작

```bash
pip install -r requirements.txt
python -m streamlit run app.py --server.headless true --server.port 8513
```

### API 키 설정

로컬에서 실행하려면 `.streamlit/secrets.toml`을 만들고 아래 세 키를 채워 넣습니다
(이 파일은 `.gitignore`에 등록되어 있어 GitHub에는 올라가지 않습니다).

```toml
ASOS_API_KEY = "공공데이터포털에서 발급받은 Decoding 키"
KMA_HUB_KEY  = "기상청 API 허브 인증키"
KAKAO_REST_KEY = "카카오 REST API 키"
```

| 키 | 발급처 | 용도 |
|---|---|---|
| `ASOS_API_KEY` | [공공데이터포털](https://www.data.go.kr) — AsosHourlyInfoService | ASOS 시간 관측자료(풍향·풍속) 수집 |
| `KMA_HUB_KEY` | [기상청 API 허브](https://apihub.kma.go.kr) — `stn_inf.php` | 관측소 위경도 DB 조회(주소 자동선택용) |
| `KAKAO_REST_KEY` | [Kakao Developers](https://developers.kakao.com) | 주소 → 위경도 지오코딩 |

`.streamlit/secrets.toml`이 없어도 앱 화면의 **API 키 설정** 버튼에서 직접 입력할 수
있으며, 입력값은 브라우저 세션에만 유지됩니다.

Streamlit Community Cloud에 배포할 때는 위 3개 키를 앱의 **Settings → Secrets**에
동일한 형식(TOML)으로 등록합니다.

## 사용법

1. **관측소 선택** — ASOS 지역/지점 선택, AWS는 [기상자료개방포털](https://data.kma.go.kr)에서
   내려받은 CSV 업로드, 또는 주소 입력으로 최근접 관측소 자동 선택
2. **분석기간** 설정 (기본 최근 10년)
3. **측풍 허용치** 확인 — 활주로 길이 입력 시 자동 산정, 필요 시 수동 선택
4. **분석 시작** 클릭 → 이용률·풍배도·빈도표·상세표 확인
5. 필요 시 **검토서 다운로드(.docx)** 로 ICAO 기준 검토서 초안 확보

## 분석 방법론

```
이용률(%) = (Calm 관측수 + 측풍성분 ≤ 허용치 관측수) ÷ 전체 관측수 × 100
```

- Calm(정온): 풍속 3 kt(1.5 m/s) 이하 — 방향 무관 전 방향에서 이용 가능으로 집계
- 측풍 허용치 3종(10/13/20 kt)의 이용률을 합산한 결합 기준으로 단일 최적 방향을 공동 선정
- 활주로 명칭이 10° 단위로만 존재하는 점을 반영해 분석 격자도 10° 단위(0°~170°, 18방향)로 고정
- 근거: ICAO Annex 14, ICAO Doc.9157 Airport Design Manual Part 1, 신동진·김도현(2009)
  "활주로 방향설정을 위한 풍배도 프로그램의 개발 연구"

## 프로젝트 구조

```
app.py                          # 전체 로직 (수집·분석·UI·검토서 생성)
assets/report_template.docx     # 검토서 스타일 템플릿 (글꼴·표 스타일·머리말/꼬리말)
assets/report_template_guide.md # 템플릿 편집 가이드
.streamlit/secrets.toml         # API 키 (gitignore, 로컬 전용)
```

## 보안

API 키는 코드에 절대 하드코딩하지 않습니다. `.streamlit/secrets.toml`(로컬,
gitignore 처리)과 `st.session_state`(런타임 세션)에서만 관리되며, 이 저장소는
**퍼블릭**이므로 코드를 수정한 뒤에는 아래 명령으로 키 유출 여부를 확인한 후 커밋합니다.

```bash
grep -oE '[A-Za-z0-9+/=_-]{15,}' .streamlit/secrets.toml \
  | while IFS= read -r k; do grep -qF "$k" app.py && echo "[유출] $k"; done
```

## 배포

[Streamlit Community Cloud](https://streamlit.io/cloud)에 `main` 브랜치 푸시 시
자동 반영됩니다.
